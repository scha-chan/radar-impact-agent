"""Smoke test contra a API real do GitHub — não roda em CI por padrão.
Ligar localmente com `RUN_GITHUB_TESTS=1` e `GITHUB_TOKEN`/`GITHUB_REPO`
válidos no ambiente (ver .env.example).
"""

import os

import pytest

from src.mcp_server.tools.fetch_history import fetch_history

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_GITHUB_TESTS") != "1",
    reason="requer GITHUB_TOKEN real (RUN_GITHUB_TESTS=1 para habilitar)",
)


def test_fetch_history_against_real_github_repo():
    entries = fetch_history(
        ["risk"],
        repo=os.environ["GITHUB_REPO"],
        github_token=os.environ["GITHUB_TOKEN"],
    )

    assert isinstance(entries, list)
    assert all(entry.ref and entry.type in ("commit", "pr") for entry in entries)
