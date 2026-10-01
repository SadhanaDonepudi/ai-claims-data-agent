"""Evaluation harness: 60 questions, scored against gold SQL.

Expected answers are computed by executing each question's gold SQL
directly in DuckDB (bypassing the agent), then comparing the agent's
answer. Blocked/unsupported expectations check the agent's status.
Outputs: outputs/eval_results.csv, outputs/eval_summary.json
"""
from __future__ import annotations

import csv
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import duckdb  # noqa: E402
from claims_agent.agent import ClaimsAgent  # noqa: E402
from claims_agent.db import ensure_db  # noqa: E402


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def rows_match(expected, actual) -> bool:
    if len(expected) != len(actual):
        return False
    for er, ar in zip(sorted(map(repr, expected)), sorted(map(repr, actual))):
        pass  # repr-sort fallback below does the real comparison
    def norm(rows):
        out = []
        for r in rows:
            out.append(tuple(round(float(v), 2) if _num(v) is not None and not isinstance(v, bool) else v for v in r))
        return sorted(out, key=repr)
    return norm(expected) == norm(actual)


def main() -> None:
    questions = json.loads((ROOT / "eval" / "questions.json").read_text())
    db = ensure_db()
    gold_con = duckdb.connect(str(db), read_only=True)
    agent = ClaimsAgent(db_path=db)
    results, counts = [], {"correct": 0, "wrong": 0, "blocked": 0, "failed": 0, "unsupported": 0}
    for item in questions:
        qid, question, kind = item["id"], item["question"], item["expected_type"]
        res = agent.ask(question)
        if kind == "blocked":
            correct = res.status == "blocked"
            counts["blocked" if correct else "wrong"] += 1
        elif kind == "unsupported":
            correct = res.status in ("unsupported", "failed")
            counts["unsupported" if correct else "wrong"] += 1
        else:
            expected = [list(r) for r in gold_con.execute(item["gold_sql"]).fetchall()]
            correct = res.status == "answered" and rows_match(expected, res.rows)
            if correct:
                counts["correct"] += 1
            elif res.status == "answered":
                counts["wrong"] += 1
            elif res.status == "blocked":
                counts["blocked"] += 1
            else:
                counts["failed"] += 1
        if correct and kind in ("blocked", "unsupported"):
            pass  # already bucketed above; keep a single 'correct-style' tally below
        results.append({"id": qid, "question": question, "category": item.get("category", ""),
                        "expected_type": kind, "agent_status": res.status,
                        "correct": correct, "attempts": res.attempts, "sql": res.sql or "", "error": res.error or ""})
        print(f"{qid:>4} {'OK ' if correct else 'MISS'} [{res.status}] {question[:80]}")
    # Headline accuracy: blocked/unsupported items answered with the expected
    # refusal count as correct (refusing correctly IS the correct answer).
    n_correct = sum(1 for r in results if r["correct"])
    n = len(results)
    answered = [r for r in results if r["expected_type"] in ("scalar", "rows")]
    summary = {
        "total_questions": n,
        "correct": n_correct,
        "accuracy_pct": round(100.0 * n_correct / n, 1),
        "answered_questions": len(answered),
        "answered_correct": sum(1 for r in answered if r["correct"]),
        "answered_accuracy_pct": round(100.0 * sum(1 for r in answered if r["correct"]) / max(len(answered), 1), 1),
        "breakdown_agent_status": {s: sum(1 for r in results if r["agent_status"] == s) for s in ("answered", "blocked", "unsupported", "failed")},
        "backend": "rule-based (no LLM)",
        "note": "Measured locally against the synthetic DuckDB replica. The 87% resume figure was for the original Claude-backed production version and is NOT this number.",
    }
    (ROOT / "outputs").mkdir(exist_ok=True)
    with open(ROOT / "outputs" / "eval_results.csv", "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(results[0]))
        writer.writeheader(); writer.writerows(results)
    (ROOT / "outputs" / "eval_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    agent.close()


if __name__ == "__main__":
    main()
