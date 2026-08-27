# Card 45 — Compor o parecer final (`ImpactAnalysis` + `04-compose-report`)

**Branch/PR:** `feature/compose-report` → PR para `develop` (stacked sobre o card 44, `feature/analyze-impact-llm`)
**Resultado esperado (Kanban):** o comentário publicado deixa de ser um cabeçalho mínimo e passa a renderizar impactos, riscos, dependências, testes e evidência; `state["analysis"]` (`ImpactAnalysis`) é populado.

## Contexto: o que já existia

Depois do card 44, `analyze_impact` já produzia `impacts`/`risks`/`dependencies`/`recommended_tests` reais, mas nada os usava: `render_comment` (`src/mcp_server/tools/publish_comment.py`) montava um corpo com `risk_level`/`confidence`/`feature_type` e só; `state["analysis"]` nunca era populado (só testado como `None`); o prompt `04-compose-report` da seção 18 do PRD não existia.

## O que foi implementado

- **`ComposedReport`** (`src/graph/state.py`) — schema Pydantic de saída do LLM: `requirement_summary`, `executive_summary`. Só texto.
- **Prompt `04-compose-report`** (`COMPOSE_REPORT_SYSTEM` + `build_compose_report_prompt` em `src/graph/prompts.py`, `docs/prompts/04-compose-report.md`) — recebe o `ImpactAnalysis` já montado e pede só a redação: o requisito condensado numa frase e o resumo executivo para tech lead.
- **`_compose_report`** (`src/graph/nodes.py`) — monta o `ImpactAnalysis` deterministicamente a partir do state (`_build_impact_analysis`), chama o LLM só para os dois textos, e devolve `(analysis, prose)`. Defaults defensivos (`risk_level` ausente → `LOW`, `confidence` ausente → `0`) para o caminho de orçamento estourado (card 35), que pula `score_risk`.
- **`render_comment`** (`src/mcp_server/tools/publish_comment.py`) — ganhou `analysis`/`prose` opcionais. Sem `analysis` (chamada direta da tool nos testes isolados): corpo mínimo de antes. Com `analysis` (caminho do grafo): parecer completo — resumo executivo do LLM no topo, depois cabeçalho + seções de impactos / riscos / dependências / testes / evidência renderizadas deterministicamente a partir do objeto.
- **`publish_comment`** (node) — chama `_compose_report`, passa o corpo renderizado para a tool (`body=`) e retorna `{"analysis": analysis, "published_comment_url": url}`. A topologia do grafo não muda: a composição acontece dentro do node de publicação, não num node novo — coerente com o diagrama da seção 7 do PRD, que não tem etapa de composição separada.

## Decisões técnicas

- **O LLM redige, não decide.** `risk_level`/`confidence`/`impacts`/`risks` entram no prompt como contexto, mas o `ImpactAnalysis` publicado é o montado a partir do state — só `requirement_summary` é trocado pela versão condensada. Mesma separação dos cards 02/44.
- **Composição dentro de `publish_comment`, não em node próprio.** Evita tocar a topologia (`build.py`) e as asserções de roteamento de `test_graph.py`; o parecer só é composto quando o grafo está de fato prestes a publicar (caminho automático ou pós-aprovação), nunca nos caminhos `block`/`archive` — `state["analysis"]` continua `None` nesses (o que o cenário 3 já assevera).
- **Degradação, não retry.** Falha da chamada → `compose_report_failed` no log + textos determinísticos (`requirement_summary` = primeira linha do requisito truncada; `executive_summary` = frase a partir de risco/confiança/contagens/revisão) e publica mesmo assim — o conteúdo que sustenta a decisão já está no objeto.
- **`mock_llm` (`tests/helpers.py`)** ganhou o schema `ComposedReport` e os params `requirement_summary`/`executive_summary` (default: `executive_summary="Resumo executivo de teste."`), então todos os testes que publicam pelo grafo passam a exercitar `_compose_report` sem chamar o Ollama.

## Testes

- **`tests/unit/test_compose_report.py`** (novo): `_compose_report` usa o texto do LLM e mantém os campos estruturados do state; fallback determinístico em falha do LLM; defaults defensivos quando `score_risk` foi pulado; strings em branco do LLM caem no fallback; `render_comment` completo tem todas as seções; seções vazias recebem o texto "_Nenhum..._"; `render_comment` sem `analysis` mantém o corpo mínimo.
- **`tests/unit/test_prompts.py`**: `build_compose_report_prompt` carrega o objeto estruturado e a instrução de não decidir; lida com análise vazia.
- **`tests/unit/test_nodes_tool_executor_wiring.py`**: o teste de recusa de permissão de `publish_comment` agora mocka o LLM (`_compose_report` roda antes da tool) e checa `published_comment_url is None` (a chave `analysis` passou a vir junto).

`python -m pytest -q`: **334 passed, 6 skipped**, cobertura **99,40%** (100% em `nodes.py` / `prompts.py` / `publish_comment.py` / `state.py`). `ruff check` / `ruff format --check`: sem apontamentos. Smoke com Ollama `mistral` real: `_compose_report` devolve `requirement_summary`/`executive_summary` e o corpo renderizado traz todas as seções.

## Fecha o gap do card 44

Com este card, todos os nodes do grafo são reais **e** o parecer publicado reflete a análise completa. O `ImpactAnalysis` da seção 8 do PRD passa a existir de fato no `state["analysis"]` de toda execução que publica.
