# Card 40 — Detecção de anomalia com Isolation Forest

**Branch/PR:** `feature/anomaly-isolation-forest`
**Extensão pós-rubrica** (seção 21 do PRD) — detecção multivariada, seção 16.

## O que foi implementado

`src/devops/anomaly.py` (novo): `detect_anomalies()` normaliza (`StandardScaler`) cinco features do dataset já existente do card 27 (`duration_ms`, `retries_used`, `confidence`, `tool_errors`, `evidence_sources_count`) e treina um `IsolationForest` (`contamination` configurável, default 0,1) sobre elas. `list_outliers()` devolve só as execuções marcadas outlier, ordenadas da mais anômala para a menos.

`human_review_required` fica fora das features — é quase determinístico a partir de `confidence` (RF-06.1/06.2); incluí-lo faria o modelo redizer o que o baseline univariado (card 27) já cobre. O valor de uma detecção multivariada está em achar combinações incomuns *entre as demais features*, não a mesma coisa por outro caminho.

Resultado real (dataset de 50 execuções, `contamination=0.1`), interpretação execução por execução, e o caso que corresponde exatamente ao exemplo motivador da seção 16 do PRD ("confiança alta com muitos retries") estão documentados em [`docs/devops/anomalias-isolation-forest.md`](../devops/anomalias-isolation-forest.md).

## Testes

`tests/unit/test_devops_anomaly.py`: dataset vazio, cardinalidade dos resultados, uma combinação sintética deliberadamente incomum é corretamente marcada outlier (prova de que o modelo captura o padrão que motiva o card, não só reproduz o dataset real por coincidência), ordenação por score, determinismo por `random_state`, e proporção de outliers no dataset real como minoria clara.

`pytest -q`: 308 passed (6 novos), 6 skipped (Ollama real), 99,33% de cobertura. `ruff check .`/`ruff format --check .`: sem apontamentos.
