# Card 44 — Implementar `analyze_impact` real (LLM, RF-04)

**Branch/PR:** `feature/analyze-impact-llm` → PR para `develop`
**Resultado esperado (Kanban):** o parecer para de sair com `impacts`/`risks` vazios em execução real; o único node stub do grafo passa a ser real.

## Contexto: o que já existia

A topologia do grafo (card 04) nasceu com todos os nodes stub. As integrações reais entraram nos cards seguintes — `extract_requirement` (6), `search_code`/`fetch_history` (8/9), `retrieve_rag` (13), `score_risk` (02/04), `human_approval` (15), `publish_comment` (10), `guard_adversarial` (18). `analyze_impact` ficou de fora: o cabeçalho de `nodes.py` o chamava de "card 14 do LLM", mas o card 14 do Kanban é *confidence scoring* — o node nunca teve card próprio nem horas alocadas no plano de 40h. Consequência: em execução real `impacts`/`risks` voltavam vazios, `aggregate_risk_level([])` retornava sempre `LOW`, e os cenários 2/3 dos testes precisavam mockar a saída inteira do node para exercitar o resto do pipeline.

## O que foi implementado

- **`ImpactAnalysisResult`** (`src/graph/state.py`) — schema Pydantic de saída estruturada do node: `impacts`, `risks`, `dependencies`, `recommended_tests`. É um recorte de `ImpactAnalysis` (a saída final) com só os quatro campos que o modelo produz; reusa os models `Impact` e `Risk` já existentes.
- **Prompt `03-analyze-impact`** (`ANALYZE_IMPACT_SYSTEM` + `build_analyze_impact_prompt` em `src/graph/prompts.py`, documentado em `docs/prompts/03-analyze-impact.md`) — no padrão dos prompts 01/02: system string + builder que interpola dado externo dentro de bloco delimitado. A evidência coletada entra em três blocos rotulados (`código` / `padrões` / `histórico`), cada item prefixado pelo `file:line` / `source` / `ref` para o modelo poder citá-lo em `Impact.evidence`.
- **`analyze_impact`** (`src/graph/nodes.py`) — real: `build_chat_model().with_structured_output(ImpactAnalysisResult).invoke(prompt)`, `_set_gen_ai_span_attributes()` como os outros nodes LLM (RF-09.6), e o contrato de saída idêntico ao do stub (as mesmas quatro chaves), então `score_risk`/`decide_autonomy`/`build.py` não mudam.

## Decisões técnicas

- **RF-04.5 (rastreabilidade) aplicada no node, não confiada ao prompt.** Se `state["evidence_sources"]` está vazio, o node devolve tudo vazio sem chamar o modelo — não há fonte para sustentar afirmação nenhuma. Com evidência, os impactos passam por `_impact_is_grounded`: o campo `evidence` precisa referenciar (substring, nos dois sentidos) um identificador de fonte coletada — o caminho do arquivo, seu basename, o `source` do RAG ou o `ref` do histórico. Impacto que não casa é descartado, com `analyze_impact_dropped_ungrounded_impacts` no log. Riscos passam direto: o model `Risk` não tem campo de evidência, e a RF-04.5 já é satisfeita estruturalmente pelo `evidence_sources` que os nodes de coleta populam.
- **Degradação, não retry.** Erro de chamada ou parse → log `analyze_impact_failed` + quatro listas vazias, mesma filosofia de `extract_requirement`/`guard_adversarial`. O grafo continua; sem impactos/riscos a `confidence` calculada em `score_risk` fica baixa e o resultado escala para revisão humana em vez de publicar (seção 11 do PRD). Não há retry dedicado — o orçamento de execução (card 35) já limita passos, e reinvocar um modelo local que acabou de devolver JSON inválido raramente muda o resultado.
- **O LLM não decide nada.** `analyze_impact` só classifica; `risk_level` e `confidence` continuam 100% determinísticos em `score_risk` (RF-05.4). É a contenção arquitetural da seção 13 do PRD — mesmo um modelo induzido não consegue rebaixar um risco alto.

## Testes

- **`tests/unit/test_analyze_impact.py`** (novo): saída do LLM mapeada para as quatro chaves; evidência coletada presente no prompt; impacto sem `evidence` ou com fonte inexistente é descartado, o grounded é mantido; `evidence_sources` vazio → tudo vazio e o modelo não é chamado; exceção do LLM → tudo vazio; `requirement is None` → tudo vazio sem chamar o modelo.
- **`tests/unit/test_prompts.py`** (novo): `build_analyze_impact_prompt` inclui cada peça de evidência com seu identificador; blocos vazios recebem o texto de "nada encontrado"; `CodeMatch` sem `line` não vira `arquivo:None`.
- **`tests/integration/test_scenario_2_high_risk_escalation.py`**: deixou de fazer `monkeypatch.setattr(nodes, "analyze_impact", ...)` — agora fixa só a chamada ao modelo via `mock_llm(..., risks=[...])` e exercita o node real. Asserções intactas (`risk_level == "HIGH"`, `confidence == 65`, escala e retoma, auditoria `["ESCALATED", ...]`).
- **`tests/helpers.py`**: `mock_llm` ganhou o schema `ImpactAnalysisResult` e os parâmetros `impacts`/`risks`/`dependencies`/`recommended_tests` (default: vazios — o node roda, só não produz nada, preservando o comportamento que os testes do cenário 1 / paralelismo / logging esperavam do stub).

`python -m pytest -q`: **325 passed, 6 skipped**, cobertura **99,38%** (100% em `src/graph/nodes.py`, `prompts.py`, `state.py`). `ruff check` / `ruff format --check`: sem apontamentos.

## Limitação remanescente

A **composição do parecer final** continua provisória e vira o **card 45** (concluído em seguida): `render_comment` (`src/mcp_server/tools/publish_comment.py`) monta um corpo markdown mínimo a partir de `risk_level`/`confidence`/`requirement` e ainda não consome `impacts`/`risks`/`dependencies`/`recommended_tests`; `state["analysis"]` (`ImpactAnalysis`) nunca é populado; falta o prompt `04-compose-report` (seção 18 do PRD). Ver [`card-45-compose-report.md`](card-45-compose-report.md).
