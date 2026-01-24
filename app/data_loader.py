from __future__ import annotations

import pandas as pd


def load_excel(path: str) -> pd.DataFrame:
    """
    Load an Excel file into a pandas DataFrame.

    Responsibilities:
    - Read the Excel file using a fixed engine for reproducibility
    - Drop fully empty rows
    - Normalize column names by stripping surrounding whitespace

    This function intentionally does NOT perform:
    - Type conversions
    - Locale-specific parsing
    - Data quality checks

    All further processing is handled in downstream steps
    (cleaning, profiling, analysis).
    """
    df = pd.read_excel(path, engine="openpyxl")

    # Drop rows that are completely empty
    df = df.dropna(how="all")

    # Normalize column names (avoid issues in SQL and analysis)
    df.columns = [str(c).strip() for c in df.columns]

    return df
