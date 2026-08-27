# Estimativa de falha com classificador calibrado e action gating (card 41)

**Módulo:** `src/devops/trend_model.py`
**Base:** o mesmo dataset de 50 execuções do card 27 (`docs/devops/dataset-execucoes.csv`), as mesmas features do Isolation Forest (`anomaly.py`, card 40): `duration_ms`, `retries_used`, `confidence`, `tool_errors`, `evidence_sources_count`.

## Classificador calibrado

`HistGradientBoostingClassifier` (scikit-learn) calibrado via `CalibratedClassifierCV` (método `sigmoid` — Platt scaling, adequado ao volume pequeno de 50 amostras, seção 16 do PRD), para estimar a probabilidade de `human_review_required=True` na próxima execução.

## Bug real encontrado e corrigido: `min_samples_leaf` padrão colapsa o modelo neste dataset

Primeira medição, com os parâmetros padrão de `HistGradientBoostingClassifier`:

```
ROC-AUC:      0.4679  (pior que aleatório)
Brier score:  0.2505  (quase idêntico ao baseline ingênuo — prever sempre a taxa base, 0.2496)
```

Isso é sintoma de um modelo que não aprendeu nada. Investigando: `HistGradientBoostingClassifier` usa `min_samples_leaf=20` por padrão — adequado para datasets grandes, mas **maior que o número de amostras que sobra em cada dobra interna do `CalibratedClassifierCV`** sobre um dataset de 50 execuções (a dobra externa de validação já reduz para ~40 amostras; a calibração interna do `CalibratedClassifierCV` divide isso de novo, sobrando ~27-35 por dobra de treino do modelo base). Com `min_samples_leaf=20` e ~30 amostras de treino, a árvore não consegue fazer nenhuma divisão útil — o modelo colapsa para um previsor quase constante. Confirmado inspecionando as probabilidades calibradas: convergiam para só dois valores (~0,476 e ~0,5), sem discriminação nenhuma.

Sem a calibração (`HistGradientBoostingClassifier` puro, sem `CalibratedClassifierCV`), o mesmo dataset já dava ROC-AUC=0,79 — a calibração com dobras pequenas demais é que destruía o sinal, não a falta de sinal no dataset. Reduzindo `min_samples_leaf` para `5` (`src/devops/trend_model.py::MIN_SAMPLES_LEAF`):

```
ROC-AUC:              1.0
Average precision:    1.0
Brier score:          0.0279
```

## Por que ROC-AUC=1,0 não significa "modelo perfeito para produção"

`human_review_required` é derivado quase deterministicamente de uma das próprias features (`confidence < CONFIDENCE_THRESHOLD`, RF-06.1/06.2) — um classificador que usa `confidence` como entrada tem uma vantagem estrutural enorme para separar as classes neste dataset simulado. Isso valida a **metodologia** (o pipeline de treino/calibração funciona, e a correção do `min_samples_leaf` foi real), não o **poder discriminativo em produção** — que só um volume real de execuções, com falhas por motivos que `confidence` sozinho não capta, poderia confirmar (mesma ressalva já registrada nas limitações do README/PRD para o Isolation Forest).

## Action gating (uso da estimativa)

Se a probabilidade prevista de escalação da próxima execução ultrapassar 70%, o `CONFIDENCE_THRESHOLD` efetivo sobe temporariamente (`src/devops/trend_model.py::effective_confidence_threshold`) — paralelo simplificado ao padrão VALIDATE: o sistema não bloqueia execuções (isso seria RESTRICT/PAUSE), só eleva a exigência de confiança até a taxa observada normalizar.

**Caso simulado:**

| Próxima execução (hipotética) | `confidence` | Prob. de escalação prevista | `CONFIDENCE_THRESHOLD` efetivo |
|---|---:|---:|---:|
| Cenário degradado (poucas fontes de evidência, erros de tool) | 25 | **0,8524** | **80** (70 + 10, gating acionado) |
| Cenário normal (evidência boa, sem retries) | 90 | 0,1393 | 70 (sem alteração) |

No cenário degradado, a probabilidade prevista (85,24%) ultrapassa o limiar de 70% — o sistema eleva `CONFIDENCE_THRESHOLD` de 70 para 80 até a taxa observada normalizar, tornando a publicação automática mais rara nesse período (mais análises passam a escalar para revisão humana, por precaução). No cenário normal, a probabilidade (13,93%) fica bem abaixo do limiar — nenhuma mudança.

## Testes

`tests/unit/test_devops_trend_model.py`: treino sem erro sobre o dataset real, probabilidade sempre em `[0, 1]`, uma execução de baixa confiança prevista com probabilidade de escalação maior que uma de alta confiança, `CalibrationReport` bem formado, `effective_confidence_threshold` inalterado abaixo do limiar / elevado acima dele / inalterado exatamente no limiar (estritamente "ultrapassar", não "atingir") / usando o bump padrão de 10.

`pytest -q`: 316 passed (8 novos), 6 skipped (Ollama real), 99,35% de cobertura. `ruff check .`/`ruff format --check .`: sem apontamentos.
