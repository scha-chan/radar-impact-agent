# Card 46 — Distinguir "risco baixo" de "não avaliado" quando falta evidência

**Branch/PR:** `feature/risk-not-assessed` → PR para `develop` (stacked sobre os cards 44/45)
**Resultado esperado (Kanban):** a tela e o parecer não mostram mais "risco: Baixo" quando, na verdade, não houve o que avaliar.

## Contexto: o que acontecia

Quando a análise degrada por falta de evidência (`search_codebase`/`retrieve_rag`/`fetch_history` voltam vazios — sem `GITHUB_TOKEN`, sem `nomic-embed-text`, ou Code Search não indexou), `analyze_impact` devolve `impacts: []` / `risks: []` por design (RF-04.5). Aí `aggregate_risk_level([])` retorna `LOW` e a tela mostrava **"risco: Baixo"** — que se lê como "mudança segura", quando o real é "não deu para avaliar".

Reproduzido: os dois requisitos de exemplo (um plausível de risco alto, um fora do corpus) voltaram ambos `risco: Baixo`, confiança 45 e 10. A confiança baixa sinalizava a degradação; o nível de risco, não.

Só o caminho de orçamento estourado (card 35) tinha um piso `MEDIUM` + decisão de auditoria distinta (`ESCALATED_BUDGET_EXCEEDED`). O caminho "sem evidência" não tinha equivalente.

## O que foi implementado

Sinal explícito **`risk_assessed`**, decidido em `decide_autonomy` e propagado até a tela.

- **`decide_autonomy`** (`src/graph/nodes.py`): `risk_assessed = há impacto/risco identificado **ou** o risco já era ≥ MEDIUM **ou** nem precisou de revisão (confiança alta = veredito real)`. Quando `False` **e** o parecer escala **e** não é o caso de orçamento estourado: aplica o mesmo piso `MEDIUM` (nunca rebaixa um risco já maior) e registra `ESCALATED_NOT_ASSESSED` na auditoria (em vez de `ESCALATED`).
- **`AgentState.risk_assessed` / `ImpactAnalysis.risk_assessed`** (`src/graph/state.py`) — default `True`; `_build_impact_analysis` (card 45) copia do state.
- **`AuditDecision`** (`src/observability/audit.py`): novo valor `ESCALATED_NOT_ASSESSED`, incluído em `_PENDING_DECISIONS` para a sessão aparecer no painel `GET /approvals`.
- **`AnalyzeResponse.risk_assessed` / `PendingApproval.risk_assessed`** (`src/api/schemas.py`, `src/api/app.py`) — a resposta do `/analyze` e cada item do painel carregam o sinal. No painel, deriva da decisão de auditoria (`risk_assessed = decision == "ESCALATED"`), então `ESCALATED_BUDGET_EXCEEDED` também conta como não avaliado.
- **Tela** (`src/api/static/ts/{types,i18n,app}.ts`, JS recompilado): `riskDisplayLabel`/`riskDisplayClass` mostram **"não avaliado"** (cinza, sem cor de severidade) no painel de resultado e nos cards de aprovação pendente quando `risk_assessed` é `false`.
- **Comentário publicado** (`render_comment`, card 45): a linha de risco vira `não avaliado — evidência insuficiente (piso MEDIUM aplicado)` quando `analysis.risk_assessed` é `False`.

## Decisões técnicas

- **Piso `MEDIUM` + flag, não só flag.** Um consumidor que só olha `risk_level` (API, auditoria) não deve ver "LOW" num parecer que não foi avaliado — mesma postura do card 35. A flag é a honestidade extra para a UI e o comentário mostrarem "não avaliado" em vez do piso.
- **`risk_assessed=True` no auto-publish de confiança alta.** Confiança alta sem riscos é um veredito real ("olhamos, nada preocupante") — a tela mostra "Baixo", não "não avaliado". Só a combinação *escalou + sem impacto/risco + risco baixo* é tratada como não avaliada.
- **Não rebaixa risco elevado.** Se `risk_level` já era HIGH/CRITICAL, houve sinal — `risk_assessed=True`, sem piso.

## Testes

- **`tests/unit/test_decide_autonomy.py`** (novos): não avaliado quando escala sem impacto/risco (piso MEDIUM); avaliado quando há risco, quando há só impacto, e no auto-publish de confiança alta; risco já elevado não é rebaixado.
- **`tests/integration/test_audit_trail.py`**: `ESCALATED_NOT_ASSESSED` registrado sem impacto/risco; `ESCALATED` (plano) quando há risco; correlação no grafo completo passa a esperar `ESCALATED_NOT_ASSESSED`.
- **`tests/integration/test_graph.py`**: o cenário "escala sem evidência" agora espera `risk_level == "MEDIUM"` e `risk_assessed is False`.
- **`tests/unit/test_compose_report.py`**: `render_comment` marca "não avaliado" quando `risk_assessed=False`.
- **`tests/e2e/test_api.py`**: `/analyze` sem evidência devolve `risk_assessed=False`, e o item do painel `/approvals` também.

`python -m pytest -q`: **341 passed, 6 skipped**, cobertura **99,41%** (100% em `nodes.py` / `state.py` / `audit.py` / `app.py` / `schemas.py` / `publish_comment.py`). `ruff check` / `ruff format --check`: sem apontamentos. `tsc` (`npm run build`): sem erro de tipo. Smoke pelo grafo real: requisito sem evidência → `risk_level MEDIUM`, `risk_assessed False`, auditoria `ESCALATED_NOT_ASSESSED`.
