import pandas as pd
from sqlalchemy import create_engine, inspect, text
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime


@dataclass
class Alert:
    title:      str
    metric:     str
    current:    float
    threshold:  float
    change:     float
    severity:   str
    message:    str
    suggestion: str


@dataclass
class AlertReport:
    alerts:     List[Alert] = field(default_factory=list)
    checked_at: str = ""
    summary:    str = ""
    db_info:    str = ""


# ── Schema discovery ──────────────────────────────────────────────────────────

def _discover_alert_schema(engine) -> List[dict]:
    """
    Discovers all tables suitable for alerting.
    Returns list of {table, date_col, metric_cols, cat_cols, row_count}
    """
    inspector  = inspect(engine)
    tables     = inspector.get_table_names()

    date_kws   = ["date","time","created","updated","timestamp"]
    metric_kws = ["revenue","amount","fee","bill","net","gross","total",
                  "cost","price","salary","sales","income","profit",
                  "quantity","marks","score","rating","orders","count"]
    skip_kws   = ["id","key","code","rank","index","pct","percent",
                  "rate","age","days","hours","minutes","year","month","day"]
    cat_kws    = ["region","city","state","department","dept","branch",
                  "category","channel","type","status","grade","class",
                  "section","sector","specialization","location","zone",
                  "division","product","doctor","subject","cuisine","role"]
    skip_cat   = ["name","email","address","comment","description",
                  "note","url","password","remark","request"]
    numeric_t  = ["INT","REAL","FLOAT","NUMERIC","DECIMAL","DOUBLE","NUMBER"]
    text_t     = ["TEXT","VARCHAR","CHAR","STRING"]

    discovered = []

    for table in tables:
        cols      = inspector.get_columns(table)
        col_names = [c["name"] for c in cols]
        col_types = {c["name"]: str(c["type"]).upper() for c in cols}

        # Find date column
        date_col = None
        for col in col_names:
            if col.lower() in ["year","month","day"]:
                continue
            if any(kw in col.lower() for kw in date_kws):
                try:
                    with engine.connect() as conn:
                        sample = conn.execute(text(
                            f"SELECT `{col}` FROM `{table}` "
                            f"WHERE `{col}` IS NOT NULL LIMIT 1"
                        )).fetchone()
                    if sample:
                        val = str(sample[0])
                        if ("-" in val or "/" in val) and len(val) >= 8:
                            date_col = col
                            break
                except Exception:
                    continue

        if not date_col:
            continue

        # Find metric columns
        metric_cols = []
        for col in col_names:
            col_lower = col.lower()
            col_type  = col_types.get(col,"")
            if not any(nt in col_type for nt in numeric_t):
                continue
            if any(kw in col_lower for kw in skip_kws):
                continue
            if any(kw in col_lower for kw in metric_kws):
                metric_cols.insert(0, col)
            else:
                metric_cols.append(col)

        if not metric_cols:
            continue

        # Find category columns
        cat_cols = []
        for col in col_names:
            col_lower = col.lower()
            col_type  = col_types.get(col,"")
            if col in [date_col] + metric_cols:
                continue
            if any(tt in col_type for tt in text_t):
                if any(kw in col_lower for kw in cat_kws) and \
                   not any(kw in col_lower for kw in skip_cat):
                    cat_cols.append(col)

        # Get row count
        try:
            with engine.connect() as conn:
                count = conn.execute(
                    text(f"SELECT COUNT(*) FROM `{table}`")
                ).fetchone()[0]
            if count < 10:
                continue
        except Exception:
            continue

        discovered.append({
            "table":       table,
            "date_col":    date_col,
            "metric_cols": metric_cols[:3],
            "cat_cols":    cat_cols[:4],
            "row_count":   count
        })

    return discovered


def _run(engine, sql: str) -> pd.DataFrame:
    try:
        return pd.read_sql_query(sql, engine)
    except Exception:
        return pd.DataFrame()


# ── Universal alert checks ────────────────────────────────────────────────────

