# Card 03 — Definir o AgentState tipado

**Branch/PR:** `feature/langgraph-agente` → [PR #3](https://github.com/scha-chan/radar-impact-agent/pull/3)
**Resultado esperado (Kanban):** `graph/state.py`

## O que foi implementado

`src/graph/state.py`:

- `AgentState` (`TypedDict`) — todos os campos da seção 8 do PRD: identificação/rastreio, entrada, controle de fluxo, evidência coletada em paralelo, análise, decisão e saída
- Modelos Pydantic v2 que compõem o state: `Requirement`, `CodeMatch`, `PatternChunk`, `HistoryEntry`, `EvidenceSource`, `Impact`, `Risk`, `ImpactAnalysis` — replicam o schema do exemplo JSON da seção 8
- `create_initial_state()` — monta o estado inicial a partir do requisito bruto; `session_id`/`correlation_id` compartilhados desde o início, para correlação de observabilidade (seção 14)

`tests/unit/test_state.py`: validação de `feature_type` e `confidence` fora do intervalo, payload completo de `ImpactAnalysis`, defaults de `create_initial_state`, independência entre `session_id`s gerados.

## Prompt utilizado

> "Crie branch para o card 3 e realize a implementação"

## Decisões técnicas

- `AgentState` como `TypedDict` (exigência do LangGraph para estado compartilhado), mas os campos internos usam modelos Pydantic para validação — decisão não explicitada no PRD, mas necessária para reconciliar "TypedDict porque é o que o LangGraph espera" com "Pydantic v2" na stack (seção 7)
- Literais de string (`SeverityLevel`, `RiskLevelLiteral` etc.) em vez de reusar os `IntEnum` de `src/domain/risk.py` — o contrato externo (JSON publicado na Issue) usa strings, e acoplar os dois desde já criaria dependência prematura entre `graph/` e `domain/`; a conversão explícita foi resolvida no card 04
