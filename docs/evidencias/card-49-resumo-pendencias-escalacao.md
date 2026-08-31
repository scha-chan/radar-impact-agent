# Card 49 — Resumo (gerado por IA) das pendências que causaram a escalação

**Branch/PR:** `feature/review-brief` → PR para `develop` (stacked sobre 44–48)
**Resultado esperado (Kanban):** o revisor abre "Aprovações pendentes" e entende, sem clicar em nada, o que está sendo pedido, por que o sistema não decidiu sozinho, e o que preencher no campo de contexto da reanálise (card 47).

## Problema

O painel de aprovações pendentes mostrava só `session_id · risco · confiança`. Feedback do uso: *"Não sei o que preciso aprovar, o que tenho que preencher no contexto?"*. O `escalation_reason` do painel de detalhe (card 47) é uma frase fixa por decisão de auditoria — não explica **esta** mudança.

## O que foi implementado

### Node LLM `brief_escalation` + prompt `05-review-brief`

- **`src/graph/escalation.py`** (novo) — `escalation_reason(last_decision)`, `last_escalation_decision(entries)` e `describe_gaps(state_like, last_decision)`, movidos de `src/api/app.py` (`_ESCALATION_REASONS`/`_derive_gaps`, card 47). Agora o node e a API usam o mesmo código (de-dup, no espírito do card 48). `app.py` importa daqui.
- **`ReviewBrief`** (`src/graph/state.py`) — `summary` (2–3 frases) + `suggested_context` (1–2 frases sobre o que colar na reanálise). `AgentState` += `review_brief: str | None`.
- **`REVIEW_BRIEF_SYSTEM` + `build_review_brief_prompt`** (`src/graph/prompts.py`, doc `docs/prompts/05-review-brief.md`) — recebe requisito, risco/`risk_assessed`/confiança/threshold, motivo da escalação, impactos, riscos e a lista de "o que faltou". Regras: português, sem inventar, **não sugerir dispensar revisão** (mesma contenção dos prompts 03/04).
- **`brief_escalation`** (`src/graph/nodes.py`) — entre `decide_autonomy` e `human_approval` (`route_after_decision` → `"brief_escalation"`; `build.py` liga `brief_escalation → human_approval`). Monta `gaps`/`reason`, chama `with_structured_output(ReviewBrief)`, `_set_gen_ai_span_attributes()`. Concatena `summary` + "O que ajudaria numa reanálise: {suggested_context}" em `review_brief`. Falha do LLM ou `requirement` ausente → texto de fallback determinístico; a escalação nunca é bloqueada. Roda **de novo a cada rodada de reanálise** (card 47), atualizando o resumo.

### API

- **`PendingApproval.review_brief`** e **`EscalationDetail.review_brief`** (`src/api/schemas.py`).
- `list_approvals` passa a ler o state congelado de cada sessão pendente (`graph.get_state(config).values`, via `_review_brief_for`) para trazer o `review_brief` já na lista — antes só usava a trilha de auditoria. `get_escalation_detail` (card 47) só adiciona o campo.

### Frontend (`src/api/static/ts/*`, JS recompilado)

- `types.ts`: `review_brief` nos dois contratos.
- `app.ts`: `reviewBriefBlock(brief)` — bloco `bg-amber-50` com uma linha por parágrafo. Renderizado no topo de cada card de aprovação pendente (primeira coisa que o revisor lê) e no topo do painel de detalhe.

## Custo no grafo

+1 passo por escalação. Caminho de escalação do 1º ciclo ≈ 11 passos (< `max_steps=12`); as rodadas de reanálise já têm folga por `_STEPS_PER_REANALYSIS=6` (card 47).

## Testes

- **`tests/unit/test_escalation.py`** (novo): `escalation_reason`, `last_escalation_decision` (ignora entradas não-escalação), `describe_gaps` (lacunas + específicas de decisão; vazio quando tudo presente).
- **`tests/integration/test_review_brief.py`** (novo): escalação real popula `review_brief` (summary + suggested_context concatenados); falha do LLM → fallback determinístico com motivo/lacunas; no-op quando `human_review_required=False`; `requirement=None` → fallback sem chamar o modelo; reanálise (card 47) regenera o brief.
- **`tests/e2e/test_api.py`**: item de `GET /approvals` e `GET /approvals/{id}` trazem `review_brief` não vazio.
- **`tests/unit/test_prompts.py`**: `build_review_brief_prompt` carrega requisito, motivo, lacunas, e a instrução de não dispensar revisão.
- **`tests/integration/test_graph.py`**: `route_after_decision` com revisão → `"brief_escalation"`.
- **`tests/helpers.py`**: `mock_llm` trata o schema `ReviewBrief` (`review_summary`/`suggested_context`).

`python -m pytest -q`: **360 passed, 6 skipped**, cobertura **99,52%** (100% em `nodes.py` / `prompts.py` / `escalation.py` / `app.py` / `schemas.py` / `state.py` / `build.py`). `ruff check` / `format --check`: limpos. `npm run build` + `tsc --noEmit`: sem erro.

Smoke com Ollama `mistral` real, requisito sem evidência: o brief saiu como *"Adição de autenticação por 2FA nos usuários existentes: análise não produziu impactos nem riscos devido a falta de evidência de código, padrões de impacto e histórico de mudanças. […] O que ajudaria numa reanálise: Informe o local do código relacionado à autenticação dos usuários existentes."*
