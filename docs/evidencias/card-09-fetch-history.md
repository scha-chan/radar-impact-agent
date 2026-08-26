# Card 09 — Implementar `fetch_history`

**Branch/PR:** `feature/mcp-github-tools`
**Resultado esperado (Kanban):** Commits e PRs relacionados

## O que foi implementado

- `src/mcp_server/tools/_http.py` — **extraído** de `search_code.py`: `get_with_retry()`, GET com timeout/retry/backoff compartilhado (RF-03.5). Segundo uso idêntico da mesma lógica justificou a extração; `search_code.py` foi refatorado para usá-lo, sem mudar comportamento (6 testes existentes continuam verdes sem alteração)
- `src/mcp_server/tools/fetch_history.py` — busca commits (`/search/commits`) e PRs (`/search/issues?type:pr`) por termo do requisito, combina e deduplica por `ref`
- `server.py` — `fetch_history` registrada como tool MCP
- `graph/nodes.py::fetch_history` — reescrito de stub para real; popula `change_history` e `evidence_sources` (`type="history"`)

## Decisão de arquitetura que não estava óbvia no PRD

RF-03.3 diz que `fetch_history` busca commits/PRs "que tocaram os arquivos encontrados" — leitura literal sugeriria depender da saída de `search_code`. Mas os três nodes de evidência rodam em **paralelo** via `Send` (seção 7, já implementado nos cards 04-05): `fetch_history` não pode esperar `search_code` terminar sem quebrar essa paralelização.

Resolvido usando os mesmos `search_terms` do requisito como entrada de `fetch_history` (em vez dos arquivos de `code_matches`) — as duas tools buscam endpoints diferentes da mesma API a partir do mesmo input, de forma independente; `analyze_impact` (card 14) correlaciona os dois depois. Preserva a arquitetura já testada em vez de forçar uma dependência sequencial que exigiria redesenhar o fan-out.

## Testes

- `tests/unit/test_fetch_history.py` — 5 testes com `respx`: vazio sem repo/token, parse de commit+PR, dedupe entre termos, fallback quando busca de commit falha (PR continua funcionando), respeito a `max_results`
- `tests/integration/test_fetch_history_github.py` — smoke test contra a API real, pulado por padrão (`RUN_GITHUB_TESTS=1`)
- `tests/integration/test_evidence_parallelism.py` (card 05) — **precisou de correção**: a suposição original ("os três nodes de evidência têm latência simulada") ficou falsa depois que `search_codebase` (card 08) e `fetch_history` (este card) viraram reais. Corrigido mockando as chamadas de rede subjacentes com a mesma latência simulada, preservando o benchmark original

## Evidência registrada

Smoke test contra a API real (repo `scha-chan/radar-impact-agent`, termo `"risk"`):

```
tests/integration/test_fetch_history_github.py::test_fetch_history_against_real_github_repo PASSED
1 passed in 0.92s
```

Resultado real (chamada manual, fora da suíte):

```
pr PR #2 feat(domain): matriz de risco e formula de confianca
pr PR #5 feat(graph): esqueleto do grafo com nodes stub
pr PR #3 feat(graph): AgentState tipado e contrato do grafo
total: 3
```

3 PRs relacionados encontrados de verdade (busca de commits voltou vazia — mesma indexação em atraso documentada no card 08).

Suíte completa (sem os três smoke tests): **63 passed in 1.58s**.

## Prompt utilizado

> "Sim, segue"

## Decisões técnicas

- Extração de `_http.get_with_retry()` no meio do card, não isolada em um card próprio — a duplicação só ficou visível ao escrever a segunda tool; refatorar imediatamente evita a terceira tool (card 10, `publish_comment`) copiar a mesma lógica pela segunda vez
- `_search_commits`/`_search_prs` combinados numa única lista antes do dedupe/corte por `max_results` — favorece diversidade (mistura commits e PRs) em vez de esgotar o orçamento só com um tipo
- Sem correlação entre `code_matches` e `change_history` neste card — a correlação de evidências (RF-04.5, cada afirmação do parecer aponta sua origem) é responsabilidade de `analyze_impact` (card 14), não das tools de coleta
