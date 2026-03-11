# AI Data Quality PoC
**Junior AI Specialist – GenAI / LLM / RAG**

---

## Overview

This repository contains a proof-of-concept (PoC) for **AI-assisted data quality management**.

The goal of this PoC is to demonstrate how **non-technical users** can explore and assess data quality using **natural language**, while the system safely translates user questions into **controlled SQL queries** and analytical checks.

The solution was designed to resemble a **real corporate analytics PoC** rather than a toy demo, with a strong emphasis on:

- correctness
- safety
- explainability
- controlled use of Large Language Models (LLMs)

The PoC addresses a typical client request for an **AI-powered “data analyst”** capable of:

- profiling datasets
- detecting missing values and anomalies
- answering basic data quality questions interactively
- doing so without allowing unsafe or destructive operations

---

## Key Features

### Data ingestion
- Loads Excel data into a pandas DataFrame
- Drops fully empty rows
- Normalizes column names for consistent downstream processing

### Data cleaning & normalization
- Handles mixed numeric locales (e.g. `370,374`, `342,954.98`)
- Normalizes boolean and selection-like fields
- Safely parses date and integer-like columns
- Produces a structured cleaning report for transparency

### Dataset profiling
- Row and column counts
- Column data types
- Percentage of missing values
- Identification of numeric and datetime fields
- Compact schema text representation used as LLM context

### Manual SQL exploration
- SQL queries executed via `pandasql` (SQLite dialect)
- Strict SQL guardrails:
  - SELECT-only queries
  - disallowed keywords filtering
  - automatic LIMIT enforcement for large result sets

### Predefined data quality checks (no AI)
- Missing value detection
- Value distributions
- Debit/Credit balance checks
- Duplicate detection
- Basic descriptive statistics

### LLM-powered Q&A
- Natural-language questions translated into:
  - safe SQL queries, or
  - analytical explanations
- Strict JSON-based contract between the LLM and the application
- All generated SQL is validated before execution

### Retrieval-Augmented Generation (RAG)
- Optional enrichment from local knowledge files (`./knowledge`)
- Improves explanations of domain-specific columns and rules
- Fully local implementation (TF-IDF–based), no external vector database
- Reduces hallucinations and increases business-context accuracy

---

## Architecture (High-Level)

### Data Layer
- Excel → pandas DataFrame
- In-memory processing (no database required for PoC)

### Processing Layer
- Data cleaning & normalization
- Dataset profiling & schema generation
- SQL execution via `pandasql`

### AI Layer
- LLM generates either:
  - safe SQL queries, or
  - analytical explanations
- Optional RAG context retrieved from local documentation

### Interface
- Interactive command-line interface (CLI)
- Clear separation between:
  - manual actions
  - automated checks
  - AI-driven interactions

---

## Project Structure

```text
.
├── app/
│   ├── __init__.py
│   ├── analysis.py        # Outlier detection (IQR)
│   ├── cleaning.py        # Data normalization & cleaning
│   ├── cli.py             # Interactive CLI
│   ├── config.py          # Centralized configuration
│   ├── data_loader.py     # Excel loading
│   ├── executor.py        # SQL execution via pandasql
│   ├── llm.py             # LLM interaction (OpenAI)
│   ├── profiling.py       # Dataset profiling & schema text
│   ├── rag.py             # TF-IDF–based RAG
│   └── sql_safety.py      # SQL guardrails
├── data/
│   └── sample.xlsx        # Example dataset
├── knowledge/
│   ├── data_dictionary.md
│   └── quality_rules.md
├── .gitignore
├── ARCHITECTURE.md
├── main.py                # Application entry point
├── requirements.txt
└── README.md
```

## Installation

1. Create a virtual environment (recommended)

    python -m venv .venv
    source .venv/bin/activate   # Linux / macOS
    .venv\Scripts\activate      # Windows

2. Install dependencies

    pip install -r requirements.txt

3. Environment variables

Create a .env file in the project root:

    DATA_PATH=data/sample.xlsx
    OPENAI_API_KEY=your_openai_key_here
    OPENAI_MODEL=gpt-4o-mini
    KNOWLEDGE_DIR=knowledge
    SQL_DEFAULT_LIMIT=50

**Note:**  
All non-LLM functionality works without an API key.

---

## Usage

Start the CLI:

    python main.py

### Available commands

- profile — show dataset profile
- sql — run manual SQL queries (SELECT-only)
- checks — run predefined data quality checks
- outliers — detect outliers using the IQR rule
- ask — ask a natural-language question (LLM)
- ask_rag — ask a question with additional RAG context
- exit — quit the application

---

## Example Questions

- How many rows have empty Clearing Date?
- What is the total Transaction Value by Currency?
- How many negative Transaction Values are there?
- What does Debit/Credit ind mean?
- How are outliers detected in this PoC?

---

## Safety & Guardrails

To ensure predictable and safe behavior:

- Only SELECT queries are allowed
- Destructive SQL keywords are blocked
- Semicolons are disallowed
- Result size is limited for CLI readability
- All LLM outputs are validated before execution

These measures prevent unsafe operations while keeping the system usable for non-technical users.

---

## Scope & Limitations

This PoC intentionally:

- avoids persistent databases
- avoids web frontends
- prioritizes correctness and explainability over infrastructure complexity

It is designed as a foundation that can be extended with:

- real SQL databases
- dashboards or web-based UIs
- embedding-based or vector-database-backed RAG
- enterprise authentication and access control

---

## Author

**Vladyslav Korzun**  
