from __future__ import annotations

import pandas as pd


def profile_dataframe(df: pd.DataFrame) -> dict:
    """
    Build a lightweight dataset profile used for CLI display and LLM context.

    The profile intentionally stays simple and fast:
    - row/column counts
    - column dtypes
    - missing (NULL) percentage per column
    - top columns by missingness
    - lists of numeric and datetime columns
    """
    total_rows = int(len(df))
    cols = list(df.columns)

    null_pct: dict[str, float] = {}
    dtypes: dict[str, str] = {}

    for c in cols:
        dtypes[c] = str(df[c].dtype)
        null_pct[c] = float(df[c].isna().mean()) if total_rows else 0.0

    top_missing = sorted(null_pct.items(), key=lambda x: x[1], reverse=True)[:10]

    numeric_cols = [c for c in cols if pd.api.types.is_numeric_dtype(df[c])]
    datetime_cols = [c for c in cols if pd.api.types.is_datetime64_any_dtype(df[c])]

    return {
        "rows": total_rows,
        "cols": int(df.shape[1]),
        "columns": cols,
        "dtypes": dtypes,
        "null_pct": null_pct,
        "top_missing": top_missing,
        "numeric_cols": numeric_cols,
        "datetime_cols": datetime_cols,
    }


def schema_text(profile: dict) -> str:
    """
    Convert a dataset profile into a compact, human-readable schema summary.

    This text is displayed in the CLI and also used as context for the LLM,
    so it should be stable and easy to parse by both humans and models.
    """
    lines: list[str] = []
    lines.append(f"Rows: {profile['rows']}, Columns: {profile['cols']}\n")

    lines.append("Columns (name | dtype | null%):")
    for c in profile["columns"]:
        null_percent = round(profile["null_pct"][c] * 100, 2)
        lines.append(f"- {c} | {profile['dtypes'][c]} | {null_percent}%")

    lines.append("\nTop 10 columns by missing %:")
    for name, pct in profile["top_missing"]:
        lines.append(f"- {name}: {round(pct * 100, 2)}%")

    lines.append("\nNumeric columns:")
    lines.append(", ".join(profile["numeric_cols"]) if profile["numeric_cols"] else "(none)")

    lines.append("\nDatetime columns:")
    lines.append(", ".join(profile["datetime_cols"]) if profile["datetime_cols"] else "(none)")

    return "\n".join(lines)
