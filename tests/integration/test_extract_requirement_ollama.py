"""Smoke test contra o Ollama real — não roda em CI (não há Ollama no
runner). Ligar localmente com `RUN_OLLAMA_TESTS=1` e o serviço no ar
(`ollama serve`, modelo já baixado — ver LLM_MODEL em .env.example).
"""

import os

import pytest

from src.graph.nodes import extract_requirement
from src.graph.state import create_initial_state

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_OLLAMA_TESTS") != "1",
    reason="requer Ollama rodando localmente (RUN_OLLAMA_TESTS=1 para habilitar)",
)


def test_extract_requirement_against_real_ollama():
    state = create_initial_state(
        "Adicionar filtro por data na listagem de pedidos, permitindo "
        "selecionar intervalo inicial e final."
    )

    result = extract_requirement(state)
    requirement = result["requirement"]

    assert requirement.feature_type == "listagem"
    assert len(requirement.search_terms) >= 1
    assert result["retries_left"] == state["retries_left"]
