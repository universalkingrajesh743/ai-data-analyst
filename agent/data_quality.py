import pandas as pd
import numpy as np
from sqlalchemy import create_engine, inspect, text
from dataclasses import dataclass, field
from typing import List


@dataclass
class ColumnIssue:
    column:      str
    issue_type:  str
    severity:    str    # "critical" | "warning" | "info"
    detail:      str
    suggestion:  str


@dataclass
class TableReport:
    table:       str
    row_count:   int
    issues:      List[ColumnIssue] = field(default_factory=list)
    score:       int = 100          # 0-100 quality score


@dataclass
class QualityReport:
    db_path:     str
    tables:      List[TableReport] = field(default_factory=list)
    overall_score: int = 100
    summary:     str = ""


def _score_deduction(severity: str) -> int:
    return {"critical": 15, "warning": 7, "info": 2}.get(severity, 0)


def analyse_table(engine, table: str) -> TableReport:
    try:
        df = pd.read_sql_query(f"SELECT * FROM `{table}` LIMIT 5000", engine)
    except Exception as e:
        return TableReport(table=table, row_count=0,
                           issues=[ColumnIssue(table, "read_error", "critical",
                                               str(e), "Check table permissions")])

    report = TableReport(table=table, row_count=len(df))

    # ── 1. Duplicate rows ─────────────────────────────────────────────────────
    dup_count = df.duplicated().sum()
    if dup_count > 0:
        pct = round(dup_count / len(df) * 100, 1)
        sev = "critical" if pct > 5 else "warning"
        report.issues.append(ColumnIssue(
            column     = "_all_columns_",
            issue_type = "duplicates",
            severity   = sev,
            detail     = f"{dup_count} duplicate rows ({pct}% of table)",
            suggestion = f"Run: DELETE FROM {table} WHERE rowid NOT IN (SELECT MIN(rowid) FROM {table} GROUP BY {', '.join(df.columns.tolist()[:5])})"
        ))
        report.score -= _score_deduction(sev)

    for col in df.columns:
        series = df[col]

        # ── 2. Missing values ─────────────────────────────────────────────────
        null_count = series.isna().sum()
        if null_count > 0:
            pct = round(null_count / len(df) * 100, 1)
            sev = "critical" if pct > 20 else ("warning" if pct > 5 else "info")
            report.issues.append(ColumnIssue(
                column     = col,
                issue_type = "missing_values",
                severity   = sev,
                detail     = f"{null_count} nulls ({pct}%)",
                suggestion = f"Fill with default or investigate source pipeline for column '{col}'"
            ))
            report.score -= _score_deduction(sev)

        # ── 3. Outliers (numeric columns only) ───────────────────────────────
        if pd.api.types.is_numeric_dtype(series):
            clean = series.dropna()
            if len(clean) > 10:
                q1, q3 = clean.quantile(0.25), clean.quantile(0.75)
                iqr    = q3 - q1
                if iqr > 0:
                    lower  = q1 - 3 * iqr
                    upper  = q3 + 3 * iqr
                    out_ct = ((clean < lower) | (clean > upper)).sum()
                    if out_ct > 0:
                        pct = round(out_ct / len(clean) * 100, 1)
                        sev = "warning" if pct > 1 else "info"
                        report.issues.append(ColumnIssue(
                            column     = col,
                            issue_type = "outliers",
                            severity   = sev,
                            detail     = f"{out_ct} outliers ({pct}%) outside IQR×3 bounds [{lower:.1f}, {upper:.1f}]",
                            suggestion = f"Investigate extreme values in '{col}' — may indicate data entry errors"
                        ))
                        report.score -= _score_deduction(sev)

        # ── 4. Cardinality check (string columns) ─────────────────────────────
        if pd.api.types.is_object_dtype(series):
            n_unique = series.nunique()
            n_total  = series.count()
            if n_total > 50 and n_unique == n_total:
                report.issues.append(ColumnIssue(
                    column     = col,
                    issue_type = "high_cardinality",
                    severity   = "info",
                    detail     = f"All {n_unique} values are unique — likely an ID column",
                    suggestion = f"Consider indexing '{col}' if used in WHERE clauses"
                ))

            # Whitespace / casing issues
            if n_total > 0:
                stripped = series.dropna().str.strip()
                ws_issues = (series.dropna() != stripped).sum()
                if ws_issues > 0:
                    report.issues.append(ColumnIssue(
                        column     = col,
                        issue_type = "whitespace",
                        severity   = "warning",
                        detail     = f"{ws_issues} values have leading/trailing whitespace",
                        suggestion = f"Run: UPDATE {table} SET {col} = TRIM({col})"
                    ))
                    report.score -= _score_deduction("warning")

        # ── 5. Constant columns ───────────────────────────────────────────────
        if series.nunique() == 1 and len(series) > 1:
            report.issues.append(ColumnIssue(
                column     = col,
                issue_type = "constant_column",
                severity   = "info",
                detail     = f"Column has only one unique value: '{series.iloc[0]}'",
                suggestion = f"Column '{col}' may be redundant or misconfigured"
            ))

    report.score = max(0, report.score)
    return report


def run_quality_check(db_path: str, tables: list = None) -> QualityReport:
    engine = create_engine(f"sqlite:///{db_path}")
    insp   = inspect(engine)
    all_tables = tables or insp.get_table_names()

    report = QualityReport(db_path=db_path)

    for table in all_tables:
        table_report = analyse_table(engine, table)
        report.tables.append(table_report)

    engine.dispose()

    # Overall score
    if report.tables:
        report.overall_score = int(
            sum(t.score for t in report.tables) / len(report.tables)
        )

    # Summary
    total_issues  = sum(len(t.issues) for t in report.tables)
    critical      = sum(
        1 for t in report.tables
        for i in t.issues if i.severity == "critical"
    )
    warnings      = sum(
        1 for t in report.tables
        for i in t.issues if i.severity == "warning"
    )

    if total_issues == 0:
        report.summary = "No data quality issues found. Database looks clean."
    else:
        report.summary = (
            f"Found {total_issues} issues across {len(report.tables)} tables "
            f"({critical} critical, {warnings} warnings). "
            f"Overall quality score: {report.overall_score}/100."
        )

    return report


def format_report_for_display(report: QualityReport) -> dict:
    """Converts QualityReport to a dict ready for API/UI."""
    tables_out = []
    for t in report.tables:
        issues_out = [
            {
                "column":      i.column,
                "issue_type":  i.issue_type,
                "severity":    i.severity,
                "detail":      i.detail,
                "suggestion":  i.suggestion
            }
            for i in t.issues
        ]
        tables_out.append({
            "table":     t.table,
            "row_count": t.row_count,
            "score":     t.score,
            "issues":    issues_out
        })

    return {
        "overall_score": report.overall_score,
        "summary":       report.summary,
        "tables":        tables_out
    }