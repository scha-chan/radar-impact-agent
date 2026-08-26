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

from mcp.server.mcpserver import MCPServer

SERVER_NAME = "radar-mcp-server"
SERVER_VERSION = "0.1.0"


def build_server() -> MCPServer:
    return MCPServer(name=SERVER_NAME, version=SERVER_VERSION)


server = build_server()


if __name__ == "__main__":
    server.run()
