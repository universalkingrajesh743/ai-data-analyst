import pandas as pd
from sqlalchemy import create_engine, text
from dataclasses import dataclass, field
from typing import List
import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage

load_dotenv(override=True)


@dataclass
class RootCauseInsight:
    dimension:   str
    finding:     str
    impact:      str
    severity:    str    # "high" | "medium" | "low"
    evidence:    str


@dataclass
class RootCauseReport:
    question:    str
    summary:     str
    insights:    List[RootCauseInsight] = field(default_factory=list)
    data_snapshots: dict = field(default_factory=dict)
    recommendation: str = ""


def _run_query(engine, sql: str) -> pd.DataFrame:
    try:
        return pd.read_sql_query(sql, engine)
    except Exception:
        return pd.DataFrame()


def _investigate(db_path: str, metric: str, region: str,
                 period: str, compare_period: str) -> dict:
    """
    Runs multiple diagnostic queries across dimensions:
    region, product, category, channel, sales_rep, returns
    """
    engine  = create_engine(f"sqlite:///{db_path}")
    results = {}

    # ── 1. Overall comparison ─────────────────────────────────────────────────
    results["overall"] = _run_query(engine, f"""
        SELECT
            CASE
                WHEN strftime('%Y-%m', date) BETWEEN '{compare_period}-01' AND '{compare_period}-03'
                THEN 'comparison_period'
                ELSE 'target_period'
            END as period,
            ROUND(SUM(revenue),0)  as revenue,
            COUNT(*)               as orders,
            ROUND(AVG(revenue),0)  as avg_order_value
        FROM sales
        WHERE region = '{region}'
        AND (
            strftime('%Y-%m', date) BETWEEN '{period}-01'     AND '{period}-03'
            OR
            strftime('%Y-%m', date) BETWEEN '{compare_period}-01' AND '{compare_period}-03'
        )
        GROUP BY period
    """)

    # ── 2. Category breakdown ─────────────────────────────────────────────────
    results["by_category"] = _run_query(engine, f"""
        SELECT
            category,
            ROUND(SUM(CASE WHEN strftime('%Y-%m', date) BETWEEN '{period}-01'
                           AND '{period}-03' THEN revenue ELSE 0 END), 0) as target_rev,
            ROUND(SUM(CASE WHEN strftime('%Y-%m', date) BETWEEN '{compare_period}-01'
                           AND '{compare_period}-03' THEN revenue ELSE 0 END), 0) as compare_rev,
            COUNT(*) as orders
        FROM sales
        WHERE region = '{region}'
        GROUP BY category
        ORDER BY compare_rev DESC
        LIMIT 10
    """)

    # ── 3. Channel breakdown ──────────────────────────────────────────────────
    results["by_channel"] = _run_query(engine, f"""
        SELECT
            channel,
            ROUND(SUM(CASE WHEN strftime('%Y-%m', date) BETWEEN '{period}-01'
                           AND '{period}-03' THEN revenue ELSE 0 END), 0) as target_rev,
            ROUND(SUM(CASE WHEN strftime('%Y-%m', date) BETWEEN '{compare_period}-01'
                           AND '{compare_period}-03' THEN revenue ELSE 0 END), 0) as compare_rev
        FROM sales
        WHERE region = '{region}'
        GROUP BY channel
        ORDER BY compare_rev DESC
    """)

    # ── 4. City breakdown ─────────────────────────────────────────────────────
    results["by_city"] = _run_query(engine, f"""
        SELECT
            city,
            ROUND(SUM(CASE WHEN strftime('%Y-%m', date) BETWEEN '{period}-01'
                           AND '{period}-03' THEN revenue ELSE 0 END), 0) as target_rev,
            ROUND(SUM(CASE WHEN strftime('%Y-%m', date) BETWEEN '{compare_period}-01'
                           AND '{compare_period}-03' THEN revenue ELSE 0 END), 0) as compare_rev
        FROM sales
        WHERE region = '{region}'
        GROUP BY city
        ORDER BY compare_rev DESC
    """)

    # ── 5. Returns spike ──────────────────────────────────────────────────────
    results["returns"] = _run_query(engine, f"""
        SELECT
            COUNT(*)                as return_count,
            ROUND(SUM(refund_amount),0) as total_refunds,
            reason,
            COUNT(*) * 100.0 / (
                SELECT COUNT(*) FROM returns WHERE region='{region}'
            ) as pct
        FROM returns
        WHERE region = '{region}'
        GROUP BY reason
        ORDER BY return_count DESC
        LIMIT 5
    """)

    # ── 6. Discount pattern ───────────────────────────────────────────────────
    results["discounts"] = _run_query(engine, f"""
        SELECT
            ROUND(AVG(discount_pct),1) as avg_discount,
            ROUND(MIN(revenue),0)      as min_revenue,
            ROUND(MAX(revenue),0)      as max_revenue,
            COUNT(*)                   as orders
        FROM sales
        WHERE region='{region}'
        AND strftime('%Y-%m', date) BETWEEN '{period}-01' AND '{period}-03'
    """)

    engine.dispose()
    return results


