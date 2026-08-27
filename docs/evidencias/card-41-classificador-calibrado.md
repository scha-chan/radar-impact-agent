# Card 41 — Estimativa de falha com classificador calibrado

**Branch/PR:** `feature/calibrated-failure-classifier`
**Extensão pós-rubrica** (seção 21 do PRD) — RNF-11, seção 16.

## O que foi implementado

`src/devops/trend_model.py` (novo): `train_escalation_classifier()`/`predict_escalation_probability()` (`HistGradientBoostingClassifier` calibrado via `CalibratedClassifierCV`, método sigmoid), `evaluate_calibration()` (RNF-11: discriminação — ROC-AUC, average precision — **e** calibração — Brier score), `effective_confidence_threshold()` (action gating da seção 16 do PRD).

`src/devops/dataset.py`/`anomaly.py` receberam um pequeno refactor: `FEATURE_NAMES`/`to_feature_matrix()` (antes só em `anomaly.py`, com nome privado `_to_feature_matrix`) foram movidos para `dataset.py` — agora compartilhados entre `anomaly.py` (card 40) e `trend_model.py` (este card), consistente com a seção 16 do PRD: "[o classificador] treinado sobre o mesmo dataset e as mesmas features do Isolation Forest".

## Achado principal: bug real de configuração, não do dataset

A primeira medição real deu ROC-AUC=0,47 (pior que aleatório) e Brier quase idêntico ao de um previsor ingênuo — sintoma de modelo que não aprendeu nada. Investigado e corrigido: `min_samples_leaf=20` (padrão do `HistGradientBoostingClassifier`) é maior que o número de amostras que sobra em cada dobra interna do `CalibratedClassifierCV` sobre um dataset de 50 execuções — a árvore não conseguia fazer nenhuma divisão útil. Reduzindo para `5`, ROC-AUC subiu para 1,0 e Brier score para 0,0279. Detalhe completo da investigação (incluindo a comparação com/sem calibração que isolou a causa) em [`docs/devops/action-gating.md`](../devops/action-gating.md).

## Brier score documentado (RNF-11)

```
ROC-AUC:              1.0
Average precision:    1.0
Brier score:          0.0279
```

Reportado lado a lado com a ressalva de que `human_review_required` é quase determinístico a partir de uma das próprias features (`confidence`) — o resultado valida a metodologia (pipeline de treino/calibração corrigido), não um poder discriminativo real de produção, mesma ressalva já registrada para o Isolation Forest.

## Action gating

Caso simulado documentado em `docs/devops/action-gating.md`: uma execução hipotética com evidência degradada (confidence=25) recebe probabilidade de escalação prevista de 85,24% — acima do limiar de 70% — elevando `CONFIDENCE_THRESHOLD` efetivo de 70 para 80.

## Testes

`tests/unit/test_devops_trend_model.py`: 8 testes cobrindo treino, predição, relatório de calibração e as três faixas de `effective_confidence_threshold` (abaixo/acima/exatamente no limiar).

`pytest -q`: 316 passed (8 novos), 6 skipped (Ollama real), 99,35% de cobertura. `ruff check .`/`ruff format --check .`: sem apontamentos.
