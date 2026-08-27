"""Smoke test contra o Ollama real — não roda em CI (não há Ollama no
runner). Ligar localmente com `RUN_OLLAMA_TESTS=1` e o serviço no ar
(`ollama serve`, modelo já baixado — ver LLM_MODEL em .env.example).
"""

import os

import pytest

from src.quality.risk_score import classify_impact, impact_score

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_OLLAMA_TESTS") != "1",
    reason="requer Ollama rodando localmente (RUN_OLLAMA_TESTS=1 para habilitar)",
)


def test_classify_impact_against_real_ollama():
    code_excerpt = (
        "def publish_comment(state, *, repo, github_token, dry_run, ...):\n"
        "    authorize(PUBLISH_COMMENT_PERMISSION, state)\n"
        "    ...\n"
        "    return _publish_via_github_api(...)  # publica na Issue de origem"
    )

    classification = classify_impact(
        "src/mcp_server/tools/publish_comment.py", code_excerpt=code_excerpt
    )

    assert classification.criticality in {"LOW", "MEDIUM", "HIGH"}
    assert classification.blast_radius in {"LOW", "MEDIUM", "HIGH"}
    assert classification.reversibility in {"LOW", "MEDIUM", "HIGH"}
    assert classification.rationale
    assert 0.0 <= impact_score(classification) <= 1.0
