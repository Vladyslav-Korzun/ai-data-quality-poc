from __future__ import annotations

import pandas as pd
from pandasql import sqldf


def run_sql(df: pd.DataFrame, sql: str) -> pd.DataFrame:
    """
    Execute a SELECT SQL query against a pandas DataFrame using pandasql.

    The DataFrame is exposed to the SQL engine under the table name `data`.
    SQL safety and validation are handled upstream.
    """
    env = {"data": df}
    return sqldf(sql, env)