def _check_metric_drop(
    engine,
    table:      str,
    date_col:   str,
    metric_col: str,
    cat_col:    str,
    threshold:  float
) -> List[Alert]:
    """Checks for drops in a metric grouped by a category column."""
    alerts = []

    df = _run(engine, f"""
        SELECT
            `{cat_col}` as dimension,
            ROUND(SUM(CASE
                WHEN `{date_col}` >= date('now','-30 days')
                THEN `{metric_col}` ELSE 0 END), 0) as recent_val,
            ROUND(SUM(CASE
                WHEN `{date_col}` >= date('now','-60 days')
                AND  `{date_col}` <  date('now','-30 days')
                THEN `{metric_col}` ELSE 0 END), 0) as prev_val
        FROM `{table}`
        WHERE `{cat_col}` IS NOT NULL
        AND   `{metric_col}` IS NOT NULL
        GROUP BY `{cat_col}`
        HAVING prev_val > 0
        ORDER BY prev_val DESC
        LIMIT 20
    """)

    if df.empty:
        return alerts

    metric_label = metric_col.replace("_"," ").title()
    cat_label    = cat_col.replace("_"," ").title()

    for _, row in df.iterrows():
        if row["prev_val"] <= 0:
            continue
        change_pct = (row["recent_val"] - row["prev_val"]) / row["prev_val"] * 100
        if change_pct <= -threshold:
            sev = "critical" if change_pct <= -40 else "warning"
            alerts.append(Alert(
                title      = f"{metric_label} drop — {row['dimension']} ({cat_label})",
                metric     = metric_col,
                current    = float(row["recent_val"]),
                threshold  = threshold,
                change     = round(change_pct, 1),
                severity   = sev,
                message    = (
                    f"{cat_label} '{row['dimension']}': {metric_label} dropped "
                    f"{abs(change_pct):.1f}% "
                    f"({row['recent_val']:,.0f} vs {row['prev_val']:,.0f} previous period)"
                ),
                suggestion = (
                    f"Investigate {cat_label} '{row['dimension']}' — "
                    f"check recent activity in {table} table"
                )
            ))

    return alerts


def _check_low_volume(
    engine,
    table:    str,
    date_col: str,
    cat_col:  str,
    threshold: int = 5
) -> List[Alert]:
    """Checks for low record volume in last 7 days by category."""
    alerts    = []
    cat_label = cat_col.replace("_"," ").title()

    df = _run(engine, f"""
        SELECT
            `{cat_col}` as dimension,
            COUNT(*) as recent_count
        FROM `{table}`
        WHERE `{date_col}` >= date('now','-7 days')
        AND   `{cat_col}` IS NOT NULL
        GROUP BY `{cat_col}`
        ORDER BY recent_count ASC
        LIMIT 10
    """)

    if df.empty:
        return alerts

    for _, row in df.iterrows():
        if row["recent_count"] <= threshold:
            alerts.append(Alert(
                title      = f"Low activity — {row['dimension']} ({cat_label})",
                metric     = "record_count",
                current    = float(row["recent_count"]),
                threshold  = threshold,
                change     = 0,
                severity   = "warning",
                message    = (
                    f"{cat_label} '{row['dimension']}' had only "
                    f"{row['recent_count']} records in the last 7 days"
                ),
                suggestion = (
                    f"Check if activity in '{row['dimension']}' "
                    f"is expected to be low or if there's a data issue"
                )
            ))

    return alerts


def _check_high_value_anomaly(
    engine,
    table:      str,
    date_col:   str,
    metric_col: str,
    cat_col:    str
) -> List[Alert]:
    """Detects unusually high average values (possible data errors)."""
    alerts       = []
    metric_label = metric_col.replace("_"," ").title()
    cat_label    = cat_col.replace("_"," ").title()

    df = _run(engine, f"""
        SELECT
            `{cat_col}` as dimension,
            ROUND(AVG(`{metric_col}`), 2)    as avg_val,
            ROUND(MAX(`{metric_col}`), 2)    as max_val,
            COUNT(*)                          as records
        FROM `{table}`
        WHERE `{date_col}` >= date('now','-30 days')
        AND   `{metric_col}` IS NOT NULL
        AND   `{metric_col}` > 0
        AND   `{cat_col}` IS NOT NULL
        GROUP BY `{cat_col}`
        HAVING records >= 3
        ORDER BY avg_val DESC
        LIMIT 10
    """)

    if df.empty or len(df) < 2:
        return alerts

    overall_avg = df["avg_val"].mean()
    overall_std = df["avg_val"].std()

    for _, row in df.iterrows():
        if overall_std > 0 and row["avg_val"] > overall_avg + 2 * overall_std:
            alerts.append(Alert(
                title      = f"Unusually high {metric_label} — {row['dimension']}",
                metric     = metric_col,
                current    = float(row["avg_val"]),
                threshold  = round(overall_avg + 2 * overall_std, 2),
                change     = 0,
                severity   = "warning",
                message    = (
                    f"{cat_label} '{row['dimension']}' has avg {metric_label} "
                    f"of {row['avg_val']:,.1f} vs overall avg {overall_avg:,.1f} "
                    f"(max: {row['max_val']:,.1f})"
                ),
                suggestion = (
                    f"Verify data accuracy for '{row['dimension']}' — "
                    f"values are significantly above average"
                )
            ))

    return alerts


