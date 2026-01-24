"""
Centralized configuration for the PoC.

Keeps environment parsing in one place and avoids scattering os.getenv across the codebase.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AppConfig:
    """Runtime configuration loaded from environment variables."""
    data_path: str
    openai_api_key: str | None
    openai_model: str
    knowledge_dir: str
    sql_default_limit: int


def load_config() -> AppConfig:
    """
    Load configuration from environment variables.

    Environment variables:
      - DATA_PATH (default: data/sample.xlsx)
      - OPENAI_API_KEY (optional for non-LLM mode)
      - OPENAI_MODEL (default: gpt-4o-mini)
      - KNOWLEDGE_DIR (default: knowledge)
      - SQL_DEFAULT_LIMIT (default: 50)
    """
    data_path = os.getenv("DATA_PATH", "data/sample.xlsx")
    openai_api_key = os.getenv("OPENAI_API_KEY")
    openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    knowledge_dir = os.getenv("KNOWLEDGE_DIR", "knowledge")

    # Safe default for CLI readability
    try:
        sql_default_limit = int(os.getenv("SQL_DEFAULT_LIMIT", "50"))
    except ValueError:
        sql_default_limit = 50

    return AppConfig(
        data_path=data_path,
        openai_api_key=openai_api_key,
        openai_model=openai_model,
        knowledge_dir=knowledge_dir,
        sql_default_limit=sql_default_limit,
    )
