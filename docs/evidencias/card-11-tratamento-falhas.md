# Card 11 — Tratamento de falhas nas tools

**Branch/PR:** `feature/mcp-github-tools`
**Resultado esperado (Kanban):** Cenário 4 reproduzível

## O que foi implementado

Timeout, retry e fallback (RF-03.5) já existiam desde os cards 08-09; faltava o sinal de que uma tool caiu em fallback chegar até `score_risk`, para a fórmula de confiança (seção 11 do PRD) aplicar a dedução de −15 por tool que falhou — até este card, `tools_failed_with_fallback` estava hardcoded em `0` em `score_risk` (card 04).

- `src/mcp_server/tools/_http.py` — `get_with_retry()` ganhou `on_exhausted: Callable | None`, chamado quando as tentativas se esgotam
- `search_code()`/`fetch_history()` — novo parâmetro opcional `failures: list[str] | None`; quando informado, recebe uma entrada por termo/endpoint que esgotou as tentativas. Backward-compatible: chamadores que não passam `failures` (a tool MCP registrada em `server.py`) continuam funcionando sem mudança
- `src/graph/state.py` — `tools_failed: Annotated[list[str], operator.add]` no `AgentState`, mesmo padrão de reducer de `evidence_sources` (card 08) — `search_codebase` e `fetch_history` podem escrever aqui em paralelo
- `graph/nodes.py::search_codebase`/`fetch_history` — passam uma lista `failures` real para as tools e traduzem em `tools_failed` no state
- `graph/nodes.py::score_risk` — `tools_failed_with_fallback=len(state["tools_failed"])`, real desde agora

## Teste principal: Cenário 4 reproduzido pelo grafo real

`tests/integration/test_scenario_4_resilience.py` — não testa a tool isolada, invoca `build_graph().invoke()` ponta a ponta com `search_code` batendo num 403 (rate limit) consistente via `respx`:

- **Timeout respeitado, dois retries com backoff:** `code_route.call_count == 3` (1 tentativa original + 2 retries)
- **Fallback para análise sem evidência de código:** `code_matches == []`, `"search_code" in tools_failed`
- **Dedução de confiança:** `100 − 20 (requisito curto) − 25 (sem code_matches) − 15 (tool falhou) − 20 (sem RAG) − 10 (menos de 2 fontes) = 10` — batido exatamente contra o valor real calculado por `score_risk`
- **Escalação automática:** `human_review_required is True`, `published_comment_url is None`

## Testes complementares

- `tests/unit/test_search_code.py` — 2 novos: registra falha ao esgotar tentativas; **não** registra falha quando a busca teve sucesso mas voltou vazia (distinção importante: "não encontrou nada" ≠ "a tool falhou")
- `tests/unit/test_fetch_history.py` — 1 novo: registra falha nos dois endpoints (`commit` e `pr`) separadamente

Suíte completa (sem os três smoke tests contra APIs reais): **78 passed in 2.25s**.

## Prompt utilizado

> "Sim, segue"

## Decisões técnicas

- `failures` como parâmetro opcional em vez de mudar o tipo de retorno das tools (`list[CodeMatch]` → algum wrapper com `.failed`) — evita quebrar a assinatura usada pela tool MCP registrada em `server.py` e pelos testes já existentes dos cards 08-09; callback `on_exhausted` em `_http.py` mantém a mudança isolada num único ponto
- Distinção deliberada entre "0 resultados" (sucesso legítimo, sem dedução extra além da já prevista por `code_matches_found=False`) e "falha após esgotar retries" (dedução adicional de −15) — sem isso, uma tool saudável que não encontra nada seria penalizada como se tivesse quebrado
- Teste do cenário 4 calcula a dedução de confiança passo a passo no comentário e bate contra o valor real, em vez de só verificar "confidence baixo" — torna a fórmula da seção 11 auditável a partir do teste, não só a conclusão qualitativa
