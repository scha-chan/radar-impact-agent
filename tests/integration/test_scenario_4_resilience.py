"""Cenário 4 do PRD (seção 12) — Falha de integração (resiliência).

Entrada: requisito cujo `search_code` bate numa API do GitHub retornando
403 (rate limit) de forma consistente. Comportamento esperado: timeout
respeitado, dois retries com backoff, fallback para análise sem evidência
de código, dedução de 25 pontos de confiança pela ausência de
`code_matches` e mais 15 pelo fallback da tool, escalação automática por
confiança baixa.

Reproduzido pelo grafo real (`build_graph().invoke`), não por chamada
isolada da tool — para provar que o sinal de falha (`tools_failed`, card
11) realmente chega em `score_risk` através do fluxo completo.

`retrieve_rag` (card 13) é mockado para retornar vazio: este cenário testa
especificamente a falha de `search_code`, não a disponibilidade do RAG —
sem o mock, o resultado dependeria de o Ollama local ter ou não o modelo de
embedding configurado (`OLLAMA_EMBED_MODEL`), o que tornaria a dedução de
confiança abaixo não determinística.
"""

import httpx
import respx

from src.graph import nodes
from src.graph.build import build_graph
from src.graph.state import create_initial_state
from tests.helpers import mock_llm


@respx.mock
def test_scenario_4_search_code_rate_limited_escalates_with_documented_deductions(
    monkeypatch,
):
    monkeypatch.setattr("time.sleep", lambda *_: None)  # nao esperar de verdade no teste
    monkeypatch.setenv("GITHUB_REPO", "owner/repo")
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    monkeypatch.setattr(nodes, "retrieve_patterns", lambda *_a, **_k: [])

    # LLM mockado: um unico termo de busca, para contar tentativas com precisao.
    mock_llm(
        monkeypatch,
        feature_type="listagem",
        search_terms=["pedidos"],
        requirement_text="Adicionar filtro por data na listagem de pedidos",
    )

    # search_code: 403 consistente (rate limit) - RF-03.5 tenta 3x (1 + 2 retries).
    code_route = respx.get("https://api.github.com/search/code").mock(
        return_value=httpx.Response(403)
    )
    # fetch_history: sem achados, mas sem falhar (nao e o alvo deste cenario).
    respx.get("https://api.github.com/search/commits").mock(
        return_value=httpx.Response(200, json={"items": []})
    )
    respx.get("https://api.github.com/search/issues").mock(
        return_value=httpx.Response(200, json={"items": []})
    )

    graph = build_graph()
    state = create_initial_state(
        "Adicionar filtro por data na listagem de pedidos", issue_number=44
    )

    result = graph.invoke(state)

    # timeout respeitado, dois retries com backoff: 1 tentativa original + 2 retries.
    assert code_route.call_count == 3

    # fallback para analise sem evidencia de codigo.
    assert result["code_matches"] == []
    assert "search_code" in result["tools_failed"]

    # dedução de 25 (sem code_matches) + 15 (tool falhou com fallback) —
    # mais as deduções já existentes por: requisito com menos de 15 palavras
    # (-20), ausência de padrão RAG (mockado para retornar vazio: -20) e
    # menos de duas fontes de evidência (-10). feature_type "listagem" não
    # é "outro", então essa dedução não se aplica.
    assert result["confidence"] == 100 - 20 - 25 - 15 - 20 - 10 == 10

    # escalação automática por confiança baixa.
    assert result["human_review_required"] is True
    assert result["published_comment_url"] is None
