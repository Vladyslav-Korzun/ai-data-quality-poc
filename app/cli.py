from __future__ import annotations

import re

import pandas as pd
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from tabulate import tabulate

from app.analysis import iqr_outliers
from app.cleaning import clean_dataframe
from app.config import AppConfig, load_config
from app.data_loader import load_excel
from app.executor import run_sql
from app.llm import ask_model
from app.profiling import profile_dataframe, schema_text
from app.rag import format_context, retrieve_context
from app.sql_safety import enforce_limit, is_safe_sql

console = Console()

HELP_TEXT = """
[bold]Commands:[/bold]
- [cyan]profile[/cyan]     show dataset profile
- [cyan]examples[/cyan]    show example SQL queries
- [cyan]sql[/cyan]         run SQL (multi-line supported). End input with an empty line.
- [cyan]checks[/cyan]      run a bundle of data-quality checks (no LLM)
- [cyan]ask[/cyan]         ask in natural language (LLM generates SQL or analysis plan)
- [cyan]ask_rag[/cyan]     ask with RAG context from ./knowledge (recommended)
- [cyan]outliers[/cyan]    run IQR outlier detection (no LLM)
- [cyan]exit[/cyan]        quit

[bold]Notes:[/bold]
- SQL table name is: [bold]data[/bold]
- Only SELECT queries are allowed (guardrails)
- If query returns many rows and has no LIMIT, app will add LIMIT for readability
- API key is read from .env (never commit secrets)
- RAG reads markdown/txt files from ./knowledge
""".strip()

EXAMPLES = """
[bold]Example SQL queries:[/bold]

1) Count rows
SELECT COUNT(*) AS cnt FROM data

2) Missing clearing date
SELECT COUNT(*) AS missing_clearing_date
FROM data
WHERE "Clearing Date" IS NULL

3) Total by currency
SELECT Currency, SUM("Transaction Value") AS total_value
FROM data
GROUP BY Currency
ORDER BY total_value DESC

4) Biggest absolute transactions
SELECT "Transaction Value", Currency, "Debit/Credit ind"
FROM data
ORDER BY ABS("Transaction Value") DESC
LIMIT 10

[bold]Example ask questions:[/bold]
- How many rows have empty Clearing Date?
- What is the total Transaction Value by Currency?
- Show top 10 largest absolute Transaction Value rows.
- How many negative Transaction Values are there?

[bold]Example ask_rag questions:[/bold]
- What does Debit/Credit ind mean?
- How are outliers detected in this PoC?
- Why might Clearing Date be missing?
""".strip()


def _print_df(df: pd.DataFrame) -> None:
    """Pretty-print a DataFrame to the CLI (keeps output compact)."""
    if len(df) == 0:
        console.print("[yellow]No rows returned.[/yellow]")
        return

    # Scalar result (single cell)
    if len(df) == 1 and len(df.columns) == 1:
        console.print(f"[green]Result:[/green] [bold]{df.iloc[0, 0]}[/bold]")
        return

    console.print(tabulate(df.head(20), headers="keys", tablefmt="github", showindex=False))
    if len(df) > 20:
        console.print(f"[yellow]Showing first 20 rows out of {len(df)}[/yellow]")


def _read_multiline_sql() -> str:
    """Read multi-line SQL input from user. Input ends with an empty line."""
    console.print("[bold]Enter SQL (SELECT-only). Finish with empty line:[/bold]")
    lines: list[str] = []
    while True:
        line = console.input("").rstrip("\n")
        if line.strip() == "":
            break
        lines.append(line)
    return "\n".join(lines).strip()


def _is_scalar_query(sql: str) -> bool:
    """
    Heuristic: treat a query as scalar if it looks like it returns a single aggregated value.
    This helps decide when to auto-apply LIMIT for readability.
    """
    s = re.sub(r"\s+", " ", (sql or "").strip().lower())
    if not s.startswith("select "):
        return False

    # GROUP BY usually implies multiple rows
    if " group by " in s:
        return False

    return any(fn in s for fn in ["count(", "sum(", "avg(", "min(", "max("])


def _apply_limit_if_needed(sql: str, limit: int) -> str:
    """Apply LIMIT to non-scalar queries to keep CLI output small."""
    if _is_scalar_query(sql):
        return sql
    return enforce_limit(sql, limit=limit)


