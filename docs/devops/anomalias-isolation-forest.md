# Detecção multivariada de anomalia — Isolation Forest (card 40)

Extensão pós-rubrica (seção 21 do PRD), seção 16. Complementa o baseline univariado do card 27 (`docs/devops/anomalia-taxa-escalacao.md` — taxa de escalação por janela): o baseline não captura **combinações incomuns** entre sinais, só um sinal isolado fora de faixa.

## Metodologia

`src/devops/anomaly.py::detect_anomalies` normaliza (`StandardScaler`) cinco features do mesmo dataset do card 27 (`docs/devops/dataset-execucoes.csv`, 50 execuções, seed fixa): `duration_ms`, `retries_used`, `confidence`, `tool_errors`, `evidence_sources_count`. `human_review_required` fica de fora de propósito — é quase determinístico a partir de `confidence` (RF-06.1/06.2), então incluí-lo faria o modelo redizer o que o baseline já cobre.

`IsolationForest(contamination=0.1, random_state=42)` treinado sobre as features normalizadas. `contamination=0.1` reflete a expectativa de que anomalias são raras (~10% do dataset) — **accuracy não é métrica útil aqui** (classe rara, um classificador que sempre prevê "normal" teria 90% de acerto e zero utilidade); o que importa é o orçamento de falso alarme, por isso o `score_samples` de cada execução é reportado, não só o rótulo binário outlier/inlier.

## Resultado real (dataset de 50 execuções, `contamination=0.1`)

5 de 50 execuções (10%) marcadas como outlier:

| session_id | score | duration_ms | retries | confidence | tool_errors | evidence_sources | human_review |
|---|---:|---:|---:|---:|---:|---:|---|
| `sim-045` | -0.6449 | 25497 | 2 | 75 | 0 | 2 | não |
| `sim-044` | -0.6212 | 14528 | 0 | 0 | 1 | 0 | sim |
| `sim-039` | -0.6071 | 14049 | 0 | 0 | 2 | 1 | sim |
| `sim-047` | -0.5977 | 8727 | 0 | 40 | 2 | 1 | sim |
| `sim-004` | -0.5965 | 21974 | 1 | 100 | 0 | 3 | não |

(`score_samples` do Isolation Forest: quanto mais negativo, mais anômalo.)

## Interpretação por execução

- **`sim-045`** (mais anômala): 2 retries e duração alta (25,5s, a maior do dataset), mas confiança ainda razoável (75) e sem erro de tool — a combinação "esforço muito acima da média sem escalar" é incomum; o baseline não veria isso porque `human_review_required=False` (75 ≥ 70).
- **`sim-044`/`sim-039`**: confiança no piso absoluto (0) combinada com poucas fontes de evidência (0 e 1) e erro de tool — casos extremos que o baseline já capturaria via `human_review_required=True`, mas aqui aparecem como outliers pela combinação de *múltiplos* sinais ruins simultâneos, não um único sinal fora de faixa.
- **`sim-047`**: confiança baixa (40) com 2 erros de tool e só 1 fonte de evidência — padrão de degradação de evidência semelhante ao identificado no baseline (card 27), mas isolado como caso individual extremo, não só parte da janela degradada.
- **`sim-004`**: **o caso que a seção 16 do PRD descreve como motivador da detecção multivariada** — "confiança alta com muitos retries, indício de uma tool mascarando falha". Aqui, confiança perfeita (100) com 1 retry e duração entre as mais altas do dataset (22s): a fórmula de confiança não penaliza retry diretamente (só `tools_failed_with_fallback`, que é 0 aqui — o retry teve sucesso na segunda tentativa), então o baseline nunca veria isso como suspeito. A combinação "teve que tentar de novo, mas terminou com confiança máxima" é exatamente o tipo de sinal que só aparece olhando as features juntas.

## Testes

`tests/unit/test_devops_anomaly.py`: dataset vazio, uma linha de resultado por execução, uma combinação sintética deliberadamente incomum (confiança alta + muitos retries + erros de tool + poucas fontes — o mesmo padrão do `sim-004`/`sim-047` reais) é corretamente marcada como outlier, ordenação de `list_outliers` por score, determinismo (mesmo `random_state` → mesmo resultado), e a proporção de outliers no dataset real fica abaixo de 50% (uma minoria clara, não metade do dataset).

`pytest -q`: 308 passed (6 novos), 6 skipped (Ollama real), 99,33% de cobertura. `ruff check .`/`ruff format --check .`: sem apontamentos.
