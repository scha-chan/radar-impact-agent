# Card 02 — Modelar a matriz de risco e a fórmula de confiança

**Branch/PR:** `feature/langgraph-agente` → [PR #2](https://github.com/scha-chan/radar-impact-agent/pull/2)
**Resultado esperado (Kanban):** `domain/risk.py` com testes

## O que foi implementado

`src/domain/risk.py`:

- `Severity`, `Probability`, `RiskLevel` (`IntEnum`, para permitir `max()` na agregação)
- `classify_risk(severity, probability)` — aplica a matriz severidade × probabilidade da seção 11 do PRD
- `aggregate_risk_level(risks)` — `risk_level` da análise = maior nível entre os riscos identificados
- `calculate_confidence(inputs)` — fórmula de dedução cumulativa (seção 11), piso 0 / teto 100

`tests/unit/test_risk.py`: 30 testes — matriz completa (16 combinações), agregação, cada regra de dedução isolada, teto de dedução por mitigação ausente, piso/teto do score, e determinismo (RF-05.3).

## Prompt utilizado

> "Com base no PRD, resolva os cards 1 e 2"

## Decisões técnicas

- `Severity`/`Probability`/`RiskLevel` como `IntEnum` (não `str, Enum`) especificamente para permitir `max()` direto na agregação — decisão que criou uma inconsistência de tipo com o schema JSON de saída (que usa strings "HIGH"/"LOW"), resolvida no card 04 com uma tabela de conversão `_SEVERITY_BY_NAME`/`_RISK_LEVEL_NAME` em `src/graph/nodes.py`
- `aggregate_risk_level([])` retorna `LOW` (não erro) — decisão não especificada no PRD, documentada no docstring
- Ambiente Python configurado neste card: `venv/` local, `pytest` instalado, primeira execução real da suíte
