# Card 17 — Implementar permissões de tool

**Branch/PR:** `feature/tool-executor`
**Resultado esperado (Kanban):** Autorizar antes de executar → Chamada não autorizada recusada

## Contexto: o que já existia

`src/governance/permissions.py` (cards 10/11) já tinha `ToolPermission` e `authorize()`, mas só protegiam `publish_comment` — a própria tool chamava `authorize()` internamente antes de agir. `search_code` e `fetch_history` eram chamadas direto pelos nodes, sem passar por nenhuma checagem de permissão: funcionavam porque são só leitura, não porque houvesse alguma barreira as impedindo de rodar sem autorização declarada.

## O que foi implementado

- `src/governance/tool_executor.py` (novo) — classe `ToolExecutor`: um registro de `ToolPermission` por nome de tool (`register`) e um ponto único de validação antes de qualquer chamada (`execute`). Uma tool sem permissão registrada é **recusada** (`PermissionDeniedError`) — o `call` nunca chega a ser invocado.
- `SEARCH_CODE_PERMISSION` (`src/mcp_server/tools/search_code.py`) e `FETCH_HISTORY_PERMISSION` (`src/mcp_server/tools/fetch_history.py`) — ambas `destructive=False`, leitura, mesmo padrão de `PUBLISH_COMMENT_PERMISSION` (card 10).
- `src/graph/nodes.py` monta um `ToolExecutor` de módulo (`_tool_executor`) e registra as três permissões; `search_codebase`, `fetch_history` e `publish_comment` passam a chamar a tool através de `_tool_executor.execute(nome, state, lambda: ...)` em vez de chamar a função direto.
- `retrieve_rag` **não** passa pelo executor — não é uma tool MCP externa (é ChromaDB local, card 13), então fica fora do escopo de "tool com efeito externo" que a seção 13 do PRD descreve. Documentado no docstring do node.

## Por que `publish_comment` ainda chama `authorize()` duas vezes

A tool (`mcp_server/tools/publish_comment.py`) mantém sua própria chamada interna a `authorize()`, já testada isoladamente em `tests/unit/test_publish_comment.py` (chama a função direto, sem passar pelo node nem pelo executor). Rotear pelo `ToolExecutor` no node adiciona uma segunda checagem, com a mesma permissão e o mesmo resultado — redundante, mas deliberado: defesa em profundidade. Se algum dia a tool for chamada de outro lugar que não seja `graph/nodes.py` (ex.: diretamente via MCP por um client externo), ela continua protegida sozinha.

## Testes

- `tests/unit/test_tool_executor.py` (novo) — tool registrada executa; tool **não registrada** é recusada sem chamar o `call` (a prova central do card); `authorize()` é aplicado de verdade para uma tool destrutiva registrada (nega sem aprovação, permite aprovada); registrar de novo o mesmo nome sobrescreve a permissão anterior.
- `tests/unit/test_nodes_tool_executor_wiring.py` (novo) — substitui `nodes._tool_executor` por um executor vazio (via monkeypatch) e confirma que `search_codebase`, `fetch_history` e `publish_comment` **realmente** dependem dele (levantam/retornam recusa), não só coincidem por acaso com o comportamento esperado. Sem esse teste, seria possível reescrever os nodes chamando a tool direto de novo e nenhum teste apontaria a regressão.

`pytest -q`: 113 passed, 3 skipped (Ollama real). `ruff check`: sem apontamentos.

## Decisões técnicas

- `ToolExecutor` fica em `governance/`, não em `mcp_server/` — é uma política de autorização (mesma família de `permissions.py`), não faz parte do protocolo MCP em si; as tools que ele protege é que moram em `mcp_server/tools/`.
- Registro de permissões acontece em `graph/nodes.py`, não em `governance/tool_executor.py` — evitei um factory central importando as três tools (`search_code`, `fetch_history`, `publish_comment`) de dentro de `governance/`, o que inverteria a direção de dependência esperada (`governance` não deveria conhecer tools concretas). `nodes.py` já importa as três, então é o lugar natural para compor o registro.
