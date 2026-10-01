"""Real MCP server (Model Context Protocol Python SDK, FastMCP) over stdio.

IMPLEMENTED (real MCP): this module uses the official ``mcp`` Python SDK
(``FastMCP``), registers genuine MCP tools, and serves them over the
standard MCP stdio transport. An MCP client (e.g. Claude Desktop, or the
production Claude agent) can connect, list tools, and call them.

EMULATED (local substitutes behind the tools): the tools execute against
DuckDB instead of Amazon Athena, and the catalog comes from a local
schema module instead of the AWS Glue Data Catalog. The MCP protocol
itself is not emulated — only the AWS backends behind the tools are.

Run:  python -m claims_agent.mcp_server
"""
# NOTE: no `from __future__ import annotations` here — FastMCP inspects
# live type objects when registering tools.
from mcp.server.fastmcp import FastMCP

from .tools import ClaimsTools

mcp = FastMCP("ai-claims-data-agent")
_tools = ClaimsTools()


@mcp.tool()
def list_tables() -> list[str]:
    """List tables in the (local Glue-catalog stand-in) claims database."""
    return _tools.list_tables()


@mcp.tool()
def describe_table(table: str) -> dict:
    """Describe one table's columns, types and PII flags."""
    return _tools.describe_table(table)


@mcp.tool()
def run_query(sql: str, row_limit: int = 1000) -> dict:
    """Run a guardrail-checked, read-only SQL query (DuckDB locally; Athena in production).

    Mutations, multi-statement SQL, SELECT *, and PII columns are blocked.
    """
    return _tools.run_query(sql, row_limit=row_limit)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
