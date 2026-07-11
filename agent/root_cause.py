import pandas as pd
from sqlalchemy import create_engine, inspect, text
from dataclasses import dataclass, field
from typing import List, Optional
import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage

load_dotenv(override=True)


# ── Schema discovery ──────────────────────────────────────────────────────────

def _discover_rca_schema(engine) -> dict:
    """
    Auto-discovers the best table + columns for root cause analysis.
    Returns: {table, date_col, metric_col, category_cols, row_count}
    """
    inspector = inspect(engine)
    tables    = inspector.get_table_names()

    date_kws     = ["date","time","created","updated","timestamp"]
    metric_kws   = ["revenue","amount","fee","bill","net","gross","total",
                    "cost","price","salary","sales","income","profit",
                    "quantity","marks","score","rating"]
    skip_kws     = ["id","key","code","rank","index","number","pct",
                    "percent","rate","age","days","hours","minutes"]
    cat_kws      = ["region","city","state","department","dept","branch",
                    "category","channel","type","status","grade","class",
                    "section","sector","specialization","location","zone",
                    "division","ward","reason","subject","product","doctor",
                    "teacher","course","cuisine","role","designation"]
    skip_cat_kws = ["name","email","address","comment","description",
                    "note","url","password","remark","request"]
    skip_types   = ["TEXT","VARCHAR","CHAR","STRING","BOOL"]
    numeric_types= ["INT","REAL","FLOAT","NUMERIC","DECIMAL","DOUBLE","NUMBER"]

    best       = None
    best_score = -1

    for table in tables:
        cols      = inspector.get_columns(table)
        col_names = [c["name"] for c in cols]
        col_types = {c["name"]: str(c["type"]).upper() for c in cols}

        # Find date column
        date_col = None
        for col in col_names:
            col_lower = col.lower()
            if col_lower in ["year","month","day","hour","week"]:
                continue
            if any(kw in col_lower for kw in date_kws):
                try:
                    with engine.connect() as conn:
                        sample = conn.execute(text(
                            f"SELECT `{col}` FROM `{table}` "
                            f"WHERE `{col}` IS NOT NULL LIMIT 3"
                        )).fetchall()
                    if sample:
                        val = str(sample[0][0])
                        if ("-" in val or "/" in val) and len(val) >= 8:
                            date_col = col
                            break
                except Exception:
                    continue

        if not date_col:
            continue

        # Find metric column
        metric_col  = None
        metric_score = -1
        for col in col_names:
            col_lower = col.lower()
            col_type  = col_types.get(col,"")
            if any(st in col_type for st in skip_types):
                continue
            if not any(nt in col_type for nt in numeric_types):
                continue
            if any(kw in col_lower for kw in skip_kws):
                continue
            score = 0
            if any(kw in col_lower for kw in ["revenue","amount","fee",
                                                "bill","net","total","salary"]):
                score = 30
            elif any(kw in col_lower for kw in metric_kws):
                score = 10
            else:
                score = 1
            if score > metric_score:
                metric_score = score
                metric_col   = col

        if not metric_col:
            continue

        # Find category columns
        cat_cols = []
        for col in col_names:
            col_lower = col.lower()
            col_type  = col_types.get(col,"")
            if col in [date_col, metric_col]:
                continue
            if any(st in col_type for st in skip_types) or \
               "TEXT" in col_type or "VARCHAR" in col_type or "CHAR" in col_type:
                if any(kw in col_lower for kw in cat_kws) and \
                   not any(kw in col_lower for kw in skip_cat_kws):
                    cat_cols.append(col)

        if not cat_cols:
            continue

        # Verify enough data
        try:
            with engine.connect() as conn:
                result = conn.execute(text(f"""
                    SELECT COUNT(DISTINCT strftime('%Y-%m', `{date_col}`)) as months,
                           COUNT(*) as rows
                    FROM `{table}`
                    WHERE `{date_col}` IS NOT NULL
                    AND `{metric_col}` IS NOT NULL
                """)).fetchone()
            months = result[0] if result else 0
            rows   = result[1] if result else 0
            if months < 3 or rows < 10:
                continue
        except Exception:
            continue

        score = metric_score + months + min(rows // 100, 20)
        if score > best_score:
            best_score = score
            best = {
                "table":      table,
                "date_col":   date_col,
                "metric_col": metric_col,
                "cat_cols":   cat_cols[:5],
                "row_count":  rows,
                "months":     months
            }

    return best


# ── Investigation queries ─────────────────────────────────────────────────────

def _run(engine, sql: str) -> pd.DataFrame:
    try:
        return pd.read_sql_query(sql, engine)
    except Exception:
        return pd.DataFrame()


def _build_period_filter(date_col: str, period: str, compare_period: str) -> tuple:
    """
    Builds SQL WHERE conditions for target and comparison periods.
    period / compare_period format: 'YYYY-MM'
    """
    # Get year and month from period string
    p_year,  p_mon  = period.split("-")
    c_year,  c_mon  = compare_period.split("-")

    # Build 3-month quarter windows
    p_months = [f"{int(p_mon)+i:02d}" for i in range(3) if int(p_mon)+i <= 12]
    c_months = [f"{int(c_mon)+i:02d}" for i in range(3) if int(c_mon)+i <= 12]

    p_filter = " OR ".join(
        [f"(strftime('%Y', `{date_col}`)='{p_year}' AND strftime('%m', `{date_col}`)='{m}')"
         for m in p_months]
    )
    c_filter = " OR ".join(
        [f"(strftime('%Y', `{date_col}`)='{c_year}' AND strftime('%m', `{date_col}`)='{m}')"
         for m in c_months]
    )
    return p_filter, c_filter


def _investigate(
    db_path:        str,
    table:          str,
    date_col:       str,
    metric_col:     str,
    cat_cols:       List[str],
    period:         str,
    compare_period: str,
    filter_col:     Optional[str] = None,
    filter_val:     Optional[str] = None
) -> dict:
    """Runs diagnostic queries across all category dimensions."""
    engine   = create_engine(f"sqlite:///{db_path}")
    results  = {}
    p_filter, c_filter = _build_period_filter(date_col, period, compare_period)

    base_filter = ""
    if filter_col and filter_val:
        base_filter = f"AND `{filter_col}` = '{filter_val}'"

    # ── Overall comparison ────────────────────────────────────────────────────
    results["overall"] = _run(engine, f"""
        SELECT
            'target'     as period,
            ROUND(SUM(`{metric_col}`), 0) as metric_value,
            COUNT(*)                       as record_count,
            ROUND(AVG(`{metric_col}`), 0)  as avg_value
        FROM `{table}`
        WHERE ({p_filter}) {base_filter}
        UNION ALL
        SELECT
            'comparison' as period,
            ROUND(SUM(`{metric_col}`), 0) as metric_value,
            COUNT(*)                       as record_count,
            ROUND(AVG(`{metric_col}`), 0)  as avg_value
        FROM `{table}`
        WHERE ({c_filter}) {base_filter}
    """)

    # ── Per category breakdown ────────────────────────────────────────────────
    for cat in cat_cols[:4]:
        results[f"by_{cat}"] = _run(engine, f"""
            SELECT
                `{cat}` as dimension,
                ROUND(SUM(CASE WHEN {p_filter} THEN `{metric_col}` ELSE 0 END), 0) as target_val,
                ROUND(SUM(CASE WHEN {c_filter} THEN `{metric_col}` ELSE 0 END), 0) as compare_val,
                COUNT(*) as records
            FROM `{table}`
            WHERE `{cat}` IS NOT NULL
            {base_filter}
            GROUP BY `{cat}`
            ORDER BY compare_val DESC
            LIMIT 10
        """)

    # ── Monthly trend around the period ──────────────────────────────────────
    results["monthly_trend"] = _run(engine, f"""
        SELECT
            strftime('%Y-%m', `{date_col}`) as month,
            ROUND(SUM(`{metric_col}`), 0)   as metric_value,
            COUNT(*)                         as records
        FROM `{table}`
        WHERE `{date_col}` IS NOT NULL
        {base_filter}
        GROUP BY strftime('%Y-%m', `{date_col}`)
        ORDER BY month
        LIMIT 24
    """)

    engine.dispose()
    return results


# ── LLM analysis ──────────────────────────────────────────────────────────────

def _summarise_with_llm(
    question:   str,
    data:       dict,
    table:      str,
    metric_col: str,
    cat_cols:   List[str]
) -> str:
    llm = ChatGroq(
        model       = "llama-3.3-70b-versatile",
        temperature = 0,
        api_key     = os.getenv("GROQ_API_KEY")
    )

    data_text = ""
    for key, df in data.items():
        if isinstance(df, pd.DataFrame) and not df.empty:
            data_text += f"\n\n[{key}]\n{df.to_string(index=False)}"

    prompt = f"""You are a senior data analyst investigating a business question.

Database context:
- Main table: {table}
- Key metric: {metric_col}
- Category dimensions analysed: {', '.join(cat_cols)}

User question: "{question}"

Investigation data:
{data_text}

Write a structured root cause analysis:
1. Executive summary (2-3 sentences with specific numbers)
2. Top 3 root causes with dimension, finding, and impact level (high/medium/low)
3. One actionable recommendation

Be specific with numbers. Reference the actual column and dimension names."""

    try:
        resp = llm.invoke([
            SystemMessage(content="You are a senior data analyst. Be precise and data-driven."),
            HumanMessage(content=prompt)
        ])
        return resp.content
    except Exception as e:
        return f"LLM analysis unavailable: {e}"


# ── Main entry point ──────────────────────────────────────────────────────────

def run_root_cause(
    db_path:        str,
    question:       str,
    region:         str  = None,
    period:         str  = "2024-07",
    compare_period: str  = "2024-04",
    metric:         str  = "auto",
    table:          str  = None,
    date_col:       str  = None,
    metric_col:     str  = None,
    filter_col:     str  = None
) -> dict:

    engine = create_engine(f"sqlite:///{db_path}")

    # ── Auto-discover schema ──────────────────────────────────────────────────
    if not table or not date_col or not metric_col:
        discovered = _discover_rca_schema(engine)
        engine.dispose()

        if not discovered:
            return {
                "error":        "Could not find suitable table for root cause analysis",
                "question":     question,
                "llm_analysis": "No suitable table found. Need a table with date, numeric metric, and category columns.",
                "insights":     [],
                "data_snapshots": {}
            }

        table      = discovered["table"]
        date_col   = discovered["date_col"]
        metric_col = discovered["metric_col"]
        cat_cols   = discovered["cat_cols"]
        filter_col = filter_col or (cat_cols[0] if cat_cols else None)
    else:
        engine.dispose()
        inspector  = inspect(create_engine(f"sqlite:///{db_path}"))
        cols       = [c["name"] for c in inspector.get_columns(table)]
        cat_cols   = [c for c in cols if c not in [date_col, metric_col]][:5]

    metric_label = metric_col.replace("_"," ").title()

    # ── Run investigation ─────────────────────────────────────────────────────
    data = _investigate(
        db_path        = db_path,
        table          = table,
        date_col       = date_col,
        metric_col     = metric_col,
        cat_cols       = cat_cols,
        period         = period,
        compare_period = compare_period,
        filter_col     = filter_col if region else None,
        filter_val     = region
    )

    # ── LLM analysis ──────────────────────────────────────────────────────────
    analysis = _summarise_with_llm(question, data, table, metric_col, cat_cols)

    # ── Build structured insights ─────────────────────────────────────────────
    insights = []
    for cat in cat_cols[:4]:
        key = f"by_{cat}"
        df  = data.get(key, pd.DataFrame())
        if df.empty or "target_val" not in df.columns:
            continue
        df["change"] = df["target_val"] - df["compare_val"]
        if df["change"].abs().max() == 0:
            continue
        worst = df.loc[df["change"].idxmin()]
        drop  = float(worst["compare_val"]) - float(worst["target_val"])
        if drop <= 0:
            continue
        insights.append({
            "dimension": cat.replace("_"," ").title(),
            "finding":   f"{worst['dimension']} dropped by {drop:,.0f} in {metric_label}",
            "severity":  "high" if drop > df["compare_val"].mean() else "medium",
            "data":      df.to_dict(orient="records")
        })

    # ── Serialise snapshots ───────────────────────────────────────────────────
    snapshots = {}
    for k, v in data.items():
        if isinstance(v, pd.DataFrame) and not v.empty:
            snapshots[k] = v.to_dict(orient="records")

    return {
        "question":       question,
        "table":          table,
        "metric_col":     metric_col,
        "cat_cols":       cat_cols,
        "period":         period,
        "compare_period": compare_period,
        "filter_col":     filter_col,
        "region":         region,
        "llm_analysis":   analysis,
        "insights":       insights,
        "data_snapshots": snapshots
    }