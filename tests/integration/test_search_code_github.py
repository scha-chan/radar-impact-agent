"""Smoke test contra a API real do GitHub — não roda em CI por padrão.
Ligar localmente com `RUN_GITHUB_TESTS=1` e `GITHUB_TOKEN`/`GITHUB_REPO`
válidos no ambiente (ver .env.example).

Não assume resultado específico: o índice de Code Search do GitHub tem
atraso de indexação (às vezes minutos) após um push, especialmente em
repositórios novos — `incomplete_results: true` é uma resposta 200 válida
com zero itens. O que este teste prova é que a chamada autenticada
funciona de ponta a ponta (sem erro de auth/rede/parse), não que um
arquivo específico já está indexado.
"""

import os

import pytest

from src.mcp_server.tools.search_code import search_code

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_GITHUB_TESTS") != "1",
    reason="requer GITHUB_TOKEN real (RUN_GITHUB_TESTS=1 para habilitar)",
)


def test_search_code_against_real_github_repo():
    matches = search_code(
        ["classify_risk"],
        repo=os.environ["GITHUB_REPO"],
        github_token=os.environ["GITHUB_TOKEN"],
    )

    assert isinstance(matches, list)
    assert all(match.file for match in matches)
