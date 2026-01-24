from __future__ import annotations

import pandas as pd
import numpy as np


TRUE_SET = {"true", "t", "yes", "y", "1", "x"}
FALSE_SET = {"false", "f", "no", "n", "0", ""}


def _to_bool_series(s: pd.Series) -> pd.Series:
    """
    Convert a pandas Series to a nullable boolean dtype.

    Supports mixed representations such as:
    - true/false
    - yes/no
    - x / empty
    """
    def conv(v):
        if pd.isna(v):
            return pd.NA
        if isinstance(v, (bool, np.bool_)):
            return bool(v)
        txt = str(v).strip().lower()
        if txt in TRUE_SET:
            return True
        if txt in FALSE_SET:
            return False
        return pd.NA

    return s.map(conv).astype("boolean")


def _normalize_number_text(v: str) -> str:
    """
    Normalize numeric strings with mixed locale formats.

    Rules:
    - If both ',' and '.' exist -> ',' is thousands separator, '.' is decimal
      Example: "342,954.98" -> "342954.98"
    - If only ',' exists:
        - If it looks like thousands grouping -> remove comma
          Example: "370,374" -> "370374"
        - Otherwise treat comma as decimal separator
          Example: "1234,56" -> "1234.56"
    - Spaces are removed
    """
    x = (v or "").strip()
    if x == "":
        return ""

    x = x.replace(" ", "")
    has_comma = "," in x
    has_dot = "." in x

    if has_comma and has_dot:
        return x.replace(",", "")

    if has_comma and not has_dot:
        parts = x.split(",")
        if len(parts) == 2:
            left, right = parts
            if right.isdigit() and len(right) == 3 and left.replace("-", "").isdigit():
                return left + right
        return x.replace(",", ".")

    return x


def _to_numeric_mixed(s: pd.Series) -> pd.Series:
    """
    Convert a Series containing mixed-locale numeric values to float.
    """
    if s.dtype.kind in "if":
        return s

    s2 = s.astype("string")
    s2 = s2.map(lambda v: _normalize_number_text(str(v)) if v is not pd.NA else "")
    s2 = s2.replace({"": np.nan, "None": np.nan, "nan": np.nan})
    s2 = s2.astype(str).str.replace(r"[^0-9\.\-\+]", "", regex=True)

    return pd.to_numeric(s2, errors="coerce")


def _to_datetime_fast(s: pd.Series) -> pd.Series:
    """
    Convert a Series to datetime using pandas inference.

    Invalid or unparseable values are coerced to NaT.
    """
    return pd.to_datetime(s, errors="coerce")


def _to_selected_bool(s: pd.Series) -> pd.Series:
    """
    Convert 'Selected' / 'Not Selected' style values to nullable boolean.
    """
    s2 = s.astype("string").fillna("").str.strip().str.lower()

    def conv(x: str):
        if x == "":
            return pd.NA
        if x == "selected":
            return True
        if x == "not selected":
            return False
        if "selected" in x and "not" not in x:
            return True
        if "selected" in x and "not" in x:
            return False
        return pd.NA

    return s2.map(conv).astype("boolean")


def clean_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Clean and normalize a raw DataFrame for analysis and SQL querying.

    Returns:
    - cleaned DataFrame
    - conversion report describing applied transformations
    """
    cleaned = df.copy()
    report: dict = {"conversions": {}}

    cleaned.columns = [str(c).strip() for c in cleaned.columns]

    if "Unnamed: 0" in cleaned.columns:
        cleaned = cleaned.drop(columns=["Unnamed: 0"])
        report["conversions"]["Unnamed: 0"] = {"action": "dropped_excel_index"}

    if "Transaction Value" in cleaned.columns:
        before_na = int(cleaned["Transaction Value"].isna().sum())
        cleaned["Transaction Value"] = _to_numeric_mixed(cleaned["Transaction Value"])
        after_na = int(cleaned["Transaction Value"].isna().sum())
        report["conversions"]["Transaction Value"] = {
            "type": "numeric_mixed_locale",
            "na_before": before_na,
            "na_after": after_na,
        }

    if "Exchange rate" in cleaned.columns:
        cleaned["Exchange rate"] = _to_numeric_mixed(cleaned["Exchange rate"])
        report["conversions"]["Exchange rate"] = {"type": "numeric_mixed_locale"}

    for col in ["Cleared Item", "Clearing Date", "Clearing Entry Date"]:
        if col in cleaned.columns:
            cleaned[col] = _to_datetime_fast(cleaned[col])
            report["conversions"][col] = {"type": "datetime"}

    if "Calculate Tax" in cleaned.columns:
        cleaned["Calculate Tax"] = _to_bool_series(cleaned["Calculate Tax"])
        report["conversions"]["Calculate Tax"] = {"type": "boolean"}

    if "Document Is Back-Posted" in cleaned.columns:
        cleaned["Document Is Back-Posted"] = _to_bool_series(cleaned["Document Is Back-Posted"])
        report["conversions"]["Document Is Back-Posted"] = {"type": "boolean"}

    if "Cash Flow-Relevant Doc." in cleaned.columns:
        cleaned["Cash Flow-Relevant Doc."] = _to_selected_bool(cleaned["Cash Flow-Relevant Doc."])
        report["conversions"]["Cash Flow-Relevant Doc."] = {"type": "boolean_selected"}

    for col in ["Currency", "Country Key", "Debit/Credit ind", "Bus. Transac. Type"]:
        if col in cleaned.columns:
            cleaned[col] = cleaned[col].astype("string").str.strip()

    int_cols = [
        "Clearing Fiscal Year",
        "Fiscal Year.1",
        "Fiscal Year.2",
        "Posting period.1",
        "Ref. Doc. Line Item",
    ]
    for col in int_cols:
        if col in cleaned.columns:
            cleaned[col] = _to_numeric_mixed(cleaned[col]).astype("Int64")
            report["conversions"][col] = {"type": "Int64"}

    return cleaned, report
