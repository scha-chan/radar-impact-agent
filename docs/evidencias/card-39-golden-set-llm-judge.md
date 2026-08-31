# Card 39 — Golden set e avaliação LLM-as-judge do parecer

**Branch/PR:** `feature/eval-llm-judge`
**Extensão pós-rubrica** (seção 21 do PRD) — RF-11.

## O que foi implementado

Novo pacote `src/eval/`:

- `golden_set.py` (RF-11.1) — 20 `GoldenEntry`, cinco por cenário da seção 12 (feliz, risco alto, adversarial, resiliência), com variação deliberada de qualidade nos textos abertos (ver `docs/qa/eval-llm-judge.md` para o porquê).
- `harness.py` (RF-11.2) — camada determinística: `risk_level`/`confidence` comparados sem LLM (igualdade exata / tolerância de 10 pontos).
- `rubric.py` (RF-11.3) — juiz LLM por critério, contrato `Veredito` com `evidencia` antes de `nota`.
- `calibration.py` (RF-11.4) — Kappa de Cohen (`cohen_kappa`, implementação pura e testável sem LLM) + `calibrate_criterion` (roda o juiz contra o golden set).
- `regression.py` (RF-11.5) — mecanismo de detecção de mudança de versão (`prompt_version`/`policy_version`/`LLM_MODEL`) e diff contra baseline salvo.

Documentação principal do card (golden set, rubrica, Kappa real calculado com Ollama, casos de discordância e a decisão tomada) está em [`docs/qa/eval-llm-judge.md`](../qa/eval-llm-judge.md) — é o entregável explícito da seção 15 do PRD para este card, então o conteúdo detalhado mora lá, não duplicado aqui.

## Achado principal (resumo — detalhe completo no doc de QA)

Rodado de verdade contra Ollama (`mistral`): **os dois critérios ficaram com Kappa abaixo do limiar de confiabilidade de 0,4** (`resumo_fiel`=0,214, `testes_sustentados`=0,167) — RF-11.4 bloqueia o uso do juiz como gate automático nesse estado, e essa é a decisão tomada aqui: documentar o viés (leniência em `testes_sustentados`, rigor excessivo nas notas intermediárias de `resumo_fiel`) em vez de forçar um resultado acima do limiar.

## Testes

Todos os módulos novos com testes unitários (juiz mockado) em 100% de cobertura, mais um smoke test de integração contra Ollama real (`tests/integration/test_eval_calibration_ollama.py`, padrão `RUN_OLLAMA_TESTS=1` já usado desde o card 6) — é essa execução que produziu os números documentados em `docs/qa/eval-llm-judge.md`.

`pytest -q`: 302 passed (35 novos), 4 skipped, 99,32% de cobertura. `ruff check .`/`ruff format --check .`: sem apontamentos.
