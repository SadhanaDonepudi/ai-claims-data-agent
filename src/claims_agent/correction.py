"""Deterministic self-correction for failed SQL.

On an execution error the agent retries with adjusted SQL (counting
attempts). Strategies, in order: (1) replace a missing/misspelled column
with the closest schema column (difflib), (2) drop a failing ORDER BY,
(3) drop a failing GROUP BY column back to a plain aggregate. This is a
local, rule-based stand-in for the production LLM self-correction loop.
"""
from __future__ import annotations

import difflib
import re

from .catalog import all_columns


def propose_correction(sql: str, error: str) -> str | None:
    cols = all_columns()
    m = re.search(r'column\s+"?([A-Za-z_][A-Za-z0-9_]*)"?', error, flags=re.I)
    if not m:
        m = re.search(r"\b([A-Za-z_][A-Za-z0-9_]*)\b.*not found", error, flags=re.I)
    if m:
        bad = m.group(1)
        close = difflib.get_close_matches(bad, list(cols), n=1, cutoff=0.6)
        if close and close[0] != bad:
            return re.sub(rf"\b{re.escape(bad)}\b", close[0], sql)
    if "order" in error.lower() and "ORDER BY" in sql.upper():
        return re.sub(r"\s+ORDER BY[^;]+?(?=\s+LIMIT|\s*$)", "", sql, flags=re.I)
    if "group" in error.lower() and "GROUP BY" in sql.upper():
        return re.sub(r"\s+GROUP BY[^;]+?(?=\s+ORDER BY|\s+LIMIT|\s*$)", "", sql, flags=re.I)
    return None