def _run_sql_safe(df: pd.DataFrame, sql: str, cfg: AppConfig) -> None:
    """Validate SQL (SELECT-only), auto-limit, execute, and print result."""
    ok, reason = is_safe_sql(sql)
    if not ok:
        console.print(Panel(f"{reason}\n\nYour SQL:\n{sql}", title="Blocked SQL", style="red"))
        return

    sql_to_run = _apply_limit_if_needed(sql, limit=cfg.sql_default_limit)
    console.print(Panel(sql_to_run, title="Executing SQL"))

    try:
        result = run_sql(df, sql_to_run)
    except Exception as e:
        console.print(Panel(str(e), title="SQL execution error", style="red"))
        return

    _print_df(result)


def _handle_llm_decision(df: pd.DataFrame, decision: dict, cfg: AppConfig, panel_title_sql: str) -> None:
    """
    Handle model response in the strict JSON contract:
    - mode: sql | analysis
    - sql / analysis
    - explanation
    """
    mode = (decision.get("mode") or "").strip()
    explanation = (decision.get("explanation") or "").strip()

    if mode == "sql":
        sql = (decision.get("sql") or "").strip()
        ok, reason = is_safe_sql(sql)
        if not ok:
            console.print(Panel(f"{reason}\n\nModel SQL:\n{sql}", title="Blocked SQL from LLM", style="red"))
            return

        sql_to_run = _apply_limit_if_needed(sql, limit=cfg.sql_default_limit)
        console.print(Panel(sql_to_run, title=panel_title_sql))
        if explanation:
            console.print(f"[green]Explanation:[/green] {explanation}")

        try:
            result = run_sql(df, sql_to_run)
        except Exception as e:
            console.print(Panel(str(e), title="SQL execution error", style="red"))
            return

        _print_df(result)
        return

    if mode == "analysis":
        analysis = (decision.get("analysis") or "").strip()
        console.print(Panel(analysis, title="LLM analysis plan"))
        if explanation:
            console.print(f"[green]Explanation:[/green] {explanation}")
        console.print("[yellow]Tip:[/yellow] For outliers, use command: outliers")
        return

    console.print(Panel(str(decision), title="Unexpected LLM output", style="yellow"))


def _run_checks(df: pd.DataFrame, cfg: AppConfig) -> None:
    """Run a predefined set of SQL-based data-quality checks (no LLM)."""
    console.print(Panel.fit("Running data-quality checks (no LLM)", title="Checks"))

    checks = [
        ("Row count", "SELECT COUNT(*) AS rows FROM data"),
        ("Missing Clearing Date", 'SELECT COUNT(*) AS missing_clearing_date FROM data WHERE "Clearing Date" IS NULL'),
        ("Missing Clearing Entry Date", 'SELECT COUNT(*) AS missing_clearing_entry_date FROM data WHERE "Clearing Entry Date" IS NULL'),
        ("Negative Transaction Value count", 'SELECT COUNT(*) AS neg_tx FROM data WHERE "Transaction Value" < 0'),
        ("Positive Transaction Value count", 'SELECT COUNT(*) AS pos_tx FROM data WHERE "Transaction Value" > 0'),
        ("Min/Max/Avg Transaction Value",
         'SELECT MIN("Transaction Value") AS min_v, MAX("Transaction Value") AS max_v, AVG("Transaction Value") AS avg_v FROM data'),
        ("Top 10 by absolute Transaction Value",
         'SELECT "Transaction Value", Currency, "Debit/Credit ind", "Clearing Date" FROM data ORDER BY ABS("Transaction Value") DESC LIMIT 10'),
        ("Totals by Currency",
         'SELECT Currency, SUM("Transaction Value") AS total_value FROM data GROUP BY Currency ORDER BY total_value DESC LIMIT 20'),
        ("Debit/Credit distribution",
         'SELECT "Debit/Credit ind" AS dc, COUNT(*) AS cnt FROM data GROUP BY "Debit/Credit ind" ORDER BY cnt DESC'),
        ("Potential duplicates (all columns)",
         'SELECT COUNT(*) AS dup_rows FROM (SELECT *, COUNT(*) AS c FROM data GROUP BY '
         '"Authorization Group","Bus. Transac. Type","Calculate Tax","Cash Flow-Relevant Doc.","Cleared Item","Clearing Date","Clearing Entry Date",'
         '"Clearing Fiscal Year","Country Key","Currency","Debit/Credit ind","Transaction Value","Document Is Back-Posted","Exchange rate",'
         '"Fiscal Year.1","Fiscal Year.2","Posting period.1","Ref. Doc. Line Item" HAVING c > 1)'),
    ]

    for title, sql in checks:
        console.print(f"\n[bold]{title}[/bold]")
        _run_sql_safe(df, sql, cfg)


