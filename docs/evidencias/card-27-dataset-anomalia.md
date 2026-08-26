# Card 27 — Dataset e detecção de anomalia

**Branch/PR:** `feature/devops-baseline-anomaly`
**Resultado esperado (Kanban):** Taxa de escalação → Anomalia identificada e explicada

## Escopo

Este card cobre o baseline univariado exigido pelo edital como "estimativa simples" (seção 16 do PRD). A detecção multivariada com Isolation Forest é o card 40 — extensão pós-rubrica explicitamente marcada como risco aceito de pendência (seção 23 do PRD) — fora de escopo aqui.

## O que foi implementado

- `src/devops/dataset.py` — `generate_dataset()`: 50 execuções simuladas em duas fases (normal 1–35, degradada 36–50), seed fixa (reprodutível). `confidence` de cada linha é calculado pela fórmula **real** de produção (`calculate_confidence`, `domain/risk.py`, card 02) a partir de sinais de evidência simulados — não é um número sorteado direto. `write_csv`/`read_csv` fazem o round-trip com `docs/devops/dataset-execucoes.csv` (committed, 50 linhas reais geradas pelo script).
- `src/devops/baseline.py` — `escalation_rate_by_window()`: taxa de escalação humana por janela de N execuções (default 10), marcando janelas fora da faixa esperada 20%–40%.
- `docs/devops/anomalia-taxa-escalacao.md` — o entregável de análise: metodologia do dataset, tabela de taxa por janela, comparação agregada por fase, anomalia identificada (janelas 4 e 5, execuções 31–50, taxa 70%/80%) e interpretação (queda de `evidence_sources_count`/`confidence` — RAG ou busca de código pararam de encontrar correspondência, não "requisitos mais complexos").

## Por que `confidence` vem da fórmula real, não de um sorteio

Um dataset simulado com `confidence` sorteado de uma distribuição arbitrária "para parecer uma anomalia" seria fácil de fabricar, mas não provaria nada sobre o comportamento real do RADAR. Alimentar `calculate_confidence` com sinais de evidência simulados (código encontrado, padrão RAG encontrado, falhas de tool, fontes distintas) faz o número de confiança de cada linha ser exatamente o que a fórmula de produção calcularia — a anomalia observada no baseline é uma consequência real da fórmula reagindo a evidência ruim, não um artefato da simulação.

## Testes

`tests/unit/test_devops_baseline.py` — cálculo de taxa por janela isolado (janela completa, parcial, múltiplas janelas, acima/abaixo da faixa esperada, entrada vazia).

`tests/unit/test_devops_dataset.py` — determinismo por seed, 50 linhas, `confidence` sempre no intervalo válido, `human_review_required` consistente com o threshold, round-trip CSV, e um teste que trava a anomalia documentada em si (fase degradada > 40% e maior que a fase normal) — protege contra a documentação ficar desatualizada se a metodologia de simulação mudar.

`pytest -q`: 181 passed, 3 skipped (Ollama real), 99,06% de cobertura. `ruff check .`/`ruff format --check .`: sem apontamentos.

## Decisões técnicas

- `src/devops/` criado neste card (não existia) — mesma pasta que os cards 28/40/41 (extensão) vão usar (`trend_model.py`, `anomaly.py`).
- Dataset committed em `docs/devops/dataset-execucoes.csv`, não gerado em tempo de execução pelos testes — a análise documentada (tabela, números) precisa ser sobre um dataset fixo e citável, não recalculada a cada rodada de teste com dados diferentes.
