import re
from dataclasses import dataclass


@dataclass
class ValidationResult:
    is_safe:  bool
    risk:     str   # "safe" | "warning" | "blocked"
    message:  str
    suggestion: str = ""


# Patterns that are always blocked
BLOCKED_PATTERNS = [
    (r"\bDROP\b",        "DROP statement detected — would delete tables or databases"),
    (r"\bDELETE\b",      "DELETE statement detected — would remove data"),
    (r"\bTRUNCATE\b",    "TRUNCATE statement detected — would empty entire table"),
    (r"\bINSERT\b",      "INSERT statement detected — read-only mode enforced"),
    (r"\bUPDATE\b",      "UPDATE statement detected — read-only mode enforced"),
    (r"\bALTER\b",       "ALTER statement detected — schema changes not allowed"),
    (r"\bCREATE\b",      "CREATE statement detected — schema changes not allowed"),
    (r"\bGRANT\b",       "GRANT statement detected — permission changes not allowed"),
    (r"\bATTACH\b",      "ATTACH DATABASE detected — not allowed"),
    (r";\s*\w",          "Multiple SQL statements detected — possible injection attempt"),
]

# Patterns that are warnings (allowed but flagged)
WARNING_PATTERNS = [
    (r"SELECT\s+\*\s+FROM\s+\w+\s*$",
     "SELECT * without WHERE or LIMIT — may scan entire table",
     "Consider adding WHERE conditions or LIMIT to narrow results"),
    (r"SELECT\s+\*\s+FROM\s+\w+\s+WHERE",
     "SELECT * used — consider selecting only needed columns",
     "Replace SELECT * with specific column names for better performance"),
    (r"\bLIKE\s+'%[^%]",
     "Leading wildcard in LIKE — cannot use index",
     "Leading % in LIKE prevents index usage, may be slow on large tables"),
]


def validate_sql(sql: str) -> ValidationResult:
    """
    Validates SQL before execution.
    Returns ValidationResult with is_safe, risk level, message.
    """
    if not sql or not sql.strip():
        return ValidationResult(
            is_safe    = False,
            risk       = "blocked",
            message    = "Empty SQL query",
            suggestion = "Please ask a question so the AI can generate a query"
        )

    sql_upper = sql.upper().strip()

    # Must start with SELECT (or WITH for CTEs)
    if not re.match(r"^\s*(SELECT|WITH)\b", sql_upper):
        return ValidationResult(
            is_safe    = False,
            risk       = "blocked",
            message    = f"Query must start with SELECT or WITH. Got: {sql_upper[:30]}",
            suggestion = "Only read-only SELECT queries are permitted"
        )

    # Check blocked patterns
    for pattern, message in BLOCKED_PATTERNS:
        if re.search(pattern, sql_upper):
            return ValidationResult(
                is_safe    = False,
                risk       = "blocked",
                message    = message,
                suggestion = "This operation is not permitted in read-only analytics mode"
            )

    # Check warning patterns
    for item in WARNING_PATTERNS:
        pattern, message, suggestion = item
        if re.search(pattern, sql_upper):
            return ValidationResult(
                is_safe    = True,
                risk       = "warning",
                message    = message,
                suggestion = suggestion
            )

    # Check for LIMIT (soft warning if missing)
    if "LIMIT" not in sql_upper:
        return ValidationResult(
            is_safe    = True,
            risk       = "warning",
            message    = "No LIMIT clause found — query may return many rows",
            suggestion = "Consider adding LIMIT 500 to avoid large result sets"
        )

    return ValidationResult(
        is_safe    = True,
        risk       = "safe",
        message    = "Query passed all safety checks",
        suggestion = ""
    )


def get_risk_badge(risk: str) -> str:
    """Returns a text badge for display in UI."""
    badges = {
        "safe":    "✅ Safe",
        "warning": "⚠️ Warning",
        "blocked": "🚫 Blocked"
    }
    return badges.get(risk, "❓ Unknown")