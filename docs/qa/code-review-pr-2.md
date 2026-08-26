# Code review com IA — PR #2

**Card:** 24 — Code review com IA de um PR real
**PR analisado:** [#2 — feat(domain): matriz de risco e fórmula de confiança](https://github.com/scha-chan/radar-impact-agent/pull/2)
**Por que este PR:** sugestão explícita da seção 15 do PRD — "o PR que introduz o `score_risk`, por ser o módulo de maior criticidade". `src/domain/risk.py` é a lógica determinística que decide `risk_level`/`confidence` (RF-05), a garantia central do produto (seção 13: "o LLM não controla o `risk_level` nem o threshold de escalação").

## O diff analisado

3 arquivos de conteúdo (`src/domain/risk.py`, +119; `tests/unit/test_risk.py`, +151; `requirements.txt`, +1), mais dois renames de `.gitkeep` para `__init__.py`. Introduz `Severity`/`Probability`/`RiskLevel` (`IntEnum`), a matriz severidade × probabilidade (`classify_risk`/`aggregate_risk_level`) e a fórmula de confiança por deduções cumulativas (`calculate_confidence`), com 30 testes cobrindo a matriz completa (16 combinações), agregação, cada regra de dedução isolada, teto/piso e determinismo.

Diff completo obtido via `gh pr diff 2 --patch`.

## Processo de revisão

Revisão em 8 ângulos (correção × 3, limpeza × 3, altitude, convenções — método do skill `code-review`, nível `high`): varredura linha a linha, auditoria de comportamento removido, rastreamento cross-file, reuso, simplificação, eficiência, altitude da correção e convenções de `CLAUDE.md` (nenhum arquivo `CLAUDE.md` existe no repositório — esse ângulo não se aplica). Contrato de cada apontamento: **severidade**, **confiança** (`CONFIRMED`/`PLAUSIBLE`/`REFUTED`), **evidência** (linha + cenário concreto) e **sugestão de correção** — o mesmo contrato `Finding` da aula de revisão de código.

**Resultado da varredura de correção:** nenhum bug encontrado. A matriz de 16 combinações no código bate exatamente com a tabela da seção 11 do PRD, célula por célula (conferido manualmente). A fórmula de confiança implementa cada dedução do PRD com o valor correto, e o piso/teto (`max(0, min(100, score))`) está correto para qualquer combinação de deduções, mesmo levando `score` bem abaixo de zero antes do clamp. `classify_risk` não pode lançar `KeyError` mesmo com uso indevido de tipo (um `int` puro teria o mesmo hash/igualdade do `IntEnum` correspondente). `aggregate_risk_level([])` está protegido contra `max()` de sequência vazia pela guarda explícita. Nenhum comportamento foi removido (arquivo novo) e não havia call sites no momento do merge (a integração em `graph/nodes.py` só chega no card 04).

Três apontamentos sobreviveram à verificação — todos de manutenibilidade/cobertura, nenhum de correção:

## Apontamentos

### 1. `RiskLevel` duplica a estrutura de `Severity` — **RECUSADO**

- **Severidade:** baixa
- **Confiança:** `CONFIRMED`
- **Evidência:** `src/domain/risk.py:29-33` — `RiskLevel` tem exatamente os mesmos quatro nomes e valores de `Severity` (`src/domain/risk.py:15-19`).
- **Sugestão de correção recebida:** unificar os dois em um único `IntEnum`, eliminando a duplicação.
- **Decisão: recusado.** `Severity` (severidade de um risco individual) e `RiskLevel` (nível agregado da análise inteira) são conceitos diferentes que hoje têm a mesma escala numérica — não é garantido que continuem idênticos: o PRD já trata os dois como tabelas separadas (seção 11), e nada impede uma evolução futura (ex.: adicionar um nível abaixo de `LOW` só ao `risk_level` agregado, sem mexer em `Severity`). Unificar os dois acopla dois conceitos que só coincidem por enquanto — a duplicação de 4 linhas é um preço baixo por essa independência. Este é o tipo de apontamento que soa razoável à primeira vista mas erra a intenção de design; aceitar apontamentos de IA sem essa checagem é exatamente o oposto do que este card pede.

### 2. Deduções da fórmula de confiança são números mágicos — **ACEITO**

- **Severidade:** baixa
- **Confiança:** `CONFIRMED`
- **Evidência:** `src/domain/risk.py:147-162` (linhas do PR original) — `-20`, `-25`, `-15`, `-20`, `-15`, `-10`, `5`, `15` aparecem inline, sem nome, dentro de `calculate_confidence`.
- **Sugestão de correção:** extrair cada valor para uma constante nomeada que mapeie de volta à linha correspondente da tabela da seção 11 do PRD.
- **Decisão: aceito e aplicado.** Zero risco — são literais, não lógica; a extração não muda nenhum resultado (os 31 testes de `test_risk.py`, incluindo o novo do apontamento 3, continuam passando byte a byte). O ganho é real: `SHORT_REQUIREMENT_PENALTY`, `NO_CODE_MATCH_PENALTY`, `FEW_EVIDENCE_SOURCES_PENALTY` etc. tornam a função auto-descritiva e mais fácil de auditar contra o PRD sem abrir a especificação ao lado. Aplicado neste mesmo PR de evidência (ver diff em `src/domain/risk.py`).

### 3. Comportamento de `mitigation=""` não tinha teste — **ACEITO**

- **Severidade:** baixa
- **Confiança:** `CONFIRMED`
- **Evidência:** `src/domain/risk.py:161` (linha original) — `if not r.mitigation` trata `None` e `""` de forma idêntica; `tests/unit/test_risk.py` só testava `None` vs. uma string não vazia (`"ok"`).
- **Sugestão de correção:** adicionar um teste explícito para `mitigation=""`.
- **Decisão: aceito e aplicado.** O comportamento atual (tratar string vazia como "sem mitigação") é o correto — uma mitigação vazia não é uma mitigação real — mas não estava travado por teste. Sem essa trava, uma futura mudança de `if not r.mitigation` para `if r.mitigation is None` regrediria silenciosamente esse caso. `test_confidence_treats_empty_string_mitigation_as_missing` adicionado em `tests/unit/test_risk.py`.

## Resultado

- **1 recusado** com justificativa de design (separação deliberada de dois conceitos que coincidem apenas hoje).
- **2 aceitos e aplicados**: constantes nomeadas para as deduções da fórmula, e um teste novo travando o tratamento de mitigação vazia.
- `pytest -q`: 167 passed, 3 skipped (Ollama real), 99,10% de cobertura — nenhuma regressão introduzida pelas correções aceitas.
- `ruff check src/domain/risk.py tests/unit/test_risk.py`: sem apontamentos.

Recusar o apontamento 1 com argumento, em vez de aceitar todas as três sugestões automaticamente, é o que demonstra validação crítica sobre a saída da IA — não toda sugestão plausível é uma boa ideia, mesmo quando teria compilado e passado nos testes.
