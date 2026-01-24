from __future__ import annotations

import pandas as pd


def iqr_outliers(df: pd.DataFrame, column: str, k: float = 1.5) -> dict:
    if column not in df.columns:
        return {"error": f"Column not found: {column}"}

    s = df[column]
    s = s.dropna()
    if s.empty:
        return {"error": f"No numeric values in column: {column}"}

    if not pd.api.types.is_numeric_dtype(s):
        return {"error": f"Column is not numeric: {column} ({df[column].dtype})"}

    q1 = s.quantile(0.25)
    q3 = s.quantile(0.75)
    iqr = q3 - q1
    lower = q1 - k * iqr
    upper = q3 + k * iqr

    out = df[(df[column] < lower) | (df[column] > upper)].copy()
    return {
        "column": column,
        "k": k,
        "q1": float(q1),
        "q3": float(q3),
        "iqr": float(iqr),
        "lower": float(lower),
        "upper": float(upper),
        "outliers_count": int(len(out)),
        "outliers_df": out,
    }
