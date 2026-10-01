"""Command-line interface: ask one question in plain English."""
from __future__ import annotations

import argparse
import json

from .agent import ClaimsAgent


def main() -> None:
    ap = argparse.ArgumentParser(description="AI Claims Data Agent (local DuckDB replica, no LLM)")
    ap.add_argument("question", help="plain-English question about claims data")
    args = ap.parse_args()
    agent = ClaimsAgent()
    result = agent.ask(args.question)
    print(json.dumps({
        "question": result.question, "status": result.status, "sql": result.sql,
        "columns": result.columns, "rows": result.rows[:20], "attempts": result.attempts,
        "schema_tables": result.schema_tables, "error": result.error, "backend": result.backend,
    }, indent=2, default=str))
    agent.close()


if __name__ == "__main__":
    main()
