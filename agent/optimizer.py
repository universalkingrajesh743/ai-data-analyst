import re
import pandas as pd
from sqlalchemy import create_engine, inspect, text
from dataclasses import dataclass, field
from typing import List


@dataclass
class OptimizationSuggestion:
    category:   str
    severity:   str     # "critical" | "warning" | "info"
    issue:      str
    suggestion: str
    example:    str = ""


@dataclass
class OptimizationReport:
    sql:         str
    suggestions: List[OptimizationSuggestion] = field(default_factory=list)
    score:       int = 100
    summary:     str = ""


def _get_table_stats(engine, table: str) -> dict:
    """Get row count and column info for a table."""
    try:
        with engine.connect() as conn:
            count = conn.execute(text(f"SELECT COUNT(*) FROM `{table}`")).fetchone()[0]
        inspector = inspect(engine)
        cols      = inspector.get_columns(table)
        return {"row_count": count, "columns": [c["name"] for c in cols]}
    except Exception:
        return {"row_count": 0, "columns": []}


def analyse_query(sql: str, db_path: str = "sample_data/sales.db") -> OptimizationReport:
    """
    Analyses a SQL query and returns optimization suggestions.
    """
    report  = OptimizationReport(sql=sql)
    sql_up  = sql.upper().strip()
    engine  = create_engine(f"sqlite:///{db_path}")

    # ── 1. SELECT * check ─────────────────────────────────────────────────────
    if re.search(r"SELECT\s+\*", sql_up):
        report.suggestions.append(OptimizationSuggestion(
            category   = "Column selection",
            severity   = "warning",
            issue      = "SELECT * retrieves all columns including unused ones",
            suggestion = "Specify only the columns you need",
            example    = "SELECT region, SUM(revenue) instead of SELECT *"
        ))
        report.score -= 10

    # ── 2. Missing LIMIT ──────────────────────────────────────────────────────
    if "LIMIT" not in sql_up:
        report.suggestions.append(OptimizationSuggestion(
            category   = "Result size",
            severity   = "warning",
            issue      = "No LIMIT clause — query may return millions of rows",
            suggestion = "Add LIMIT to cap result size",
            example    = "Add LIMIT 500 at the end of your query"
        ))
        report.score -= 10

    # ── 3. Leading wildcard LIKE ──────────────────────────────────────────────
    if re.search(r"LIKE\s+'%[^%']+[^%]'", sql_up):
        report.suggestions.append(OptimizationSuggestion(
            category   = "Index usage",
            severity   = "critical",
            issue      = "Leading wildcard in LIKE prevents index usage",
            suggestion = "Avoid leading % in LIKE patterns",
            example    = "Use LIKE 'Odisha%' instead of LIKE '%Odisha'"
        ))
        report.score -= 20

    # ── 4. Functions on indexed columns ───────────────────────────────────────
    if re.search(r"WHERE.*(?:UPPER|LOWER|TRIM|LENGTH)\s*\(", sql_up):
        report.suggestions.append(OptimizationSuggestion(
            category   = "Index usage",
            severity   = "warning",
            issue      = "Function applied to column in WHERE clause disables index",
            suggestion = "Store pre-transformed data or use computed columns",
            example    = "Store region in lowercase at insert time"
        ))
        report.score -= 10

    # ── 5. Missing WHERE on large tables ─────────────────────────────────────
    tables_in_query = re.findall(r"FROM\s+`?(\w+)`?", sql_up)
    tables_in_query += re.findall(r"JOIN\s+`?(\w+)`?", sql_up)

    for tbl in set(tables_in_query):
        tbl_lower = tbl.lower()
        try:
            stats = _get_table_stats(engine, tbl_lower)
            if stats["row_count"] > 10000 and "WHERE" not in sql_up:
                report.suggestions.append(OptimizationSuggestion(
                    category   = "Full table scan",
                    severity   = "critical",
                    issue      = f"Table '{tbl_lower}' has {stats['row_count']:,} rows but no WHERE clause",
                    suggestion = "Add WHERE conditions to filter rows early",
                    example    = f"Add WHERE region = 'Odisha' to narrow the scan"
                ))
                report.score -= 20
        except Exception:
            pass

    # ── 6. Cartesian join (no ON clause) ─────────────────────────────────────
    if re.search(r"JOIN\s+\w+\s+(?!ON|USING)", sql_up):
        report.suggestions.append(OptimizationSuggestion(
            category   = "Join safety",
            severity   = "critical",
            issue      = "JOIN without ON/USING clause creates a cartesian product",
            suggestion = "Always specify join conditions with ON or USING",
            example    = "JOIN customers ON sales.customer_id = customers.id"
        ))
        report.score -= 25

    # ── 7. OR in WHERE (index killer) ────────────────────────────────────────
    if re.search(r"WHERE.*\bOR\b", sql_up):
        report.suggestions.append(OptimizationSuggestion(
            category   = "Index usage",
            severity   = "info",
            issue      = "OR conditions in WHERE may prevent index usage",
            suggestion = "Consider rewriting with UNION ALL or IN()",
            example    = "WHERE region IN ('Odisha','Delhi') instead of region='Odisha' OR region='Delhi'"
        ))
        report.score -= 5

    # ── 8. Subquery vs JOIN ───────────────────────────────────────────────────
    if sql_up.count("SELECT") > 1:
        report.suggestions.append(OptimizationSuggestion(
            category   = "Subquery",
            severity   = "info",
            issue      = "Nested subquery detected — may be rewritable as a JOIN",
            suggestion = "JOINs are often faster than correlated subqueries",
            example    = "Use WITH (CTE) to make subqueries readable and optimizable"
        ))
        report.score -= 5

    # ── Index recommendations ──────────────────────────────────────────────────
    index_cols = re.findall(r"WHERE.*?(\w+)\s*=", sql_up)
    index_cols += re.findall(r"GROUP BY\s+([\w,\s]+)", sql_up)
    index_cols  = list({c.strip().lower() for c in index_cols if len(c.strip()) > 2})

    if index_cols:
        report.suggestions.append(OptimizationSuggestion(
            category   = "Index recommendation",
            severity   = "info",
            issue      = f"Columns used in WHERE/GROUP BY: {', '.join(index_cols[:4])}",
            suggestion = "Consider adding indexes on frequently filtered columns",
            example    = f"CREATE INDEX idx_{index_cols[0]} ON sales({index_cols[0]})"
        ))

    engine.dispose()

    report.score = max(0, report.score)

    if not report.suggestions:
        report.summary = "Query looks well-optimized. No major issues found."
    else:
        critical = sum(1 for s in report.suggestions if s.severity == "critical")
        warnings = sum(1 for s in report.suggestions if s.severity == "warning")
        report.summary = (
            f"{len(report.suggestions)} suggestions found "
            f"({critical} critical, {warnings} warnings). "
            f"Optimization score: {report.score}/100."
        )

    return report


def format_optimizer_report(report: OptimizationReport) -> dict:
    return {
        "score":       report.score,
        "summary":     report.summary,
        "suggestions": [
            {
                "category":   s.category,
                "severity":   s.severity,
                "issue":      s.issue,
                "suggestion": s.suggestion,
                "example":    s.example
            }
            for s in report.suggestions
        ]
    }