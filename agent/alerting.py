import pandas as pd
from sqlalchemy import create_engine
from dataclasses import dataclass, field
from typing import List
from datetime import datetime


@dataclass
class Alert:
    title:     str
    metric:    str
    current:   float
    threshold: float
    change:    float
    severity:  str      # "critical" | "warning"
    message:   str
    suggestion: str


@dataclass
class AlertReport:
    alerts:    List[Alert] = field(default_factory=list)
    checked_at: str = ""
    summary:    str = ""


def _run(engine, sql):
    try:
        return pd.read_sql_query(sql, engine)
    except Exception:
        return pd.DataFrame()


def check_alerts(
    db_path: str,
    revenue_drop_threshold:  float = 20.0,
    return_rate_threshold:   float = 10.0,
    discount_threshold:      float = 15.0,
    low_orders_threshold:    int   = 5
) -> AlertReport:
    """
    Checks key business metrics and raises alerts when thresholds are breached.
    Compares last 30 days vs previous 30 days.
    """
    engine = create_engine(f"sqlite:///{db_path}")
    report = AlertReport(checked_at=datetime.now().strftime("%d %b %Y %H:%M"))
    alerts = []

    # ── 1. Revenue drop by region ─────────────────────────────────────────────
    rev_df = _run(engine, """
        SELECT
            region,
            ROUND(SUM(CASE WHEN date >= date('now','-30 days')
                           THEN revenue ELSE 0 END),0) as recent_rev,
            ROUND(SUM(CASE WHEN date >= date('now','-60 days')
                           AND date < date('now','-30 days')
                           THEN revenue ELSE 0 END),0) as prev_rev
        FROM sales
        GROUP BY region
        HAVING prev_rev > 0
    """)

    if not rev_df.empty:
        for _, row in rev_df.iterrows():
            if row["prev_rev"] > 0:
                change_pct = (row["recent_rev"] - row["prev_rev"]) / row["prev_rev"] * 100
                if change_pct <= -revenue_drop_threshold:
                    sev = "critical" if change_pct <= -40 else "warning"
                    alerts.append(Alert(
                        title      = f"Revenue drop in {row['region']}",
                        metric     = "revenue",
                        current    = float(row["recent_rev"]),
                        threshold  = revenue_drop_threshold,
                        change     = round(change_pct, 1),
                        severity   = sev,
                        message    = (f"{row['region']} revenue dropped {abs(change_pct):.1f}% "
                                      f"(₹{row['recent_rev']:,.0f} vs ₹{row['prev_rev']:,.0f} previous period)"),
                        suggestion = f"Investigate sales in {row['region']} — check channel, product, and rep performance"
                    ))

    # ── 2. High return rate ───────────────────────────────────────────────────
    ret_df = _run(engine, """
        SELECT
            r.region,
            COUNT(r.id) as returns,
            COUNT(s.id) as sales,
            ROUND(COUNT(r.id) * 100.0 / COUNT(s.id), 1) as return_rate
        FROM sales s
        LEFT JOIN returns r ON s.id = r.sale_id
        GROUP BY r.region
        HAVING return_rate > 0
        ORDER BY return_rate DESC
    """)

    if not ret_df.empty:
        for _, row in ret_df.iterrows():
            if row["return_rate"] and row["return_rate"] >= return_rate_threshold:
                sev = "critical" if row["return_rate"] >= 20 else "warning"
                alerts.append(Alert(
                    title      = f"High return rate in {row['region']}",
                    metric     = "return_rate",
                    current    = float(row["return_rate"]),
                    threshold  = return_rate_threshold,
                    change     = 0,
                    severity   = sev,
                    message    = (f"{row['region']} return rate is {row['return_rate']}% "
                                  f"({row['returns']} returns out of {row['sales']} sales)"),
                    suggestion = "Review product quality, delivery issues, or misleading listings"
                ))

    # ── 3. Excessive discounting ──────────────────────────────────────────────
    disc_df = _run(engine, """
        SELECT
            category,
            ROUND(AVG(discount_pct),1) as avg_discount,
            COUNT(*) as orders
        FROM sales
        WHERE date >= date('now','-30 days')
        GROUP BY category
        HAVING avg_discount >= ?
        ORDER BY avg_discount DESC
    """.replace("?", str(discount_threshold)))

    if not disc_df.empty:
        for _, row in disc_df.iterrows():
            alerts.append(Alert(
                title      = f"High discounting in {row['category']}",
                metric     = "discount",
                current    = float(row["avg_discount"]),
                threshold  = discount_threshold,
                change     = 0,
                severity   = "warning",
                message    = (f"{row['category']} avg discount is {row['avg_discount']}% "
                              f"over last 30 days ({row['orders']} orders)"),
                suggestion = "Review discount policy — high discounts may erode margins"
            ))

    # ── 4. Low order volume by region ─────────────────────────────────────────
    orders_df = _run(engine, """
        SELECT
            region,
            COUNT(*) as recent_orders
        FROM sales
        WHERE date >= date('now','-7 days')
        GROUP BY region
        ORDER BY recent_orders ASC
    """)

    if not orders_df.empty:
        for _, row in orders_df.iterrows():
            if row["recent_orders"] <= low_orders_threshold:
                alerts.append(Alert(
                    title      = f"Very low orders in {row['region']}",
                    metric     = "orders",
                    current    = float(row["recent_orders"]),
                    threshold  = low_orders_threshold,
                    change     = 0,
                    severity   = "warning",
                    message    = (f"{row['region']} had only {row['recent_orders']} "
                                  f"orders in the last 7 days"),
                    suggestion = "Check if sales team is active and pipeline is healthy"
                ))

    engine.dispose()

    report.alerts = alerts

    if not alerts:
        report.summary = "All metrics within thresholds. No alerts triggered."
    else:
        critical = sum(1 for a in alerts if a.severity == "critical")
        warnings = sum(1 for a in alerts if a.severity == "warning")
        report.summary = (
            f"{len(alerts)} alerts triggered — "
            f"{critical} critical, {warnings} warnings."
        )

    return report


def format_alert_report(report: AlertReport) -> dict:
    return {
        "checked_at": report.checked_at,
        "summary":    report.summary,
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