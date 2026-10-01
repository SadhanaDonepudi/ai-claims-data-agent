# AI Claims Data Agent

Let business analysts query claims data in plain English — safely.

An agent that turns a plain-English question into SQL, checks it against
read-only / row-limit / PII guardrails, runs it, and self-corrects on
errors. Tools are exposed through a **real Model Context Protocol (MCP)
server** built on the official `mcp` Python SDK.

> **Local replica disclosure.** The resume project this is based on used
> Claude tool use, an MCP server, Amazon Athena, the AWS Glue Data
> Catalog, and Lambda. This repository reproduces that architecture
> locally with **no Claude API and no AWS**: DuckDB stands in for Athena,
> a local schema catalog stands in for Glue, and a deterministic
> rule/template generator stands in for the LLM. Everything is labelled
> below — nothing here claims a live LLM or AWS service ran.

## Measured results (local, synthetic data — actual run outputs)

| Metric | Measured locally |
|---|---|
| Evaluation accuracy | **58 / 60 questions = 96.7%** |
| Accuracy on answerable (non-refusal) questions | 54 / 56 = 96.4% |
| Synthetic database | 2,000 policies · 3,500 claims · 1,747 claim payments · 30 adjusters |
| Test suite | 41 passed (`pytest`) |
| MCP tools verified | `list_tables`, `describe_table`, `run_query` — via SDK registry **and** a full MCP client session over stdio |

The 2 evaluation misses are deliberate hard questions (median claim
amount; year-over-year growth %) that sit outside the rule templates —
they are reported in `outputs/eval_results.csv`, not hidden. Most eval
questions are inside the templates' coverage by design, so 96.7%
measures template coverage + guardrail behaviour on this replica.

**Resume figure, kept distinct:** the original production version,
backed by Claude against a real Athena/Glue warehouse, answered **87%
of its 60-question evaluation set** correctly. That 87% is *not* the
number measured here and the two are not comparable — different SQL
generator (LLM vs rules), different data (real vs synthetic).

The resume's "delivered in 3 weeks with AI coding assistants (Claude
Code, OpenAI Codex), unit tests, linting and PR reviews" bullet is a
process narrative about the original build; it is background, not a
metric this repository measures.

## What's implemented vs emulated

| Piece | Status |
|---|---|
| MCP server (official `mcp` SDK, FastMCP, stdio transport) | ✅ **Implemented — real MCP.** An MCP client can connect, list tools, and call them (proven in tests). |
| Tool layer (`list_tables` / `describe_table` / `run_query`) | ✅ Implemented |
| SQL guardrails (read-only AST check, LIMIT 1000 injection/cap, PII blocklist, `SELECT *` block) | ✅ Implemented + tested |
| Schema retrieval (keyword scoring over the catalog) | ✅ Implemented (local substitute for Glue retrieval) |
| NL → SQL generation | ⚠️ **Rule/template-based** (pattern matching + slot filling). No LLM. Out-of-template questions return `unsupported` instead of hallucinating SQL. |
| Self-correction loop (fix misspelled columns, drop failing ORDER BY; max 3 attempts, attempts counted) | ✅ Implemented (rule-based stand-in for LLM self-correction) |
| `ClaudeBackend` | ⛔ **Not implemented / not exercised.** A documented integration point in `llm.py` that raises `NotImplementedError`. No Claude API key exists in this environment. |
| Athena / Glue Data Catalog / Lambda | ⛔ Emulated by DuckDB / local catalog / local processes. No AWS calls. |
| Data | Synthetic only (seed 42). Fake SSNs (`900-01-xxxx`), `example.invalid` emails. |

## Try it

```bash
pip install -r requirements.txt
export PYTHONPATH=src

python -m claims_agent.generate_data          # builds data/claims.duckdb (git-ignored)
python -m claims_agent.cli "How many claims are open?"
python -m claims_agent.cli "What is the total paid amount by claim type?"
python -m claims_agent.cli "Show me claimant names and their SSN"   # -> blocked (PII)
python -m claims_agent.cli "Delete all denied claims"               # -> blocked (read-only)

python -m claims_agent.mcp_server             # real MCP server over stdio
python eval/run_eval.py                       # 60-question evaluation -> outputs/
python -m pytest tests/ -q                    # 41 tests
```

Example answer:

```json
{
  "question": "How many claims are open?",
  "status": "answered",
  "sql": "SELECT COUNT(*) AS claim_count FROM claims WHERE claim_status = 'Open' LIMIT 1000",
  "rows": [[854]],
  "attempts": 1,
  "backend": "rule-based (no LLM)"
}
```

*(854 is the count in the current synthetic snapshot; regenerate the DB and the eval harness recomputes every expectation from gold SQL.)*

## Layout

```
src/claims_agent/
  catalog.py          local Glue-catalog stand-in (tables, columns, PII flags)
  generate_data.py    synthetic DuckDB build (2,000 policies / 3,500 claims / ...)
  schema_retrieval.py question -> relevant tables/columns
  generator.py        rule/template NL-to-SQL (NO LLM)
  llm.py              LLMBackend protocol: RuleBasedBackend (used) + ClaudeBackend (not exercised)
  guardrails.py       read-only / LIMIT / PII enforcement via sqlglot AST
  correction.py       deterministic self-correction for failed SQL
  tools.py            tool layer shared by agent + MCP server
  mcp_server.py       real MCP server (FastMCP, stdio)
  agent.py            question -> retrieve -> generate -> guard -> run -> correct -> answer
  cli.py              one-question command line
eval/questions.json   60 questions + gold SQL
eval/run_eval.py      evaluation harness -> outputs/eval_results.csv, eval_summary.json
tests/                41 tests: guardrails, generator, agent/self-correction, tools, MCP protocol
docs/                 architecture (local->production), guardrail spec, eval methodology
```

## Production mapping

See `docs/architecture.md`. In production the same agent loop keeps its
shape: Claude (via the `ClaudeBackend` integration point) calls the MCP
tools with tool use; `run_query` targets Athena instead of DuckDB; the
catalog comes from the Glue Data Catalog; the server runs on Lambda.
The guardrail module and the evaluation harness carry over unchanged.
