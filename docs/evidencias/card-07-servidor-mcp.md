# Card 07 — Criar servidor MCP

**Branch/PR:** `feature/mcp-github-tools`
**Resultado esperado (Kanban):** Servidor responde ao handshake

## O que foi implementado

- `src/mcp_server/server.py` — `build_server()` monta um `MCPServer` (SDK oficial `mcp`, v2.x) chamado `radar-mcp-server`; sem tools ainda — `search_code`, `fetch_history` e `publish_comment` chegam nos cards 8, 9 e 10, registradas via `@server.tool()`
- `tests/integration/test_mcp_server.py` — handshake `initialize` via transporte em memória do próprio SDK (`mcp.shared.memory.create_client_server_memory_streams`), sem subprocesso nem stdio real

## Evidência registrada

```
tests/integration/test_mcp_server.py::test_server_responds_to_initialize_handshake PASSED
1 passed in 0.39s
```

`ClientSession.initialize()` retorna `server_info.name == "radar-mcp-server"` e `server_info.version == "0.1.0"` — confirma que o servidor aceita conexão e responde ao protocolo, não só que o processo sobe.

Suíte completa (sem o smoke test do Ollama): **52 passed in 1.59s**.

## Prompt utilizado

> "Sim, segue" (confirmação para avançar ao card 07, depois do card 06 concluído)

## Decisões técnicas

- **`mcp` v2.x, não v1** — `pip install mcp` sem pin trouxe a versão mais recente (2.1.1) direto; a classe de alto nível foi renomeada de `FastMCP` (v1, usada em boa parte dos tutoriais e no material do curso) para `MCPServer` na v2. Ficar na v2 evita começar o projeto já preso a uma versão descontinuada — mas o nome da classe diverge do que aparece em exemplos externos, documentado aqui para não confundir depois
- Teste de handshake usa `server._lowlevel_server` (atributo "privado") em vez de só `server.run_stdio_async()` — necessário para plugar streams em memória; `run_stdio_async` só aceita stdio real. Alternativa seria testar via subprocesso real, descartada por ser mais lenta e mais frágil em CI
- Nenhuma tool registrada neste card, de propósito — o objetivo declarado no Kanban é só "servidor responde ao handshake"; registrar tools vazias/fake teria sido trabalho descartável
