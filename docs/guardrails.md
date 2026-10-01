# Guardrail specification

Implemented in `src/claims_agent/guardrails.py` (`validate_and_limit`),
applied to *every* query before execution — whether it comes from the
agent, the CLI, or an MCP client calling `run_query`.

1. **Read-only enforcement.** The SQL is parsed with sqlglot (DuckDB
   dialect). Anything that is not a single `SELECT` (or `WITH ... SELECT`)
   is rejected, including `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`,
   `TRUNCATE`, `CREATE`, `COPY`, `GRANT`, `ATTACH`. Multi-statement
   input is rejected.
2. **Row limits.** A `LIMIT 1000` is injected when absent; a larger
   requested limit is capped to 1000.
3. **PII column blocklist.** `claimant_name`, `claimant_ssn`,
   `claimant_email`, `claimant_phone` (flagged `pii: true` in the
   catalog) are rejected anywhere in the AST — including subqueries and
   CTEs. A bare `SELECT *` is rejected because it would expose them;
   `COUNT(*)` is allowed.
4. **Question-level pre-checks.** The agent additionally refuses
   questions asking for claimant names/SSNs/emails/phones or asking to
   delete/update/insert data before SQL is even generated.

Every guardrail is covered by tests in `tests/test_guardrails.py`, and
the MCP-level block is exercised end-to-end in
`tests/test_tools_and_mcp.py` (a `DELETE` sent through a real MCP
client session returns an MCP error).
