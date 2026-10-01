"""Tool layer shared by the agent and the MCP server.

In production these tools would be exposed by a Model Context Protocol
server in front of Athena. Locally they run guarded DuckDB queries.
"""
from __future__ import annotations

import pathlib

import duckdb

from .catalog import CATALOG, describe_table, list_tables
from .db import ensure_db
from .guardrails import validate_and_limit


class ClaimsTools:
    def __init__(self, db_path: str | pathlib.Path | None = None):
        self.db_path = ensure_db(db_path) if db_path else ensure_db()
        self._con = duckdb.connect(str(self.db_path), read_only=True)

    def list_tables(self) -> list[str]:
        return list_tables()

    def describe_table(self, table: str) -> dict:
        return describe_table(table)

    def get_catalog(self) -> dict:
        return CATALOG

    def run_query(self, sql: str, row_limit: int = 1000) -> dict:
        """Guardrail-checked, read-only query. GuardrailViolation propagates."""
        safe_sql = validate_and_limit(sql, row_limit=row_limit)
        cur = self._con.execute(safe_sql)
        cols = [d[0] for d in cur.description]
        rows = [list(r) for r in cur.fetchall()]
        return {"sql": safe_sql, "columns": cols, "rows": rows, "row_count": len(rows)}

    def close(self):
        self._con.close()
