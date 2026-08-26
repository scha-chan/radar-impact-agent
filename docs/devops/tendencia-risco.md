# Estimativa de tendência: projeção da taxa de escalação

**Card:** 28 — Estimativa de tendência
**Módulo:** `src/devops/trend.py`
**Base:** as 5 janelas de taxa de escalação do card 27 (`docs/devops/anomalia-taxa-escalacao.md`, sobre `dataset-execucoes.csv`)

Regressão linear simples (mantida, exigida pelo edital como "estimativa de tendência") sobre a taxa de escalação humana por janela, projetando a janela seguinte. A regressão da probabilidade de falha por classificador calibrado (`HistGradientBoostingClassifier`) é o card 41 — extensão pós-rubrica, fora de escopo aqui.

## Dados

As mesmas 5 janelas de 10 execuções do baseline do card 27:

| Janela (x) | Execuções | Taxa de escalação (y) |
|---|---|---|
| 1 | 1–10 | 0,30 |
| 2 | 11–20 | 0,20 |
| 3 | 21–30 | 0,40 |
| 4 | 31–40 | 0,70 |
| 5 | 41–50 | 0,80 |

## Regressão

Mínimos quadrados simples (`src/devops/trend.py::linear_regression`), `x` = índice da janela, `y` = taxa de escalação:

- **Coeficiente angular (slope):** `0,15` — cada janela de 10 execuções, em média, tem uma taxa de escalação 15 pontos percentuais maior que a anterior.
- **Intercepto:** `0,03`
- **Reta ajustada:** `y = 0,15x + 0,03`

## Projeção da janela seguinte

Janela 6 (execuções 51–60, hipotéticas — ainda não ocorreram):

```
y = 0,15 × 6 + 0,03 = 0,93  (93%)
```

**93% > 50%** → **alerta de degradação emitido** (`TrendEstimate.alert = True`, `src/devops/trend.py::project_next_window`).

## Conclusão

A tendência não é ruído — o coeficiente angular positivo e razoavelmente grande (0,15 por janela) confirma o que o card 27 já tinha identificado por inspeção direta: a partir da janela 4, a taxa de escalação entrou numa trajetória de alta sustentada, não um pico isolado. Projetar essa reta para a janela seguinte cruza o limiar de alerta (50%) com folga considerável (93%), o que indica que, **sem intervenção**, a tendência é a taxa de escalação continuar subindo, não estabilizar sozinha.

Isso reforça a interpretação já registrada em `anomalia-taxa-escalacao.md`: a causa provável é degradação da qualidade de evidência disponível (cobertura do RAG ou atualidade dos termos de busca de código), não uma mudança real na complexidade dos requisitos que chegam — e é acionável **antes** da próxima janela realmente escalar 93% das análises, que é exatamente o valor de uma estimativa de tendência sobre um baseline reativo (que só constata o problema depois que ele já aconteceu).

## Ação recomendada (não implementada neste card)

A seção 16 do PRD descreve, como evolução (`action-gating`, associado ao card 41), elevar temporariamente o `CONFIDENCE_THRESHOLD` efetivo quando a probabilidade prevista de escalação ultrapassa 70% — mais conservador até a taxa normalizar. Esse gating específico não foi implementado aqui (depende do classificador calibrado do card 41, fora de escopo); a ação recomendada imediata, dado só o baseline+tendência deste card, é auditar a cobertura do corpus RAG (`knowledge/`) e a atualidade dos termos de busca de código antes da próxima janela.

## Testes

`tests/unit/test_devops_trend.py` — `linear_regression` isolada (reta perfeita, reta constante, validação de tamanho e de pontos mínimos, `xs` constantes), `project_next_window` reproduzindo manualmente os números deste documento (slope 0,15, intercepto 0,03, projeção 0,93, alerta ativado), um caso sem alerta (tendência estável), e um teste de integração com o dataset real do card 27 (não um exemplo isolado) — se a metodologia de simulação mudar e a tendência parar de ultrapassar 50%, o teste falha antes deste documento ficar desatualizado silenciosamente.

`pytest -q`: 189 passed, 3 skipped (Ollama real), 99,09% de cobertura. `ruff check .`/`ruff format --check .`: sem apontamentos.