def _run_outliers(df: pd.DataFrame) -> None:
    """Run IQR outlier detection on a chosen numeric column (no LLM)."""
    col = console.input("[bold]Numeric column for outliers (default: Transaction Value):[/bold] ").strip()
    if not col:
        col = "Transaction Value"

    res = iqr_outliers(df, col, k=1.5)
    if "error" in res:
        console.print(Panel(res["error"], title="Outliers error", style="red"))
        return

    console.print(
        Panel(
            f'Column: {res["column"]}\n'
            f'Q1: {res["q1"]}\nQ3: {res["q3"]}\nIQR: {res["iqr"]}\n'
            f'Lower: {res["lower"]}\nUpper: {res["upper"]}\n'
            f'Outliers: {res["outliers_count"]}',
            title="IQR Outlier Summary",
        )
    )

    out_df = res["outliers_df"]
    if res["outliers_count"] > 0:
        out_df = out_df.assign(_abs=out_df[col].abs()).sort_values("_abs", ascending=False).drop(columns=["_abs"])
        console.print("[bold]Top outliers (by absolute value):[/bold]")
        _print_df(out_df[[col, "Currency", "Debit/Credit ind"]].head(20))
    else:
        console.print("[green]No outliers detected by IQR rule.[/green]")


def _run_ask(df: pd.DataFrame, schema: str, cfg: AppConfig) -> None:
    """Ask in natural language (no RAG context)."""
    q = console.input("[bold]Ask a question about the data:[/bold]\n").strip()
    if not q:
        return

    try:
        decision = ask_model(q, schema, cfg, extra_context="")
    except Exception as e:
        console.print(Panel(str(e), title="LLM error", style="red"))
        return

    _handle_llm_decision(df, decision, cfg, panel_title_sql="LLM generated SQL")


def _run_ask_rag(df: pd.DataFrame, schema: str, cfg: AppConfig) -> None:
    """Ask in natural language with retrieved knowledge context (RAG)."""
    q = console.input("[bold]Ask a question (RAG will retrieve context):[/bold]\n").strip()
    if not q:
        return

    chunks = retrieve_context(q, knowledge_dir=cfg.knowledge_dir, top_k=4)
    ctx = format_context(chunks)

    if ctx:
        console.print(Panel(ctx, title="RAG context (top chunks)"))
    else:
        console.print(
            Panel(
                f"No knowledge context found.\nMake sure {cfg.knowledge_dir}/ contains .md or .txt files.",
                title="RAG notice",
                style="yellow",
            )
        )

    try:
        decision = ask_model(q, schema, cfg, extra_context=ctx)
    except Exception as e:
        console.print(Panel(str(e), title="LLM error", style="red"))
        return

    _handle_llm_decision(df, decision, cfg, panel_title_sql="LLM generated SQL (RAG)")


def run_cli() -> None:
    """Entry point for the interactive CLI."""
    load_dotenv()
    cfg = load_config()

    console.print(Panel.fit("AI Data Quality PoC", subtitle="Manual SQL + Checks + LLM + RAG (Safe)"))
    console.print(f"[bold]Loading Excel:[/bold] {cfg.data_path}")

    df = load_excel(cfg.data_path)
    console.print(f"[green]Loaded rows:[/green] {len(df)} | [green]columns:[/green] {df.shape[1]}")

    df, clean_report = clean_dataframe(df)
    console.print(Panel.fit(str(clean_report), title="Cleaning report"))

    prof = profile_dataframe(df)
    schema = schema_text(prof)
    console.print(Panel(schema, title="Dataset profile (after cleaning)"))

    console.print("\n" + HELP_TEXT)

    while True:
        cmd = console.input("\n[bold cyan]>[/bold cyan] ").strip().lower()

        if cmd in {"exit", "quit"}:
            console.print("Bye!")
            return

        if cmd == "help":
            console.print(HELP_TEXT)
            continue

        if cmd == "profile":
            prof = profile_dataframe(df)
            schema = schema_text(prof)
            console.print(Panel(schema, title="Dataset profile (after cleaning)"))
            continue

        if cmd == "examples":
            console.print(Panel(EXAMPLES, title="Examples"))
            continue

        if cmd == "sql":
            sql = _read_multiline_sql()
            if not sql:
                continue
            _run_sql_safe(df, sql, cfg)
            continue

        if cmd == "checks":
            _run_checks(df, cfg)
            continue

        if cmd == "outliers":
            _run_outliers(df)
            continue

        if cmd == "ask":
            _run_ask(df, schema, cfg)
            continue

        if cmd == "ask_rag":
            _run_ask_rag(df, schema, cfg)
            continue

        console.print("[yellow]Unknown command. Type 'profile', 'sql', 'checks', 'ask', 'ask_rag', 'outliers', 'examples', or 'exit'.[/yellow]")
