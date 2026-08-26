# Card 24 — Code review com IA de um PR real

**Branch/PR:** `docs/code-review-pr-2`
**Resultado esperado (Kanban):** Validação crítica → `/docs/qa/code-review-pr-N.md`

## O que foi feito

Revisão com IA (skill `code-review`, nível `high`) do [PR #2](https://github.com/scha-chan/radar-impact-agent/pull/2) — a sugestão explícita da seção 15 do PRD, por introduzir `domain/risk.py` (`score_risk`), o módulo de maior criticidade do produto. Diff obtido via `gh pr diff 2 --patch` (119 linhas de `risk.py`, 151 de `test_risk.py`).

Entregável principal: **[`docs/qa/code-review-pr-2.md`](../qa/code-review-pr-2.md)** — o diff analisado, o processo de revisão (8 ângulos: correção × 3, limpeza × 3, altitude, convenções), e os três apontamentos que sobreviveram à verificação, cada um com o contrato `Finding` (severidade, confiança, evidência, sugestão de correção) pedido pela aula de revisão de código.

## Resultado da revisão

Nenhum bug de correção encontrado — a matriz de risco bate célula por célula com a seção 11 do PRD, a fórmula de confiança implementa cada dedução com o valor correto, e o piso/teto está correto para qualquer combinação de entradas. Três apontamentos de manutenibilidade/cobertura sobreviveram à verificação:

1. **`RiskLevel` duplica `Severity`** — **recusado**: são conceitos diferentes (severidade individual vs. nível agregado) que só coincidem numericamente hoje; unificar acopla dois conceitos que o próprio PRD já trata como tabelas separadas.
2. **Deduções da fórmula são números mágicos** — **aceito**: extraídas para constantes nomeadas (`SHORT_REQUIREMENT_PENALTY`, `NO_CODE_MATCH_PENALTY`, etc.) em `src/domain/risk.py`. Mudança puramente cosmética — os 30 testes originais de `test_risk.py` continuam passando sem alteração.
3. **`mitigation=""` sem teste** — **aceito**: `tests/unit/test_risk.py` ganhou `test_confidence_treats_empty_string_mitigation_as_missing`, travando que string vazia é tratada como ausência de mitigação (comportamento já correto, só não estava coberto).

## Por que recusar o apontamento 1 importa para este card

O Kanban pede explicitamente "validação crítica" — o valor do exercício não é aceitar tudo que a IA sugere (isso seria aceitação passiva, o oposto do que o card pede), é demonstrar que cada sugestão foi julgada com critério. O apontamento 1 é o exemplo: soa razoável à primeira vista (menos código, menos duplicação), mas ignora que os dois enums representam conceitos que o próprio PRD já separa deliberadamente. Os apontamentos 2 e 3 foram aceitos por serem estritamente seguros (sem mudança de comportamento) e por reduzirem risco real de regressão futura.

## Testes

`pytest -q`: 167 passed, 3 skipped (Ollama real) — nenhuma regressão das duas correções aceitas. `ruff check src/domain/risk.py tests/unit/test_risk.py`: sem apontamentos.
