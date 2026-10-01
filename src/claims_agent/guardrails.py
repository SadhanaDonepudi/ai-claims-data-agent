"""SQL guardrails: read-only enforcement, LIMIT injection, PII blocklist.

These guardrails are the local equivalent of the production controls
described in the resume: read-only access, row limits, and a PII column
blocklist.  They are implemented with sqlglot AST inspection — not
string matching — so subqueries, CTEs and quoted identifiers are all
checked, and every column reference in the query is visited.
"""
from __future__ import annotations

import sqlglot
from sqlglot import exp

from .catalog import PII_COLUMNS

DEFAULT_ROW_LIMIT = 1000
MAX_ROW_LIMIT = 1000

_BLOCKED_EXPRESSIONS = (
    exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Create,
    exp.Alter, exp.TruncateTable, exp.Copy, exp.Grant,
)
_MUTATION_KEYWORDS = ("insert", "update", "delete", "drop", "alter", "truncate", "create table", "copy ", "grant", "attach", "load ")


class GuardrailViolation(Exception):
    """Raised when a query violates a guardrail. The query is never executed."""


def _check_pii(tree: exp.Expression) -> None:
    cols = {c.name.lower() for c in tree.find_all(exp.Column) if c.name}
    # A bare SELECT * would expose PII columns from claims; block it.
    # (COUNT(*) is fine: its star lives inside an aggregate, not a projection.)
    for select in tree.find_all(exp.Select):
        for projection in select.expressions:
            if isinstance(projection, exp.Star) or (isinstance(projection, exp.Column) and projection.is_star):
                raise GuardrailViolation("SELECT * is blocked: it could expose PII columns; name columns explicitly")
    blocked = cols & {c.lower() for c in PII_COLUMNS}
    if blocked:
        raise GuardrailViolation(f"PII column(s) blocked: {sorted(blocked)}")


def validate_and_limit(sql: str, row_limit: int = DEFAULT_ROW_LIMIT) -> str:
    """Validate ``sql`` and return a safe, LIMIT-capped version.

    Raises GuardrailViolation for any mutation, multi-statement input,
    PII access, or non-SELECT statement.
    """
    if not sql or not sql.strip():
        raise GuardrailViolation("empty query")
    lowered = sql.strip().lower()
    # Fast keyword backstop (the AST check below is authoritative).
    first_word = lowered.split(None, 1)[0] if lowered.split() else ""
    if first_word in {"insert", "update", "delete", "drop", "alter", "truncate", "create", "grant", "attach"}:
        raise GuardrailViolation(f"mutation/DDL statements are blocked (starts with {first_word!r})")
    try:
        statements = sqlglot.parse(sql, read="duckdb")
    except Exception as exc:  # parse errors surface as guardrail failures
        raise GuardrailViolation(f"unparseable SQL: {exc}") from exc
    statements = [s for s in statements if s is not None]
    if len(statements) != 1:
        raise GuardrailViolation(f"exactly one statement is allowed, got {len(statements)}")
    tree = statements[0]
    if any(isinstance(n, _BLOCKED_EXPRESSIONS) for n in tree.walk(bfs=False)):
        raise GuardrailViolation("mutation/DDL statements are blocked (read-only access only)")
    # Allow SELECT and WITH ... SELECT only.
    core = tree
    if isinstance(tree, exp.With):
        core = tree.this
    if not isinstance(core, (exp.Select, exp.Union)):
        raise GuardrailViolation(f"only SELECT queries are allowed, got {type(core).__name__}")
    _check_pii(tree)
    limit = min(int(row_limit), MAX_ROW_LIMIT)
    existing = tree.args.get("limit")
    if existing is not None:
        try:
            requested = int(existing.expression.name)  # type: ignore[union-attr]
        except Exception:
            requested = limit
        if requested > limit:
            tree.set("limit", exp.Limit(expression=exp.Literal.number(limit)))
    else:
        tree.set("limit", exp.Limit(expression=exp.Literal.number(limit)))
    return tree.sql(dialect="duckdb")
