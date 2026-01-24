from __future__ import annotations

import re

DISALLOWED = re.compile(
    r"\b(insert|update|delete|drop|alter|create|attach|pragma)\b",
    re.IGNORECASE
)


def is_safe_sql(sql: str) -> tuple[bool, str]:
    """
    Validate that a SQL query is safe to execute.

    Safety rules:
    - Query must not be empty
    - Only SELECT statements are allowed
    - Semicolons are forbidden (no stacked queries)
    - DDL/DML keywords are explicitly blocked
    """
    s = (sql or "").strip()

    if not s:
        return False, "Empty SQL."
    if ";" in s:
        return False, "Semicolons are not allowed."
    if not re.match(r"^\s*select\b", s, re.IGNORECASE):
        return False, "Only SELECT queries are allowed."
    if DISALLOWED.search(s):
        return False, "Query contains disallowed keywords."

    return True, "OK"


def enforce_limit(sql: str, limit: int = 50) -> str:
    """
    Ensure a SELECT query has a LIMIT clause.

    If LIMIT is already present, the query is returned unchanged.
    Otherwise, a LIMIT is appended to keep CLI output manageable.
    """
    if re.search(r"\blimit\b", sql, re.IGNORECASE):
        return sql
    return sql.rstrip() + f" LIMIT {limit}"
