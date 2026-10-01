"""Agent core: question -> schema retrieval -> SQL -> guardrails -> run
-> self-correction on error -> answer.

Locally the "AI" is the rule-based backend (no LLM). The control flow —
retrieve schema, generate, validate, execute, correct-and-retry — is
the same shape as the production Claude tool-use loop.
"""
from __future__ import annotations

import pathlib
import re
from dataclasses import dataclass, field

from .correction import propose_correction
from .generator import UnsupportedQuestion
from .guardrails import GuardrailViolation, validate_and_limit
from .llm import LLMBackend, RuleBasedBackend
from .schema_retrieval import retrieve_schema
from .tools import ClaimsTools

_PII_ASK = re.compile(r"\b(ssn|social security|claimant name|claimant email|claimant phone|phone number|email address|names of (the )?claimants)\b", re.I)
_MUTATION_ASK = re.compile(r"^\s*(delete|update|insert|drop|alter|truncate)\b", re.I)


@dataclass
class AgentResult:
    question: str
    status: str = "failed"  # answered | blocked | unsupported | failed
    sql: str | None = None
    columns: list = field(default_factory=list)
    rows: list = field(default_factory=list)
    attempts: int = 0
    schema_tables: list = field(default_factory=list)
    error: str | None = None
    backend: str = "rule-based (no LLM)"


class ClaimsAgent:
    def __init__(self, db_path: str | pathlib.Path | None = None, backend: LLMBackend | None = None, max_attempts: int = 3):
        self.tools = ClaimsTools(db_path) if db_path else ClaimsTools()
        self.backend = backend or RuleBasedBackend()
        self.max_attempts = max_attempts

    def ask(self, question: str) -> AgentResult:
        schema = retrieve_schema(question)
        base = AgentResult(question=question, schema_tables=schema["tables"], backend=self.backend.name)
        if _MUTATION_ASK.search(question):
            base.status, base.error = "blocked", "mutation/DDL requests are blocked (read-only access only)"
            return base
        if _PII_ASK.search(question):
            base.status, base.error = "blocked", "PII columns are blocked (claimant name/SSN/email/phone)"
            return base
        try:
            sql = self.backend.generate_sql(question, schema)
        except UnsupportedQuestion as exc:
            base.status, base.error = "unsupported", str(exc)
            return base
        except NotImplementedError as exc:
            base.status, base.error = "failed", str(exc)
            return base
        return self.execute_with_correction(sql, base)

    def execute_with_correction(self, sql: str, base: AgentResult | None = None) -> AgentResult:
        """Guard + execute SQL, self-correcting on execution errors."""
        result = base or AgentResult(question="(direct SQL)")
        result.sql = sql
        current = sql
        last_error = None
        for attempt in range(1, self.max_attempts + 1):
            result.attempts = attempt
            try:
                safe = validate_and_limit(current)
            except GuardrailViolation as exc:
                result.status, result.error, result.sql = "blocked", str(exc), current
                return result
            try:
                out = self.tools.run_query(safe)
                result.status, result.sql = "answered", out["sql"]
                result.columns, result.rows = out["columns"], out["rows"]
                return result
            except Exception as exc:  # DuckDB execution error -> try correction
                last_error = str(exc)
                corrected = propose_correction(current, last_error)
                if corrected is None or corrected == current:
                    break
                current = corrected
                result.sql = current
        result.status, result.error = "failed", last_error
        return result

    def close(self):
        self.tools.close()
