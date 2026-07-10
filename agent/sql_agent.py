import os
import json
import re
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from agent.memory import save_message, get_history, log_query
from agent.validator import validate_sql

load_dotenv(override=True)

DEFAULT_DB_PATH = "sample_data/sales.db"


# ── Engine factory (SQLite + PostgreSQL) ──────────────────────────────────────

def _build_engine(db_path: str):
    """Supports both SQLite file paths and PostgreSQL URLs."""
    if db_path.startswith("postgresql://") or db_path.startswith("postgres://"):
        return create_engine(db_path)
    return create_engine(f"sqlite:///{db_path}")


# ── Schema discovery ──────────────────────────────────────────────────────────

def get_schema_description(db_path: str = DEFAULT_DB_PATH) -> str:
    engine    = _build_engine(db_path)
    inspector = inspect(engine)
    parts     = []
    for table in inspector.get_table_names():
        cols    = inspector.get_columns(table)
        col_str = ", ".join(f"{c['name']} ({str(c['type'])})" for c in cols)
        parts.append(f"Table `{table}`: {col_str}")
    engine.dispose()
    return "\n".join(parts)


SCHEMA = get_schema_description()


# ── SQL execution ─────────────────────────────────────────────────────────────

def run_sql(sql: str, db_path: str = DEFAULT_DB_PATH):
    try:
        engine = _build_engine(db_path)
        df     = pd.read_sql_query(sql, engine)
        engine.dispose()
        return df, None
    except Exception as e:
        return None, str(e)


# ── Chart type selector ───────────────────────────────────────────────────────

def suggest_chart_type(df: pd.DataFrame, question: str) -> str:
    if df is None or df.empty:
        return "none"
    cols     = df.columns.tolist()
    num_cols = df.select_dtypes(include="number").columns.tolist()
    q        = question.lower()

    if any(w in q for w in ["trend", "over time", "monthly", "quarterly", "weekly", "yearly"]):
        return "line"
    if any(w in q for w in ["share", "proportion", "percent", "breakdown"]) and len(df) <= 8:
        return "pie"
    if any(k in " ".join(cols).lower() for k in ["date", "month", "quarter", "year"]):
        return "line"
    if len(num_cols) >= 2 and len(df) > 10:
        return "scatter"
    return "bar"


# ── System prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = f"""You are a SQLite SQL expert. The database schema is:

{SCHEMA}

CRITICAL INSTRUCTIONS:
- Respond with ONLY a JSON object. Nothing before it. Nothing after it.
- No greetings. No markdown. No code fences. No explanation outside JSON.
- Your entire response must be parseable by Python's json.loads()

JSON format (exactly these 3 keys):
{{"sql":"SELECT ... LIMIT 500","explanation":"what the query does","insight":"one key finding"}}

SQLite rules:
- strftime('%Y', date) for year, strftime('%m', date) for month
- Q1=01,02,03 | Q2=04,05,06 | Q3=07,08,09 | Q4=10,11,12
- Never use DATE_TRUNC or non-SQLite functions
- Always LIMIT 500
"""


# ── LLM factory ───────────────────────────────────────────────────────────────

def get_llm():
    return ChatGroq(
        model   = "llama-3.3-70b-versatile",
        temperature = 0,
        api_key = os.getenv("GROQ_API_KEY")
    )


# ── JSON extractor ────────────────────────────────────────────────────────────

def extract_json(raw: str) -> dict:
    raw   = raw.strip()
    raw   = re.sub(r"^```(?:json)?\s*", "", raw)
    raw   = re.sub(r"\s*```$",          "", raw)
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        return json.loads(match.group())
    return json.loads(raw)


# ── Main agent ────────────────────────────────────────────────────────────────

def ask_agent(
    question:   str,
    session_id: str = "default",
    db_path:    str = DEFAULT_DB_PATH
) -> dict:

    llm     = get_llm()
    history = get_history(session_id, limit=6)

    # Refresh schema if using a non-default DB
    schema   = get_schema_description(db_path)
    system   = SYSTEM_PROMPT.replace(SCHEMA, schema) if db_path != DEFAULT_DB_PATH else SYSTEM_PROMPT

    messages = [SystemMessage(content=system)]
    for h in history:
        if h["role"] == "user":
            messages.append(HumanMessage(content=h["content"]))
        else:
            messages.append(AIMessage(content=h["content"]))
    messages.append(HumanMessage(content=question))

    save_message(session_id, "user", question)

    # ── LLM call ──────────────────────────────────────────────────────────────
    try:
        response = llm.invoke(messages)
        raw      = response.content.strip()

        if not raw:
            raise ValueError("LLM returned empty response")

        parsed      = extract_json(raw)
        sql         = parsed.get("sql", "").strip()
        explanation = parsed.get("explanation", "")
        insight     = parsed.get("insight", "")

        if not sql:
            raise ValueError("LLM returned no SQL")

    except Exception as e:
        # Retry with simpler prompt
        try:
            simple = f"""Write a SQLite SQL query to answer: {question}

