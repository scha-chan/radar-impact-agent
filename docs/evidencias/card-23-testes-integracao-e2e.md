# Card 23 — Testes de integração e E2E

**Branch/PR:** `feature/scenario-2-integration-test`
**Resultado esperado (Kanban):** Cobrir os quatro cenários → Suíte verde

## Estado antes deste card

Três dos quatro cenários da seção 12 do PRD já tinham teste de integração dedicado, cada um vindo do card que os motivou:

| Cenário | Teste | Card de origem |
|---|---|---|
| 1 — Fluxo principal (feliz) | `tests/integration/test_scenario_1_happy_path.py` | 14 |
| 2 — Risco alto com escalação | **faltando** | — |
| 3 — Entrada adversarial | `tests/integration/test_scenario_3_adversarial.py` | 18 |
| 4 — Falha de integração (resiliência) | `tests/integration/test_scenario_4_resilience.py` | 11/14 |

## O que foi implementado

`tests/integration/test_scenario_2_high_risk_escalation.py` (novo) — três testes cobrindo o ciclo completo do cenário 2:

1. **Escala e pausa** — evidência mockada (nenhum código encontrado, um padrão RAG de 2FA do corpus real, `knowledge/login.md`, nenhum histórico) mais `analyze_impact` mockado com o risco exato do exemplo do PRD (HIGH/LIKELY, com mitigação) produz `risk_level="HIGH"`, `confidence=65` (abaixo do threshold), `human_review_required=True`, e o grafo pausa (`interrupt()`, cards 15/16). A trilha de auditoria (card 20) registra `ESCALATED`.
2. **Aprovação retoma e publica** — `Command(resume="APPROVED")` publica o parecer (arquivo, sem `issue_number`); o corpo contém "Revisão humana necessária: sim" — o "carimbo de revisão humana" que a composição atual (`render_comment`, card 10) consegue expressar. Auditoria: `ESCALATED` → `APPROVED_PUBLISHED`, `actor="human"`.
3. **Rejeição retoma e arquiva** — `Command(resume="REJECTED")` não publica nada. Auditoria: `ESCALATED` → `REJECTED_ARCHIVED`.

## Por que a confiança é 65, não 63

O `63` da seção 12 do PRD é um número **ilustrativo** da narrativa do cenário, não uma saída travada da fórmula de confiança (seção 11) — a fórmula é determinística (card 02) e produz o que a evidência real (mockada, neste caso) manda. Com os inputs deste teste — nenhum código encontrado (`-25`), só uma fonte de evidência distinta, o padrão RAG (`-10`), mitigação presente (`0`), requisito com mais de 15 palavras (`0`), `feature_type` "login" (`0`) — o resultado é `100 − 25 − 10 = 65`. Isso é reconstruído no docstring/comentários do teste, dedução por dedução, para não parecer um número mágico.

## `analyze_impact` mockado — a peça que falta para reproduzir o cenário literalmente

`analyze_impact` (o LLM que classifica impactos e riscos a partir da evidência) ainda é stub (card 14 do LLM, distinto do card 14 do Kanban, que era sobre `confidence scoring`) — sem ele, `risks` fica sempre vazio e `aggregate_risk_level([])` é sempre `LOW`, nunca `HIGH`. O teste mocka `nodes.analyze_impact` diretamente (mesmo padrão de mockar `search_code`/`_fetch_history`/`retrieve_patterns` já estabelecido nos cards anteriores) com o risco exato do exemplo do PRD, para poder exercitar o restante do pipeline (`score_risk` → `decide_autonomy` → `human_approval` → `publish_comment`/`archive`) de ponta a ponta com um `risk_level` realista de HIGH.

## Sobre o "E2E via `TestClient` do FastAPI" (seção 15 do PRD)

Fora de escopo deste card: não existe API ainda (card 30, "Interface mínima", ainda não implementado) — não há `TestClient` para instanciar. Os "testes de integração" deste card cobrem o grafo completo (`build_graph().invoke()`), que é a peça que a aceitação E2E vai orquestrar por baixo quando os endpoints existirem; a suíte de aceitação de verdade (submeter requisito → verificar escalação → aprovar pelo endpoint → verificar publicação) é retomada no card 30.

## Housekeeping: lint 100% verde

`ruff check .` (o repositório inteiro, não só os arquivos tocados por este card) tinha um `F401` esquecido (`import pytest` não utilizado) em `tests/unit/test_extract_requirement.py`, de um card anterior. Corrigido — "suíte verde" cobre lint, não só testes.

## Testes

`pytest -q`: **166 passed, 3 skipped** (Ollama real), 99,09% de cobertura (gate de 70%, card 22, mantido). `ruff check .`: sem apontamentos, no repositório inteiro.
