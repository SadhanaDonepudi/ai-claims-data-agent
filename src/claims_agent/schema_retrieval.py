"""Schema retrieval: pick the tables/columns relevant to a question.

Local stand-in for production schema retrieval over the Glue Data
Catalog.  Deterministic keyword scoring — no embeddings, no LLM.
"""
from __future__ import annotations

import re

from .catalog import CATALOG, TABLE_KEYWORDS


def retrieve_schema(question: str, max_tables: int = 3) -> dict:
    q = question.lower()
    scores: dict[str, int] = {}
    for table, keywords in TABLE_KEYWORDS.items():
        score = 0
        for kw in keywords:
            if kw in q:
                score += 3
        for col in CATALOG[table]["columns"]:
            if col in q or col.replace("_", " ") in q:
                score += 2
        if table.rstrip("s") in q:
            score += 1
        if score:
            scores[table] = score
    if not scores:
        # Default to the central fact table rather than nothing.
        scores = {"claims": 1}
    ranked = sorted(scores, key=lambda t: (-scores[t], t))[:max_tables]
    # Joins: product-line questions need policies alongside claims.
    if "claims" in ranked and "product" in q and "policies" not in ranked:
        ranked.append("policies")
    return {
        "tables": ranked,
        "columns": {t: list(CATALOG[t]["columns"]) for t in ranked},
        "scores": {t: scores[t] for t in ranked},
    }
