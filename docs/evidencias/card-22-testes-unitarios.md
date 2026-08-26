# Card 22 — Testes unitários

**Branch/PR:** `feature/unit-test-coverage`
**Resultado esperado (Kanban):** Cobrir risco e confiança → Cobertura acima de 70%

## Estado antes deste card

Os módulos nomeados por RNF-05 ("cobertura de testes acima de 70% nos módulos de risco, confiança e permissões") já estavam em **100%** desde os cards 02 e 10/17 (`domain/risk.py`, `governance/permissions.py`) — cobertura acumulada organicamente porque cada card anterior já vinha com testes próprios. A cobertura geral do projeto já estava em **94,55%**. Não havia, porém, um gate que tornasse esse número um requisito **verificável e reproduzível**, nem visibilidade dos poucos módulos com lacunas reais.

## O que foi implementado

- `pyproject.toml` (novo) — `[tool.pytest.ini_options]` com `addopts = "--cov=src --cov-report=term-missing --cov-fail-under=70"`: `pytest` sozinho, sem flags extras, agora sempre mede cobertura e falha se cair abaixo de 70% — é o comando exato que o pipeline de CI (seção 16 do PRD, card 25) vai rodar. `[tool.coverage.report]` exclui a guarda `if __name__ == "__main__":` da medição (prática padrão: scripts de entrada não são testáveis como unidade).
- `requirements.txt` ganhou `pytest-cov`.
- Fechadas as lacunas de cobertura reais que a primeira rodada do relatório revelou (94,55% → **99,09%**), uma por módulo:

| Módulo | Antes | Lacuna fechada |
|---|---|---|
| `graph/llm.py` | 73% | `build_chat_model` nunca era chamado de verdade nos testes (só mockado) — nem o caminho feliz (`ChatOllama`) nem o `NotImplementedError` de provedor não suportado tinham teste direto |
| `graph/checkpointer.py` | 0% | `build_checkpointer()` nunca era exercitado — testes sempre construíam `SqliteSaver` manualmente |
| `graph/nodes.py` | 99% | `_to_risk_item` (nunca chamado com um risco real, `analyze_impact` real ainda é stub) e o branch `requirement is None` de `retrieve_rag` |
| `mcp_server/server.py` | 77% | os dois wrappers `@mcp_server.tool()` (`search_code`/`fetch_history`) nunca eram chamados via `call_tool()` — só o handshake `initialize` tinha teste |
| `mcp_server/tools/fetch_history.py` | 95% | os `continue` de item sem `sha`/sem `number` |
| `observability/audit.py` | 98% | `continue` de linha em branco no JSONL |
| `observability/logging.py` | 97% | `configure_structured_logging()` nunca era chamado nos testes (só manualmente, card 21) |
| `rag/corpus.py` | 98% | fallback `return ""` de `_extract_field` quando o campo não existe |
| `rag/embeddings.py` | 67% | `OllamaEmbeddingFunction.name()`/`build_embedding_function()` sem teste (o `__call__`, que faz rede de verdade, continua fora — ver decisão abaixo) |
| `rag/ingest.py` | 74% | `get_client()` nunca era chamado (testes usavam `EphemeralClient` direto) |
| `rag/retriever.py` | 85% | `_get_collection()` — o caminho lazy de produção (client real + ingestão sob demanda) nunca era exercitado, só o caminho com `collection` injetado |

## O que ficou de fora, deliberadamente

- `rag/embeddings.py::OllamaEmbeddingFunction.__call__` — faria uma chamada de rede real ao Ollama; testar isso é papel do smoke test já existente (`RUN_OLLAMA_TESTS=1`), não de um teste unitário.
- `rag/ingest.py::main()` — script de linha de comando fino, já cobre `get_client`/`get_or_create_collection`/`ingest_corpus`/`build_embedding_function` individualmente; testar o `main()` em si só testaria a colagem entre eles, sem lógica própria.

## Testes adicionados

`tests/unit/test_llm.py`, `test_checkpointer.py`, `test_embeddings.py`, `test_nodes_misc.py` (novos); extensões em `test_rag_ingest.py`, `test_rag_retriever.py` (o caminho lazy de `_get_collection()`, incluindo o caso "coleção vazia → ingere sozinha"), `test_rag_corpus.py`, `test_audit.py`, `test_structured_logging.py`, `test_fetch_history.py`, `tests/integration/test_mcp_server.py` (as duas tools MCP chamadas de verdade via `call_tool()`, não só o handshake).

`pytest -q`: **163 passed, 3 skipped** (Ollama real), **99,09% de cobertura total** — gate de 70% (`--cov-fail-under=70`) verificado passando. `ruff check`: sem apontamentos.

## Decisões técnicas

- Gate de cobertura **geral** (`--cov=src`), não restrito aos três módulos de RNF-05 — mais simples de configurar e de raciocinar sobre, e como o projeto já está em 99%, um gate mais permissivo (70% global) não mascara regressão nos módulos críticos: eles estão em 100% e qualquer queda ali seria uma queda visível no relatório `term-missing`, mesmo sem um gate por-módulo.
- `--cov-fail-under=70` em `addopts` (aplica a **todo** `pytest`, não só numa invocação específica de CI) — decisão consciente: torna o requisito da RNF-05 impossível de esquecer localmente, não só no pipeline. Rodar um subconjunto de testes (`pytest tests/unit/test_x.py`) vai falhar a asserção de cobertura por medir só aquele arquivo — comportamento esperado do `pytest-cov`, não um bug; a suíte completa é que precisa passar no gate.
