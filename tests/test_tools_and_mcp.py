import asyncio

import pytest

from claims_agent.guardrails import GuardrailViolation


def test_tools_list_and_describe(agent):
    tools = agent.tools
    assert "claims" in tools.list_tables()
    desc = tools.describe_table("claims")
    assert desc["columns"]["claimant_ssn"]["pii"] is True
    assert desc["columns"]["claim_amount"]["pii"] is False


def test_tools_run_query_guardrails(agent):
    tools = agent.tools
    out = tools.run_query("SELECT COUNT(*) AS n FROM policies")
    assert out["rows"][0][0] == 2000
    with pytest.raises(GuardrailViolation):
        tools.run_query("SELECT claimant_email FROM claims")
    with pytest.raises(GuardrailViolation):
        tools.run_query("DELETE FROM policies")


def test_mcp_server_registers_real_tools():
    from claims_agent.mcp_server import mcp
    tools = asyncio.run(mcp.list_tools())
    names = {t.name for t in tools}
    assert {"list_tables", "describe_table", "run_query"} <= names


def test_mcp_protocol_roundtrip(tmp_path):
    """Full MCP handshake over stdio with the SDK client (real protocol)."""
    import os
    import sys

    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    async def run():
        params = StdioServerParameters(
            command=sys.executable, args=["-m", "claims_agent.mcp_server"],
            env={**os.environ, "PYTHONPATH": os.path.join(root, "src")}, cwd=root)
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                listed = await session.list_tools()
                assert {"list_tables", "describe_table", "run_query"} <= {t.name for t in listed.tools}
                ok = await session.call_tool("run_query", {"sql": "SELECT COUNT(*) AS n FROM claims"})
                assert not ok.isError
                blocked = await session.call_tool("run_query", {"sql": "DELETE FROM claims"})
                assert blocked.isError

    asyncio.run(run())
