"""LLM backend abstraction — the production integration point.

``RuleBasedBackend`` is implemented and exercised locally.
``ClaudeBackend`` documents where Claude tool use would plug in for the
production (Athena/Glue/Lambda) version: it is **NOT EXERCISED** locally.
There is no Claude API key in this environment and no live LLM call is
made anywhere in this repository.
"""
from __future__ import annotations

from typing import Protocol

from .generator import generate_sql


class LLMBackend(Protocol):
    name: str
    def generate_sql(self, question: str, schema: dict) -> str: ...


class RuleBasedBackend:
    """Deterministic template generator. Implemented and tested."""
    name = "rule-based (no LLM)"

    def generate_sql(self, question: str, schema: dict) -> str:
        return generate_sql(question)


class ClaudeBackend:
    """Production Claude integration point. NOT IMPLEMENTED / NOT EXERCISED.

    In production this backend would send the question plus the retrieved
    Glue Data Catalog schema to Claude with tool use, letting the model
    call the MCP ``run_query``/``describe_table`` tools, exactly as in
    the original resume project.  Locally it raises immediately.
    """
    name = "claude (production only, not exercised)"

    def __init__(self, *args, **kwargs):
        raise NotImplementedError(
            "ClaudeBackend is the production integration point and is NOT "
            "EXERCISED locally: no Claude API key / live LLM is available. "
            "Use RuleBasedBackend for the local DuckDB replica."
        )