Schema:
{schema}

Rules: strftime for dates, LIMIT 500, SQLite only.
Respond ONLY with JSON: {{"sql":"...","explanation":"...","insight":"..."}}"""

            resp2       = llm.invoke([HumanMessage(content=simple)])
            raw2        = resp2.content.strip()
            if not raw2:
                raise ValueError("Empty retry response")
            parsed      = extract_json(raw2)
            sql         = parsed.get("sql", "").strip()
            explanation = parsed.get("explanation", "")
            insight     = parsed.get("insight", "")
        except Exception as e2:
            return {
                "error":      f"LLM failed: {str(e2)}",
                "sql":        "", "explanation": "", "insight": "",
                "chart_type": "none", "data": [], "columns": [],
                "opt_hints":  [], "validation": {}
            }

    # ── Validate SQL ──────────────────────────────────────────────────────────
    validation = validate_sql(sql)

    if not validation.is_safe:
        log_query(session_id, question, sql, 0, False)
        return {
            "error":       f"Query blocked: {validation.message}",
            "sql":         sql,
            "explanation": explanation,
            "insight":     f"Blocked for safety. {validation.suggestion}",
            "chart_type":  "none",
            "data":        [],
            "columns":     [],
            "row_count":   0,
            "opt_hints":   [],
            "validation":  {"risk": validation.risk, "message": validation.message}
        }

    # ── Run SQL ───────────────────────────────────────────────────────────────
    df, sql_error = run_sql(sql, db_path)

    # ── Auto-retry on SQL error ───────────────────────────────────────────────
    if sql_error:
        retry_msg = f"""This SQL failed: {sql_error}
Original question: {question}
Bad SQL: {sql}
Fix it and return only the corrected JSON."""
        try:
            retry     = llm.invoke([SystemMessage(content=system),
                                    HumanMessage(content=retry_msg)])
            retry_p   = extract_json(retry.content)
            sql       = retry_p.get("sql", sql).strip()
            explanation = retry_p.get("explanation", explanation)
            insight     = retry_p.get("insight", insight)
            df, sql_error = run_sql(sql, db_path)
        except Exception:
            pass

    if sql_error:
        log_query(session_id, question, sql, 0, False)
        return {
            "error":      f"SQL error: {sql_error}",
            "sql":        sql, "explanation": explanation,
            "insight":    "", "chart_type": "none",
            "data":       [], "columns":    [],
            "opt_hints":  [], "validation": {}
        }

    # ── Success ───────────────────────────────────────────────────────────────
    chart_type = suggest_chart_type(df, question)
    data       = df.to_dict(orient="records")
    columns    = df.columns.tolist()
    row_count  = len(df)

    save_message(session_id, "assistant",
                 f"[{row_count} rows] {insight}", sql_query=sql)
    log_query(session_id, question, sql, row_count, True)

    # ── Auto optimization hints ───────────────────────────────────────────────
    opt_hints = []
    try:
        from agent.optimizer import analyse_query
        opt_report = analyse_query(sql, db_path)
        opt_hints  = [
            s.issue for s in opt_report.suggestions
            if s.severity in ("critical", "warning")
        ][:2]
    except Exception:
        pass

    return {
        "error":       None,
        "sql":         sql,
        "explanation": explanation,
        "insight":     insight,
        "chart_type":  chart_type,
        "data":        data,
        "columns":     columns,
        "row_count":   row_count,
        "opt_hints":   opt_hints,
        "validation":  {"risk": validation.risk, "message": validation.message}
    }