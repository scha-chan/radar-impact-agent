"""RF (seção 7 do PRD, card 07): o servidor MCP responde ao handshake.

Usa transporte em memória do próprio SDK (`mcp.shared.memory`) — sem
subprocesso, sem stdio real, mais rápido e determinístico para CI.
"""

import anyio
import httpx
import pytest
import respx
from mcp import ClientSession
from mcp.shared import memory as mcp_memory

from src.mcp_server.server import SERVER_NAME, SERVER_VERSION, build_server


@pytest.mark.anyio
async def test_server_responds_to_initialize_handshake():
    server = build_server()

    async with mcp_memory.create_client_server_memory_streams() as (
        client_streams,
        server_streams,
    ):
        client_read, client_write = client_streams
        server_read, server_write = server_streams

        async with anyio.create_task_group() as tg:

            async def run_server() -> None:
                await server._lowlevel_server.run(
                    server_read,
                    server_write,
                    server._lowlevel_server.create_initialization_options(),
                )

            tg.start_soon(run_server)

            async with ClientSession(client_read, client_write) as session:
                result = await session.initialize()

                assert result.server_info.name == SERVER_NAME
                assert result.server_info.version == SERVER_VERSION

                tg.cancel_scope.cancel()


@pytest.mark.anyio
@respx.mock
async def test_search_code_tool_returns_matches_as_dicts(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    respx.get("https://api.github.com/search/code").mock(
        return_value=httpx.Response(
            200, json={"items": [{"path": "src/domain/risk.py", "text_matches": []}]}
        )
    )
    server = build_server()

    result = await server.call_tool("search_code", {"search_terms": ["risk"], "repo": "owner/repo"})

    assert result.structured_content["result"] == [
        {"file": "src/domain/risk.py", "snippet": "", "line": None}
    ]


@pytest.mark.anyio
@respx.mock
async def test_fetch_history_tool_returns_entries_as_dicts(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    respx.get("https://api.github.com/search/commits").mock(
        return_value=httpx.Response(200, json={"items": []})
    )
    respx.get("https://api.github.com/search/issues").mock(
        return_value=httpx.Response(200, json={"items": [{"number": 7, "title": "x"}]})
    )
    server = build_server()

    result = await server.call_tool("fetch_history", {"search_terms": ["risk"], "repo": "owner/repo"})

    assert result.structured_content["result"] == [
        {"type": "pr", "ref": "PR #7", "description": "x"}
    ]


@pytest.fixture
def anyio_backend():
    return "asyncio"
