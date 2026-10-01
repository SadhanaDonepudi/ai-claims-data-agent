# Architecture: local replica -> production

This repository is a **local replica** of the production system described
on the resume (Claude tool use + MCP server + Amazon Athena + AWS Glue
Data Catalog, deployed on Lambda). No AWS or Claude API is used locally.

| Concern | Production (resume) | This repo (local) | Status |
|---|---|---|---|
| LLM | Claude with tool use | Rule/template NL-to-SQL generator (`generator.py`) behind the `LLMBackend` protocol | **Substituted, documented** |
| LLM integration point | Claude API | `ClaudeBackend` in `llm.py` — raises `NotImplementedError` | **Not exercised** |
| Tool protocol | Model Context Protocol server | Official `mcp` Python SDK (FastMCP 1.12.4) over stdio, tools `list_tables` / `describe_table` / `run_query` | **Implemented (real MCP)** |
| SQL engine | Amazon Athena | DuckDB (`data/claims.duckdb`, generated, git-ignored) | Substituted |
| Schema catalog | AWS Glue Data Catalog | `catalog.py` + `data/catalog.json` + in-DB `schema_catalog` table | Emulated |
| Hosting | AWS Lambda | Local CLI (`cli.py`) / local MCP stdio server | Emulated |
| Data | Real claims warehouse | Synthetic: 2,000 policies, 3,500 claims, 1,747 claim payments, 30 adjusters (seed 42) | Synthetic |

## Agent loop (same shape in both)

```
question
  -> schema retrieval      (retrieve_schema: keyword scoring over the catalog)
  -> SQL generation        (Claude tool use in prod; rule templates locally)
  -> guardrails            (validate_and_limit: read-only, LIMIT, PII blocklist)
  -> execution             (Athena in prod; DuckDB locally)
  -> self-correction       (on error, propose_correction retries, max 3 attempts)
  -> answer (rows + the SQL that produced them)
```

## What is NOT here

- No Claude API calls, no API key, no live LLM anywhere in this repo.
- No Athena, Glue, S3, or Lambda resources.
- No real claims data — names/SSNs/emails are invented (SSNs use the
  fictional `900-01-xxxx` range, emails use `example.invalid`).
