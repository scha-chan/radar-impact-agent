"""Servidor MCP próprio do RADAR.

Expõe as tools de integração com o GitHub e com o corpus de padrões de
impacto ao agente (RF-03, RF-08), via Model Context Protocol. Este card
cria só o servidor e confirma que ele responde ao handshake `initialize`
— as tools (`search_code`, `fetch_history`, `publish_comment`) chegam
nos cards 8, 9 e 10, registradas aqui via `@server.tool()`.

SDK oficial `mcp` (v2.x) — a classe de alto nível chama-se `MCPServer`
(renomeada de `FastMCP` na v2; ver aviso de migração do pacote).
"""

from __future__ import annotations

import os

from mcp.server.mcpserver import MCPServer

from src import config  # noqa: F401 - carrega .env como efeito colateral do import
from src.mcp_server.tools.fetch_history import fetch_history as _fetch_history
from src.mcp_server.tools.search_code import search_code as _search_code

# publish_comment não é exposta como tool MCP genérica: ela opera sobre o
# AgentState inteiro (para a checagem de autorização RF-08.2/RF-08.3), não
# sobre um payload solto que um client MCP externo poderia montar sem as
# garantias de aprovação humana. É chamada só pelo node do grafo
# (graph/nodes.py::publish_comment), nunca via protocolo MCP.

SERVER_NAME = "radar-mcp-server"
SERVER_VERSION = "0.1.0"


def build_server() -> MCPServer:
    mcp_server = MCPServer(name=SERVER_NAME, version=SERVER_VERSION)

    @mcp_server.tool()
    def search_code(search_terms: list[str], repo: str) -> list[dict]:
        """Busca termos no código-fonte de um repositório GitHub; retorna arquivos e trechos."""
        matches = _search_code(search_terms, repo=repo, github_token=os.getenv("GITHUB_TOKEN", ""))
        return [match.model_dump() for match in matches]

    @mcp_server.tool()
    def fetch_history(search_terms: list[str], repo: str) -> list[dict]:
        """Busca commits e PRs recentes de um repositório GitHub relacionados aos termos."""
        entries = _fetch_history(search_terms, repo=repo, github_token=os.getenv("GITHUB_TOKEN", ""))
        return [entry.model_dump() for entry in entries]

    return mcp_server


server = build_server()


if __name__ == "__main__":
    server.run()