def _summarise_with_llm(question: str, data: dict) -> str:
    """Sends investigation data to Groq LLM for natural language summary."""
    llm = ChatGroq(
        model    = "llama-3.3-70b-versatile",
        temperature = 0,
        api_key  = os.getenv("GROQ_API_KEY")
    )

    # Format data snapshots as text
    data_text = ""
    for key, df in data.items():
        if isinstance(df, pd.DataFrame) and not df.empty:
            data_text += f"\n\n[{key}]\n{df.to_string(index=False)}"

    prompt = f"""You are a senior data analyst. A business user asked:
"{question}"

Here is the investigative data across multiple dimensions:
{data_text}

Write a structured root cause analysis with:
1. ONE paragraph executive summary (2-3 sentences)
2. Top 3 root causes, each with:
   - Dimension (category/channel/city/returns/discount)
   - Finding (what the data shows)
   - Business impact (high/medium/low)
3. One actionable recommendation

Be specific with numbers from the data. Be concise. No fluff."""

    try:
        resp = llm.invoke([
            SystemMessage(content="You are a senior data analyst. Be precise and data-driven."),
            HumanMessage(content=prompt)
        ])
        return resp.content
    except Exception as e:
        return f"LLM analysis unavailable: {e}"


def run_root_cause(
    db_path:        str,
    question:       str,
    region:         str  = "Odisha",
    period:         str  = "2024-07",
    compare_period: str  = "2024-04",
    metric:         str  = "revenue"
) -> dict:
    """
    Main entry point.
    period and compare_period are 'YYYY-MM' strings (start of quarter).
    """
    data     = _investigate(db_path, metric, region, period, compare_period)
    analysis = _summarise_with_llm(question, data)

    # Build structured insights from data
    insights = []

    # Category insight
    cat_df = data.get("by_category", pd.DataFrame())
    if not cat_df.empty:
        cat_df["change"] = cat_df["target_rev"] - cat_df["compare_rev"]
        worst = cat_df.loc[cat_df["change"].idxmin()] if not cat_df.empty else None
        if worst is not None:
            drop = worst["compare_rev"] - worst["target_rev"]
            insights.append({
                "dimension": "Product Category",
                "finding":   f"{worst['category']} dropped by ₹{drop:,.0f}",
                "severity":  "high" if drop > 100000 else "medium",
                "data":      cat_df.to_dict(orient="records")
            })

    # Channel insight
    ch_df = data.get("by_channel", pd.DataFrame())
    if not ch_df.empty:
        ch_df["change"] = ch_df["target_rev"] - ch_df["compare_rev"]
        worst_ch = ch_df.loc[ch_df["change"].idxmin()] if not ch_df.empty else None
        if worst_ch is not None:
            drop = worst_ch["compare_rev"] - worst_ch["target_rev"]
            insights.append({
                "dimension": "Sales Channel",
                "finding":   f"{worst_ch['channel']} channel dropped by ₹{drop:,.0f}",
                "severity":  "high" if drop > 50000 else "medium",
                "data":      ch_df.to_dict(orient="records")
            })

    # Returns insight
    ret_df = data.get("returns", pd.DataFrame())
    if not ret_df.empty:
        top_reason = ret_df.iloc[0]
        insights.append({
            "dimension": "Product Returns",
            "finding":   f"Top return reason: '{top_reason['reason']}' ({top_reason['return_count']} returns)",
            "severity":  "medium",
            "data":      ret_df.to_dict(orient="records")
        })

    # Serialise dataframes for API
    snapshots = {}
    for k, v in data.items():
        if isinstance(v, pd.DataFrame) and not v.empty:
            snapshots[k] = v.to_dict(orient="records")

    return {
        "question":       question,
        "region":         region,
        "period":         period,
        "compare_period": compare_period,
        "llm_analysis":   analysis,
        "insights":       insights,
        "data_snapshots": snapshots
    }