# Card 19 — Logs estruturados

**Branch/PR:** `feature/structured-logging`
**Resultado esperado (Kanban):** Primeiro sinal → JSON por node com duração

## O que foi implementado

- `src/observability/logging.py` (novo):
  - `configure_structured_logging()` — configura `structlog` para emitir uma linha JSON por evento (timestamp ISO8601 UTC, nível, campos estruturados). Chamada uma vez na inicialização do processo (a API do card 30 vai chamar isso no startup).
  - `log_node_execution(node_name, fn)` — envolve um node do grafo e emite o evento `node_completed` (RF-09.1) após cada execução: `session_id`, `correlation_id`, `node`, `status`, `duration_ms`, mais uma contagem automática (`<campo>_count`) para todo campo de lista que o node devolveu (generaliza o `matches_found` do exemplo da seção 14 do PRD sem precisar de código específico por node).
- `src/graph/build.py` — todos os 12 nodes do grafo passam por `log_node_execution` num único laço, em vez de cada `graph.add_node(...)` individual. Um ponto de instrumentação só, em vez de logging espalhado pelos nodes em `nodes.py` — todo node novo que entrar no grafo já sai instrumentado.
- `requirements.txt` ganhou `structlog`.

## `GraphInterrupt` não é um erro

`human_approval` (card 15) pausa lançando `GraphInterrupt` internamente — é assim que o LangGraph implementa `interrupt()`. Um wrapper genérico que capturasse `Exception` sem distinguir esse caso logaria toda pausa como `status="error"`, o que seria enganoso para quem for ler o log depois tentando reconstruir uma execução (seção 14 do PRD, "investigação demonstrada" — card 21). `log_node_execution` trata `GraphInterrupt` à parte, com `status="paused"` e nível `info`, e relança a exceção sem alterá-la — o wrapper só observa.

## Testes

`tests/unit/test_structured_logging.py` (novo) — usa `structlog.testing.capture_logs()` (não precisa de `configure_structured_logging()`, que só afeta o *renderer* de saída, não a emissão do evento):

- evento `node_completed` tem todos os campos exigidos por RF-09.1 e não altera o valor de retorno do node;
- campos de lista no retorno viram `<campo>_count` automaticamente;
- exceção genérica → `status="error"`, nível `error`, e a exceção é relançada;
- `GraphInterrupt` → `status="paused"`, nível `info`, também relançada.

`tests/integration/test_node_logging.py` (novo) — roda o grafo real (`build_graph().invoke()`, LLM mockado) e confirma que **cada node realmente alcançado** emite seu `node_completed` (não só o wrapper isolado): os oito nodes do caminho de baixa confiança, `human_approval` com `status="paused"`, e `publish_comment` **nunca** aparece no log (não foi alcançado, a execução pausou antes).

`pytest -q`: 128 passed, 3 skipped (Ollama real). `ruff check`: sem apontamentos. Smoke test manual confirma o JSON renderizado batendo com o formato da seção 14 do PRD.

## Decisões técnicas

- Instrumentação centralizada em `build.py` (decorador aplicado na montagem do grafo), não espalhada em cada função de `nodes.py` — motivo duplo: (1) garante formato uniforme entre todos os nodes sem depender de disciplina manual; (2) mantém `nodes.py` livre de código de observabilidade misturado com a lógica de negócio, que já está carregada (LLM, tools, permissões).
- Estava fora de escopo deste card: `agent_version`/`prompt_version`/`policy_version` como atributos fixos (RF-09.5) — esses campos não existem no `AgentState` atual; fazem parte do card 35 (extensão pós-rubrica, risco aceito de pendência conforme seção 23 do PRD). O log deste card cobre exatamente o que RF-09.1 e o Kanban pedem: "JSON por node com duração".
- Trilha de auditoria (JSONL, segundo sinal) e a correlação formal entre os dois sinais ficam para o card 20.
