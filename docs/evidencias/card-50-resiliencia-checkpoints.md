# Card 50 — Resiliência a checkpoints antigos e órfãos no fluxo de aprovação

**Branch/PR:** `feature/resilient-approvals` → PR para `develop`
**Resultado esperado (Kanban):** o painel de aprovações não lista sessões sobre as quais não dá para agir, e retomar uma sessão de uma versão anterior do agente devolve um erro claro (409), não um 500.

## O que acontecia

Depois de várias execuções de teste ao longo do desenvolvimento (cards 43–49, que mudaram a topologia do grafo e adicionaram chaves ao `AgentState`), o `audit/trail.jsonl` e o `radar_checkpoints.db` locais acumularam sessões escaladas de versões diferentes do código:

1. **Sessões fantasma no painel** — `GET /approvals` deriva de `audit/trail.jsonl`, que persiste em disco. Uma sessão que escalou numa execução antiga e nunca foi resolvida continua "pendente" para sempre, mesmo que o checkpoint dela não exista mais (ex.: o banco foi recriado).
2. **Erro 500 ao aprovar/rejeitar** — uma sessão pausada por uma versão antiga do grafo tem um `AgentState` congelado sem as chaves novas (`reanalysis_requested` do card 47, `risk_assessed` do 46, `review_brief` do 49, `reviewer_context`/`review_rounds` do 47, `github_repo` do 43). Ao retomar, `route_after_approval` fazia `state["reanalysis_requested"]` → `KeyError` → 500.

## O que foi implementado

### API (`src/api/app.py`)

- **`GET /approvals`** só lista sessões cujo checkpoint ainda existe e está de fato pausado em `human_approval` (`_is_paused_for_approval` — `snapshot.next == ("human_approval",)`). As que a trilha marca como escaladas mas cujo checkpoint sumiu não aparecem, porque não há como agir sobre elas. (Reaproveita o mesmo `snapshot` para ler o `review_brief`, sem uma segunda chamada.)
- **`POST /approvals/{session_id}`**:
  - `_backfill_missing_state` — antes de retomar, completa o state congelado com o default de cada chave de `_RESUME_SCHEMA_DEFAULTS` que estiver faltando (via `graph.update_state`), com um `logger.warning("approval_state_backfilled")`. Isso **conserta** sessões antigas em vez de deixá-las quebradas.
  - A chamada `graph.invoke(Command(resume=...))` está num `try/except`: qualquer erro de retomada vira **409** ("não foi possível retomar a sessão — provavelmente criada por uma versão anterior; descarte-a e submeta de novo"), com `logger.exception`, nunca um 500.

### Grafo (`src/graph/nodes.py`)

Os pontos que leem chaves novas do `AgentState` no caminho de retomada passaram de `state["x"]` para `state.get("x", <default>)` — `route_after_approval`, o payload do `interrupt()` em `human_approval`, `_request_reanalysis`, `_known_evidence_refs`/`analyze_impact` (contexto do revisor) e `_build_impact_analysis` (`risk_assessed`). Defesa em profundidade: mesmo um `Command(resume=...)` direto sobre um state incompleto (fora da API) não quebra.

### Isolamento de teste

`tests/integration/test_reviewer_action.py` passou a mockar as três fontes de evidência (`_no_evidence`): sem isso, os testes dependiam de `GITHUB_TOKEN` não estar no `.env` e de o `chroma/` local estar vazio — o que deixou de ser verdade depois que a interface foi exercitada localmente.

## Testes

- **`tests/e2e/test_api.py`** (novos): sessão na trilha sem checkpoint vivo → **não** aparece em `GET /approvals`; `submit_approval` chama o backfill quando falta chave no state congelado e ainda resolve (200); erro na retomada → **409**, não 500.
- Os testes existentes de `/approvals` (aprovar/rejeitar/reanalisar, 404, limite) seguem verdes.

`python -m pytest -q`: **390 passed, 6 skipped**, cobertura **99,47%** (100% em `src/api/app.py` e `src/graph/nodes.py`). `ruff check` / `format --check`: sem apontamentos.

## Limpeza local (não faz parte do código)

Os arquivos de estado persistente são todos gitignorados; para começar do zero: parar o servidor e apagar `radar_checkpoints.db*`, `audit/` e `chroma/`.
