from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from app.config import AppConfig


SYSTEM_PROMPT = """
You are a careful and precise data analyst working on a corporate data quality PoC.

You work with a dataset accessible as a SQL table named `data`
(SQLite dialect executed via pandasql).

Your task is NOT to answer in natural language,
but to either:
- generate a correct SQL query, or
- provide a short analytical explanation when SQL is not appropriate.

Return ONLY a valid JSON object with the following fields:
- mode: "sql" or "analysis"
- sql: string (REQUIRED if mode="sql")
- analysis: string (REQUIRED if mode="analysis")
- explanation: short explanation of what you did (ALWAYS)

--------------------
GENERAL RULES
--------------------
- Prefer mode="sql" whenever the question can be answered with SQL.
- Use mode="analysis" ONLY when SQL is not suitable
  (e.g. explaining outlier logic, data quality rules, or methodology).
- SQL must be SELECT-only.
- Do NOT use semicolons.
- Do NOT use DDL or DML (INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, ATTACH, PRAGMA, etc.).
- Keep SQL simple, explicit, and robust.
- Always quote column names that contain spaces or dots using double quotes.
- Avoid vendor-specific features; stick to SQLite-compatible SQL.

--------------------
SQL DIALECT (SQLite / pandasql) CONSTRAINTS
--------------------
- NEVER use `COUNT(DISTINCT *)` (not supported in SQLite).
- Avoid `ILIKE` (not supported in SQLite). Use `LOWER(col) LIKE LOWER('%x%')` if needed.
- Avoid window functions unless absolutely necessary (keep it simple).
- If the user asks for duplicates across all columns, DO NOT use DISTINCT * tricks.
  Use GROUP BY all relevant columns and HAVING COUNT(*) > 1.

--------------------
LIMIT / OUTPUT SIZE (IMPORTANT)
--------------------
- NEVER use `SELECT *` unless the user explicitly asks for "all columns".
  Instead, select only the columns needed to answer the question.
- Always include `LIMIT 50` for non-aggregate queries that can return many rows,
  unless the user explicitly requests a different limit.
- For "top N" requests, use exactly the requested N with `LIMIT N`.

--------------------
IMPORTANT SEMANTIC RULES
--------------------
- If the user asks about positive / negative values,
  ALWAYS use the numeric sign of "Transaction Value":
    - negative: "Transaction Value" < 0
    - positive: "Transaction Value" > 0
    - zero: "Transaction Value" = 0
- Do NOT infer positivity/negativity from "Debit/Credit ind"
  unless the user EXPLICITLY asks about that column.
- If the user asks about missing values,
  treat missing as SQL NULL after data cleaning.
- If filtering for "empty strings", check both NULL and empty:
  col IS NULL OR TRIM(col) = ''

--------------------
OUTPUT RULES
--------------------
- Return ONLY JSON (a single object).
- Do NOT include markdown.
- Do NOT include any text outside the JSON.
- Do NOT invent columns or tables.
- If unsure, choose the most conservative and explicit interpretation.

Use provided dataset schema and knowledge context
to understand column meanings and business intent,
but never override explicit user instructions.
""".strip()


def _validate_decision(obj: Any) -> dict:
    """
    Validate the model's JSON output against the minimal expected contract.
    Raises RuntimeError on invalid output.
    """
    if not isinstance(obj, dict):
        raise RuntimeError("Model output is not a JSON object.")

    mode = str(obj.get("mode", "")).strip()
    explanation = str(obj.get("explanation", "")).strip()

    if mode not in {"sql", "analysis"}:
        raise RuntimeError(f"Invalid mode: {mode!r}. Expected 'sql' or 'analysis'.")

    if not explanation:
        raise RuntimeError("Missing or empty 'explanation' field.")

    if mode == "sql":
        sql = str(obj.get("sql", "")).strip()
        if not sql:
            raise RuntimeError("Missing or empty 'sql' field for mode='sql'.")
    else:
        analysis = str(obj.get("analysis", "")).strip()
        if not analysis:
            raise RuntimeError("Missing or empty 'analysis' field for mode='analysis'.")

    return obj


def ask_model(question: str, schema: str, cfg: AppConfig, extra_context: str = "") -> dict:
    """
    Ask the LLM to either:
      - produce a safe SELECT-only SQL query (mode='sql'), or
      - produce an analysis plan (mode='analysis').

    The function enforces a strict JSON response contract and validates it.
    """
    if not cfg.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not set. Put it in .env")

    client = OpenAI(api_key=cfg.openai_api_key)

    ctx_block = f"\n\nKnowledge context:\n{extra_context}\n" if extra_context else ""

    user_prompt = f"""Dataset schema:
{schema}
{ctx_block}
User question:
{question}
"""

    # response_format enforces JSON output on supported OpenAI models.
    # If a model does not support it, OpenAI SDK will raise an error; in that case,
    # remove response_format and rely on JSON parsing fallback.
    resp = client.chat.completions.create(
        model=cfg.openai_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.1,
        response_format={"type": "json_object"},
    )

    text = (resp.choices[0].message.content or "").strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Model did not return valid JSON. Raw output:\n{text}") from e

    return _validate_decision(parsed)
