"""Smoke test contra o Ollama real — não roda em CI (não há Ollama no
runner). Ligar localmente com `RUN_OLLAMA_TESTS=1` e o serviço no ar
(`ollama serve`, modelo já baixado — ver LLM_MODEL em .env.example).

RF-11.4: calibra o juiz contra o golden set inteiro, para os dois
critérios — é essa execução que produz o Kappa e os casos de discordância
documentados em `docs/qa/eval-llm-judge.md`.
"""

import os

import pytest

from src.eval.calibration import calibrate_criterion

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_OLLAMA_TESTS") != "1",
    reason="requer Ollama rodando localmente (RUN_OLLAMA_TESTS=1 para habilitar)",
)


@pytest.mark.parametrize("criterion", ["resumo_fiel", "testes_sustentados"])
def test_judge_calibration_against_the_real_golden_set(criterion):
    result = calibrate_criterion(criterion)

    assert len(result.judge_notes) == len(result.human_notes) >= 20
    assert all(note in (1, 2, 3) for note in result.judge_notes)
    # Não trava um valor exato de Kappa (o LLM não é determinístico) —
    # só que o resultado é um número válido, no intervalo esperado.
    assert -1.0 <= result.kappa <= 1.0
