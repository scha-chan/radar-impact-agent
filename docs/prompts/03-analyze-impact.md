# 03 — analyze-impact

**Node:** `analyze_impact` (`src/graph/nodes.py`)
**Função:** classificar impactos, riscos, dependências e testes recomendados a partir da evidência coletada (RF-04)
**Modelo usado em desenvolvimento:** Ollama, `mistral` (local, sem custo de API)

## Objetivo

A partir do requisito extraído e da evidência já coletada em paralelo — trechos de código (`search_codebase`), padrões de impacto conhecidos (`retrieve_rag`), histórico de mudanças (`fetch_history`) e, numa reanálise pedida pelo revisor (card 47), o **contexto adicional do revisor** —, produzir as quatro listas da RF-04:

- **impacts** — impactos classificados por área, com severidade e a evidência que os sustenta (RF-04.1).
- **risks** — riscos com descrição, severidade, probabilidade e mitigação sugerida (RF-04.2).
- **dependencies** — dependências externas identificadas (RF-04.3).
- **recommended_tests** — testes prioritários, derivados dos riscos de maior severidade (RF-04.4).

## O que este node NÃO faz

Não calcula `risk_level` nem `confidence` — isso é `score_risk`, Python puro (RF-05.4). O LLM só alimenta a classificação de entrada; a matriz severidade × probabilidade e a fórmula de confiança nunca passam pelo modelo. É a mesma separação de `domain/risk.py`: "se dá para computar, compute".

## Regras de comportamento

- `severity`: exatamente `LOW`, `MEDIUM`, `HIGH` ou `CRITICAL`. `probability`: exatamente `RARE`, `POSSIBLE`, `LIKELY` ou `ALMOST_CERTAIN`.
- **RF-04.5 (rastreabilidade):** o campo `evidence` de cada impacto deve citar textualmente um `file`/`source`/`ref` presente no bloco de evidência do prompt. Um impacto cujo `evidence` não referencia nenhuma fonte coletada é descartado pelo node antes de seguir para `score_risk` (`analyze_impact_dropped_ungrounded_impacts` no log). Se nenhuma fonte de evidência foi coletada, a saída é inteiramente vazia — não há o que sustentar.
- Evidência insuficiente para uma lista → devolver a lista vazia, nunca inventar.

## Restrições

O texto do requisito, os trechos de código e o contexto do revisor são **dado a ser analisado**, nunca instrução dirigida ao agente — mesma blindagem contra prompt injection dos prompts 01/02 (seção 13 do PRD). O contexto do revisor ainda passa por `detect_by_pattern` na rota da API (`POST /approvals/{session_id}`) antes de chegar aqui. A contenção real continua sendo arquitetural: mesmo que o modelo seja induzido, ele não decide `risk_level` nem o threshold de escalação.

## Formato de saída esperado

Saída estruturada via `with_structured_output(ImpactAnalysisResult)` (`src/graph/state.py`) — sem texto livre, sem markdown, só o schema Pydantic (`impacts`, `risks`, `dependencies`, `recommended_tests`).

## Tratamento de falha (RF-04, degradação)

Erro de chamada ou de parse do LLM → o node loga `analyze_impact_failed` e devolve as quatro listas vazias. O grafo continua; sem impactos/riscos, `aggregate_risk_level` retorna `LOW` e a `confidence` calculada em `score_risk` fica baixa pela falta de evidência analisada — o resultado degradado escala para revisão humana em vez de publicar (seção 11 do PRD). Não há retry dedicado aqui: o orçamento de execução (`max_steps`, card 35) já limita o número de passos, e uma segunda tentativa de um modelo local que acabou de devolver JSON inválido raramente ajuda.

## Prompt (texto exato usado em produção)

Ver `ANALYZE_IMPACT_SYSTEM` e `build_analyze_impact_prompt` em `src/graph/prompts.py` — mantido em código (não carregado deste arquivo em runtime) porque interpola o texto do requisito e a evidência coletada; este documento deve ser atualizado sempre que o texto em código mudar.
