# Card 28 — Estimativa de tendência

**Branch/PR:** `feature/devops-trend`
**Resultado esperado (Kanban):** Projeção da janela seguinte → `/docs/devops/tendencia-risco.md`

## Escopo

Regressão linear simples sobre a taxa de escalação (mantida, exigida pelo edital). O classificador calibrado (`HistGradientBoostingClassifier`) é o card 41 — extensão pós-rubrica, fora de escopo aqui, mesmo padrão dos cards 27/40.

## O que foi implementado

- `src/devops/trend.py` — `linear_regression(xs, ys)`: mínimos quadrados simples, sem dependência externa (`numpy`/`sklearn`) — 5 pontos não justificam a dependência. `project_next_window(rates)`: ajusta a reta sobre as taxas de escalação por janela (card 27) e projeta a janela seguinte; `alert=True` quando a projeção ultrapassa 50% (RF explícito da seção 16 do PRD).
- `docs/devops/tendencia-risco.md` — o entregável de análise: dados (as 5 janelas do card 27), coeficiente angular (0,15), intercepto (0,03), projeção da janela 6 (93%) e conclusão.

## Resultado

Com as taxas de escalação por janela do card 27 (30%, 20%, 40%, 70%, 80%), a reta ajustada é `y = 0,15x + 0,03`. Projetando a janela seguinte (x=6): **93%**, bem acima do limiar de alerta (50%) — o alerta de degradação é emitido. O coeficiente angular positivo confirma numericamente o que a inspeção direta do card 27 já sugeria: a alta na taxa de escalação a partir da janela 4 é uma tendência sustentada, não um pico isolado.

## Testes

`tests/unit/test_devops_trend.py` — `linear_regression` isolada (reta perfeita, reta constante, validações de entrada), `project_next_window` reproduzindo os números exatos do documento, um caso sem alerta (tendência estável), e um teste de integração com o dataset real do card 27 que trava a própria conclusão do documento (a projeção sobre o dataset committed precisa continuar ultrapassando 50%) — protege `tendencia-risco.md` de ficar desatualizado se o dataset simulado mudar.

`pytest -q`: 189 passed, 3 skipped (Ollama real), 99,09% de cobertura. `ruff check .`/`ruff format --check .`: sem apontamentos.

## Decisões técnicas

- Regressão implementada à mão (mínimos quadrados, ~15 linhas), não via `numpy.polyfit`/`scipy` — evita adicionar uma dependência pesada só para 5 pontos e uma reta; a fórmula é simples o bastante para ficar auditável a olho nu, o que importa mais aqui do que reaproveitar uma biblioteca.
- `DEGRADATION_ALERT_THRESHOLD = 0.50` como constante nomeada em `trend.py`, não hardcoded dentro de `project_next_window` — mesma lição do code review do card 24 (evitar números mágicos soltos numa fórmula de regra de negócio).
