# 04 — compose-report

**Node:** `publish_comment` (`src/graph/nodes.py`, via `_compose_report`)
**Função:** redigir o texto do parecer a partir do `ImpactAnalysis` já montado (RF-08, seção 18 do PRD)
**Modelo usado em desenvolvimento:** Ollama, `mistral` (local, sem custo de API)

## Objetivo

Transformar o objeto `ImpactAnalysis` (montado deterministicamente a partir do state — `session_id`, `risk_level`, `confidence`, `human_review_required`, `impacts`, `risks`, `dependencies`, `recommended_tests`, `evidence_sources`) em texto legível para quem lê o comentário na Issue. O LLM produz apenas duas strings:

- **`requirement_summary`** — o requisito condensado em uma frase (~15 palavras).
- **`executive_summary`** — 2 a 4 frases para uma tech lead: o que a mudança afeta, o risco e por quê, e se precisa de revisão.

Todo o resto do comentário (cabeçalho com risco/confiança/revisão, tabelas de impactos e riscos, dependências, testes, evidência) é renderizado deterministicamente por `render_comment` a partir do objeto — o LLM não o escreve.

## O que este prompt NÃO faz

Não decide nem altera nenhum campo estruturado. `risk_level`, `confidence`, a lista de impactos e a de riscos entram no prompt como contexto para a redação, mas o modelo não os reescreve — o `ImpactAnalysis` publicado é o montado a partir do state, com só `requirement_summary` trocado pela versão condensada. É a mesma separação dos outros nodes: o LLM redige, as regras decidem.

## Regras de comportamento

- Escrever sempre em português do Brasil, mesmo que o objeto esteja em outro idioma.
- Não contradizer o nível de risco nem sugerir dispensar revisão humana quando o objeto diz que ela é necessária.
- Não inventar impactos, riscos, números ou sistemas que não aparecem no objeto.
- Sem markdown, sem listas — só as duas strings.

## Formato de saída esperado

Saída estruturada via `with_structured_output(ComposedReport)` (`src/graph/state.py`): `requirement_summary: str`, `executive_summary: str`.

## Tratamento de falha (degradação)

Erro de chamada ou parse → `_compose_report` loga `compose_report_failed` e usa textos determinísticos: `requirement_summary` = primeira linha do requisito (truncada); `executive_summary` = frase montada a partir de `risk_level`/`confidence`/contagem de impactos e riscos/necessidade de revisão. O parecer é publicado mesmo assim — o conteúdo que sustenta a decisão já está no objeto, o texto é acabamento.

## Prompt (texto exato usado em produção)

Ver `COMPOSE_REPORT_SYSTEM` e `build_compose_report_prompt` em `src/graph/prompts.py` — mantido em código pelo mesmo motivo dos prompts 01–03 (interpola o objeto de análise); este documento deve ser atualizado sempre que o texto em código mudar.
