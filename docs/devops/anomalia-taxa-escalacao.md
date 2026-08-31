# Baseline univariado: taxa de escalação por janela — anomalia identificada

**Card:** 27 — Dataset e detecção de anomalia
**Dataset:** [`dataset-execucoes.csv`](dataset-execucoes.csv) (50 execuções simuladas)
**Módulos:** `src/devops/dataset.py` (geração), `src/devops/baseline.py` (baseline univariado)

## Metodologia de geração do dataset

50 execuções simuladas em duas fases (`src/devops/dataset.py::generate_dataset`, seed fixa `42` — reprodutível):

- **Fase normal (execuções 1–35):** evidência de código e RAG encontrando resultado na maior parte das vezes (85–90% de chance), poucas falhas de tool.
- **Fase degradada (execuções 36–50):** simula o cenário "a base RAG parou de cobrir os tipos de requisito que chegam, ou a busca de código parou de encontrar correspondências" — probabilidade de encontrar código/padrão RAG cai para 25–30%, falhas de tool sobem, e mais requisitos são classificados como `"outro"` (o classificador não reconhece o tipo).

**Decisão de metodologia deliberada:** `confidence` de cada linha **não é um número sorteado diretamente** — é calculado pela fórmula real de produção (`calculate_confidence`, `src/domain/risk.py`, card 02) a partir dos sinais de evidência simulados acima. Isso significa que o dataset não é uma distribuição estatística arbitrária desenhada para "parecer" uma anomalia; ele é o que a fórmula de confiança do próprio RADAR produziria de verdade se a qualidade da evidência disponível caísse do jeito descrito. `human_review_required` usa a mesma regra de RF-06.1/06.2 (`confidence < 70`). `duration_ms` simula a latência dominada por chamadas de LLM — achado real do card 21 (~88% do tempo de uma execução são as duas chamadas de LLM).

Colunas do CSV: `session_id`, `duration_ms`, `retries_used`, `confidence`, `tool_errors`, `evidence_sources_count`, `human_review_required`.

## Baseline: taxa de escalação por janela de 10 execuções

Faixa esperada, calibrada para `CONFIDENCE_THRESHOLD=70` (seção 16 do PRD): **20%–40%**.

| Janela | Execuções | Taxa de escalação | Dentro da faixa esperada? |
|---|---|---|---|
| 1 | 1–10 | 30% | Sim |
| 2 | 11–20 | 20% | Sim |
| 3 | 21–30 | 40% | Sim (limite) |
| 4 | 31–40 | **70%** | **Não — anômalo** |
| 5 | 41–50 | **80%** | **Não — anômalo** |

Comparação agregada por fase (não só por janela de 10):

| Métrica | Fase normal (1–35) | Fase degradada (36–50) |
|---|---|---|
| Taxa de escalação | 31,4% (11/35) | **86,7%** (13/15) |
| `evidence_sources_count` médio | 2,34 | 1,33 |
| `confidence` médio | 79,0 | 42,0 |

Taxa geral do dataset inteiro: 48% — por si só já fora da faixa 20–40%, mas é a **quebra por janela** que localiza onde a degradação começou (a partir da execução ~31, não desde o início).

## Anomalia identificada

A partir da janela 4 (execuções 31–40), a taxa de escalação sobe de forma consistente e permanece acima de 40% — não é um pico isolado (o que sugeriria ruído/uma execução atípica), é uma mudança de patamar sustentada pelas duas janelas seguintes (70%, depois 80%).

## Interpretação

A causa não é "os requisitos ficaram mais complexos" — é queda na **qualidade da evidência disponível**, exatamente o que a fórmula de confiança (seção 11 do PRD) foi desenhada para medir. A tabela agregada confirma a mecânica: `evidence_sources_count` médio caiu de 2,34 para 1,33 (menos de 2 fontes já aciona a dedução de −10 na fórmula) e `confidence` médio caiu de 79,0 para 42,0 — bem abaixo do threshold de 70. Duas causas prováveis, ambas coerentes com o dado observado:

1. **A base de padrões RAG (`knowledge/`, card 12) parou de cobrir os tipos de requisito que chegam** — requisitos de tipos não cobertos caem em `"outro"` (penalização de −15 na fórmula) e não recuperam nenhum padrão (−20 adicional).
2. **A busca de código (`search_code`, card 08) parou de encontrar correspondências** — um repositório que mudou de estrutura, ou termos de busca que pararam de bater com o código atual, geram `code_matches_found=False` (−25) de forma sistemática, não pontual.

Em ambos os casos, o sintoma observável é o mesmo — a confiança cai por falta de evidência, não porque o LLM esteja "julgando" os requisitos mais arriscados — e a resposta correta é auditar a cobertura do RAG e a atualidade dos termos de busca, não recalibrar o `CONFIDENCE_THRESHOLD` para cima (isso só esconderia o sintoma, publicando pareceres com evidência ruim como se tivessem confiança suficiente).

## Testes

`tests/unit/test_devops_baseline.py` — o cálculo de taxa por janela, isoladamente (contagens simples, sem depender do dataset simulado).

`tests/unit/test_devops_dataset.py` — geração determinística (mesma seed → mesmo dataset), `confidence` sempre no intervalo válido da fórmula real, `human_review_required` consistente com o threshold, round-trip CSV, e um teste que trava a própria anomalia documentada aqui: a fase degradada precisa ter taxa de escalação acima de 40% e maior que a fase normal — se a metodologia de simulação mudar e parar de reproduzir esse cenário, o teste falha antes da documentação ficar desatualizada silenciosamente.

`pytest -q`: 181 passed, 3 skipped (Ollama real), 99,06% de cobertura. `ruff check .`/`ruff format --check .`: sem apontamentos.
