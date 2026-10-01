# Evaluation methodology

- **Set:** `eval/questions.json` — 60 questions, each with a gold SQL
  query (except blocked/unsupported expectations). Categories: claim
  counts/filters, aggregates, grouped claims, policies, claims-by-product-line
  joins, payments, adjusters, temporal grouping, 2 deliberately hard
  questions (median, year-over-year growth %), 3 guardrail questions
  (2 PII requests, 1 delete request), 1 unsupported forecast question.
- **Scoring:** `eval/run_eval.py` computes the expected answer by running
  the gold SQL directly in DuckDB, then compares the agent's rows
  (order-insensitive, floats rounded to 2dp). Blocked/unsupported items
  are correct only when the agent refuses with the expected status.
- **Measured result (local, synthetic data): 58/60 = 96.7%.**
  The 2 misses are the deliberately hard questions: the median question
  (no template -> unsupported) and the year-over-year growth question
  (generator falls back to a plain count). Both are reported, not hidden.
- **Interpretation:** most of the 60 questions sit inside the rule
  templates' coverage by design — this number measures template coverage
  and guardrail behaviour on a synthetic replica. It is **not**
  comparable to the 87%-on-60-questions figure from the resume, which
  was measured on the original Claude-backed production version against
  a real Athena/Glue warehouse.
- Reproduce: `python eval/run_eval.py` (writes `outputs/eval_results.csv`
  and `outputs/eval_summary.json`).