def _check_null_spike(
    engine,
    table:      str,
    date_col:   str,
    metric_col: str
) -> List[Alert]:
    """Checks if null rate has increased recently."""
    alerts = []

    df = _run(engine, f"""
        SELECT
            'recent'  as period,
            COUNT(*)  as total,
            SUM(CASE WHEN `{metric_col}` IS NULL THEN 1 ELSE 0 END) as nulls
        FROM `{table}`
        WHERE `{date_col}` >= date('now','-30 days')
        UNION ALL
        SELECT
            'previous' as period,
            COUNT(*)   as total,
            SUM(CASE WHEN `{metric_col}` IS NULL THEN 1 ELSE 0 END) as nulls
        FROM `{table}`
        WHERE `{date_col}` >= date('now','-60 days')
        AND   `{date_col}` <  date('now','-30 days')
    """)

    if df.empty or len(df) < 2:
        return alerts

    try:
        recent   = df[df["period"]=="recent"].iloc[0]
        previous = df[df["period"]=="previous"].iloc[0]

        if recent["total"] == 0 or previous["total"] == 0:
            return alerts

        recent_null_pct   = recent["nulls"]   / recent["total"]   * 100
        previous_null_pct = previous["nulls"] / previous["total"] * 100

        if recent_null_pct > 10 and recent_null_pct > previous_null_pct * 1.5:
            alerts.append(Alert(
                title      = f"Null spike in {metric_col.replace('_',' ').title()}",
                metric     = metric_col,
                current    = round(recent_null_pct, 1),
                threshold  = 10.0,
                change     = round(recent_null_pct - previous_null_pct, 1),
                severity   = "critical" if recent_null_pct > 20 else "warning",
                message    = (
                    f"{metric_col} has {recent_null_pct:.1f}% null values "
                    f"in last 30 days vs {previous_null_pct:.1f}% previously"
                ),
                suggestion = "Check data pipeline — source may have stopped sending values"
            ))
    except Exception:
        pass

    return alerts


# ── Main entry point ──────────────────────────────────────────────────────────

def check_alerts(
    db_path:               str,
    revenue_drop_threshold: float = 20.0,
    return_rate_threshold:  float = 10.0,
    discount_threshold:     float = 15.0
) -> AlertReport:

    engine    = create_engine(f"sqlite:///{db_path}")
    report    = AlertReport(checked_at=datetime.now().strftime("%d %b %Y %H:%M"))
    all_alerts = []

    # Auto-discover all suitable tables
    tables_info = _discover_alert_schema(engine)

    if not tables_info:
        engine.dispose()
        report.summary = "No suitable tables found for alerting."
        return report

    report.db_info = f"Monitoring {len(tables_info)} table(s): " + \
                     ", ".join(t["table"] for t in tables_info)

    for info in tables_info:
        table      = info["table"]
        date_col   = info["date_col"]
        metric_cols = info["metric_cols"]
        cat_cols   = info["cat_cols"]

        primary_metric = metric_cols[0] if metric_cols else None

        # Check metric drops per category
        if primary_metric and cat_cols:
            for cat_col in cat_cols[:2]:
                alerts = _check_metric_drop(
                    engine, table, date_col, primary_metric,
                    cat_col, revenue_drop_threshold
                )
                all_alerts.extend(alerts[:3])

        # Check low volume
        if cat_cols:
            alerts = _check_low_volume(engine, table, date_col, cat_cols[0])
            all_alerts.extend(alerts[:2])

        # Check high value anomalies
        if primary_metric and cat_cols:
            alerts = _check_high_value_anomaly(
                engine, table, date_col, primary_metric, cat_cols[0]
            )
            all_alerts.extend(alerts[:2])

        # Check null spikes
        if primary_metric:
            alerts = _check_null_spike(engine, table, date_col, primary_metric)
            all_alerts.extend(alerts)

    engine.dispose()

    # Deduplicate and sort by severity
    seen       = set()
    unique     = []
    sev_order  = {"critical": 0, "warning": 1}
    for a in sorted(all_alerts, key=lambda x: sev_order.get(x.severity, 2)):
        key = (a.title, a.metric)
        if key not in seen:
            seen.add(key)
            unique.append(a)

    report.alerts = unique[:20]   # cap at 20 alerts

    if not report.alerts:
        report.summary = "✅ All metrics within normal range. No alerts triggered."
    else:
        critical = sum(1 for a in report.alerts if a.severity=="critical")
        warnings = sum(1 for a in report.alerts if a.severity=="warning")
        report.summary = (
            f"{len(report.alerts)} alerts across {len(tables_info)} table(s) — "
            f"{critical} critical, {warnings} warnings."
        )

    return report


def format_alert_report(report: AlertReport) -> dict:
    return {
        "checked_at":  report.checked_at,
        "summary":     report.summary,
        "db_info":     report.db_info,
        "alert_count": len(report.alerts),
        "alerts": [
            {
                "title":      a.title,
                "metric":     a.metric,
                "current":    a.current,
                "threshold":  a.threshold,
                "change":     a.change,
                "severity":   a.severity,
                "message":    a.message,
                "suggestion": a.suggestion
            }
            for a in report.alerts
        ]
    }