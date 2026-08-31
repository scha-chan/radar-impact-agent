# Avaliação de qualidade do parecer — LLM-as-judge (RF-11, card 39)

Extensão pós-rubrica (seção 21 do PRD). Implementação em `src/eval/`:
`golden_set.py` (RF-11.1), `harness.py` (camada determinística, RF-11.2),
`rubric.py` (juiz por critério, RF-11.3), `calibration.py` (Kappa de
Cohen, RF-11.4), `regression.py` (mecanismo de RF-11.5).

## Golden set (RF-11.1)

20 entradas (`src/eval/golden_set.py`), cinco por cenário, cobrindo os
quatro cenários da seção 12 do PRD:

| Cenário | Entradas | `expected_risk_level` |
|---|---|---|
| Feliz (cenário 1) | `s1-a`..`s1-e` | LOW |
| Risco alto (cenário 2) | `s2-a`..`s2-e` | HIGH (e uma variante de fronteira, MEDIUM) |
| Adversarial (cenário 3) | `s3-a`..`s3-e` | CRITICAL (e uma variante de fronteira, menção legítima a "segurança", MEDIUM) |
| Resiliência (cenário 4) | `s4-a`..`s4-e` | MEDIUM |

Cada cenário tem cinco variantes por desenho, não por acidente: **a** (resumo fiel + testes sustentados, nota 3/3), **b** (resumo fiel + testes genéricos, nota 3/1), **c** (resumo infiel + testes sustentados, nota 1/3), **d** (ambos parcialmente certos, nota 2/2), **e** (caso de fronteira — requisito curto, confiança no limite, entrada adversarial "quase legítima", falta de evidência). Sem essa variação deliberada, um golden set onde tudo tira nota 3 não daria nenhum sinal real ao Kappa — o juiz "acertaria" sem discriminar nada (`tests/unit/test_golden_set.py::test_golden_set_has_quality_variation_not_just_perfect_scores` trava isso).

## Rubrica (RF-11.3)

Dois critérios, um veredito (`Veredito`) por chamada — nunca os dois de uma vez, para o LLM não ancorar a nota de um no outro:

- **`resumo_fiel`** — o `requirement_summary` reflete fielmente o requisito original, sem inventar ou contradizer escopo?
- **`testes_sustentados`** — os `recommended_tests` são específicos e sustentados pelo requisito, ou genéricos/desconectados dele?

`Veredito` (`criterio`, `evidencia`, `nota` 1–3, `confianca`, `abstencao`) tem `evidencia` antes de `nota` na definição — como a saída estruturada é gerada campo a campo, na ordem do schema, isso força o LLM a justificar antes de pontuar.

## Kappa calculado (RF-11.4) — rodado contra Ollama real (`mistral`)

```
resumo_fiel:         Kappa = 0.214  (não confiável — abaixo de 0.4)
testes_sustentados:  Kappa = 0.167  (não confiável — abaixo de 0.4)
```

**Os dois critérios ficaram abaixo do limiar de confiabilidade (0,4, RF-11.4).** Por definição do requisito, isso **bloqueia o uso deste juiz como gate automático** até a rubrica ser revisada — a decisão tomada aqui é justamente não usá-lo como portão de qualidade automatizado enquanto isso não for corrigido, documentando o problema em vez de forçar um número acima do limiar.

### `testes_sustentados`: viés de leniência claro

```
human:  [3, 1, 3, 2, 3, 3, 1, 3, 2, 3, 3, 1, 3, 2, 3, 3, 1, 3, 2, 3]
judge:  [3, 3, 3, 2, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3]
```

O juiz deu nota 3 em 16 das 20 entradas — inclusive em toda entrada `*-b-fiel-generico`, deliberadamente rotulada com testes genéricos como `"testar a funcionalidade"`, `"testar casos de erro"`, `"testar performance"`. Um caso concreto de discordância:

> **`s1-b-fiel-generico`** — `recommended_tests = ["testar a funcionalidade", "testar casos de erro", "testar performance"]`. Rótulo humano: **1** (genéricos, poderiam se aplicar a qualquer requisito). Nota do juiz: **3**, com `evidencia`: *"os testes cobrem a funcionalidade, casos de erro e performance, que são aspectos relevantes para qualquer funcionalidade de filtro"* — a própria justificativa do juiz confirma o problema: ele reconhece que os testes "se aplicam a qualquer funcionalidade" e mesmo assim dá nota máxima, porque a rubrica atual não deixa claro que "aplicável a qualquer coisa" é o critério de reprovação, não um ponto neutro.

**Decisão tomada:** não usar `testes_sustentados` como gate automático agora. A rubrica precisa ser revisada para pedir explicitamente uma comparação contrastiva (“estes testes fariam sentido para um requisito diferente? Se sim, são genéricos demais”) em vez de perguntar só se os testes “cobrem aspectos relevantes” — o modelo local (`mistral`, 7B) tende a responder à pergunta ampla com leniência.

### `resumo_fiel`: viés na direção oposta (mais rigoroso que o humano)

```
human:  [3, 3, 1, 2, 3, 3, 3, 1, 2, 3, 3, 3, 1, 2, 3, 3, 3, 1, 2, 3]
judge:  [3, 3, 1, 1, 3, 2, 2, 1, 1, 3, 2, 1, 1, 1, 3, 2, 2, 1, 1, 2]
```

Aqui o padrão é diferente: o juiz concorda bem nos extremos (nota 3 e nota 1 batem na maioria dos casos), mas sistematicamente rebaixa a nota 2 (parcialmente fiel) para 1, e ocasionalmente rebaixa 3 para 2 — ex. `s2-a-fiel-sustentado` (resumo correto e completo, rótulo humano 3) recebeu nota 2 do juiz, com `evidencia` apontando uma imprecisão que o rótulo humano considerou aceitável ("afeta usuários existentes" vs. o texto exato do requisito). Isso sugere um juiz mais rígido que o padrão humano nas zonas intermediárias, não um erro grosseiro — mas ainda assim abaixo do limiar de confiabilidade para servir de gate sozinho.

## Regressão de eval (RF-11.5)

`src/eval/regression.py` implementa o **mecanismo** de disparo: `EvalVersionFingerprint` (captura `prompt_version`/`policy_version`/`LLM_MODEL`), `needs_rerun` (dispara quando qualquer um dos três muda desde o baseline salvo) e `diff_against_baseline` (compara o resultado por camada). Testado sem LLM nenhum (`tests/unit/test_eval_regression.py`).

**Não** foi adicionado como job de CI que chama o juiz de verdade — a chamada real (`rubric.judge`) exige Ollama rodando, indisponível no runner `ubuntu-latest` (mesma limitação já documentada para Docker/mutmut em cards anteriores). Rodar a calibração de verdade continua um passo manual local (`RUN_OLLAMA_TESTS=1 pytest tests/integration/test_eval_calibration_ollama.py`), o mesmo padrão de todo teste "Ollama real" do projeto (card 6).

## Testes

`tests/unit/test_golden_set.py`, `test_rubric.py`, `test_calibration.py`, `test_harness.py`, `test_eval_regression.py` — juiz mockado, cobertura 100% dos cinco módulos novos. `tests/integration/test_eval_calibration_ollama.py` (skip por padrão, `RUN_OLLAMA_TESTS=1` liga) — smoke test que gerou os números reais deste documento.

`pytest -q`: 302 passed (35 novos), 4 skipped (3 já existentes + este), 99,32% de cobertura. `ruff check .`/`ruff format --check .`: sem apontamentos.
