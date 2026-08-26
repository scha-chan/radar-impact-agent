"""Cenário 1 do PRD (seção 12) — Fluxo principal (feliz).

Card 14 (confidence scoring): a fórmula pura (`calculate_confidence`,
`domain/risk.py`) já tem cobertura isolada desde o card 02
(`tests/unit/test_risk.py`). O que faltava provar é que `score_risk`
(o node) soma corretamente os sinais de qualidade de evidência quando as
três fontes reais — `search_codebase` (card 8), `retrieve_rag` (card 13) e
`fetch_history` (card 9) — retornam achados, produzindo confiança máxima e
publicação automática sem escalação. As tools externas são mockadas (não é
objetivo deste teste validar a API do GitHub nem o Ollama), mas o grafo
roda de ponta a ponta de verdade.
"""

from src.graph import nodes
from src.graph.build import build_graph
from src.graph.state import (
    CodeMatch,
    EvidenceSource,
    HistoryEntry,
    PatternChunk,
    Requirement,
    create_initial_state,
)
from tests.helpers import mock_llm

REQUIREMENT_TEXT = (
    "Adicionar um filtro por intervalo de data na listagem de pedidos, "
    "permitindo selecionar a data inicial e a data final desejadas."
)


def test_scenario_1_high_confidence_evidence_publishes_automatically(tmp_path, monkeypatch):
    # Sem GITHUB_TOKEN/issue_number, publish_comment (card 10) grava em
    # arquivo em vez de chamar a API real — roda em tmp_path para não sujar
    # o repo com audit/dry_run/.
    monkeypatch.chdir(tmp_path)

    mock_llm(
        monkeypatch,
        feature_type="listagem",
        search_terms=["pedidos", "listagem"],
        requirement_text=REQUIREMENT_TEXT,
    )

    monkeypatch.setattr(
        nodes,
        "search_code",
        lambda *_a, **_k: [
            CodeMatch(
                file="src/orders/orders_repository.py", snippet="def list_orders(...):", line=12
            )
        ],
    )
    monkeypatch.setattr(
        nodes,
        "retrieve_patterns",
        lambda *_a, **_k: [
            PatternChunk(
                content="Padrão de listagem: paginação, ordenação, performance de query.",
                source="knowledge/listagem.md#paginacao-e-performance",
                similarity=0.82,
            )
        ],
    )
    monkeypatch.setattr(
        nodes,
        "_fetch_history",
        lambda *_a, **_k: [
            HistoryEntry(
                type="pr", ref="PR #99", description="Ajuste recente na listagem de pedidos"
            )
        ],
    )

    graph = build_graph()
    state = create_initial_state(REQUIREMENT_TEXT)

    result = graph.invoke(state)

    # As três fontes de evidência vieram povoadas -> nenhuma dedução da
    # fórmula de confiança se aplica (requisito >= 15 palavras, código
    # encontrado, feature_type != "outro", padrão RAG encontrado, nenhuma
    # tool falhou, 3 fontes distintas em evidence_sources, sem riscos sem
    # mitigação porque analyze_impact — card 14 do LLM — ainda não gera
    # riscos, então não há o que penalizar).
    assert result["confidence"] == 100
    assert len(result["evidence_sources"]) == 3
    assert {source.type for source in result["evidence_sources"]} == {"code", "rag", "history"}

    # Sem riscos identificados, aggregate_risk_level (card 02) retorna LOW.
    assert result["risk_level"] == "LOW"
    assert result["human_review_required"] is False

    # confiança >= threshold e risco != CRITICAL -> publica sem escalar.
    assert result["published_comment_url"] is not None
    assert result["published_comment_url"].startswith("file://")


def test_scenario_1_confidence_is_reproducible_across_runs():
    # RF-05.3 estendido ao node: a mesma evidência produz sempre a mesma
    # confiança, rodando o node isoladamente (sem I/O), várias vezes.
    requirement = Requirement(
        text=REQUIREMENT_TEXT, feature_type="listagem", search_terms=["pedidos", "listagem"]
    )
    state = create_initial_state(REQUIREMENT_TEXT)
    state["requirement"] = requirement
    state["code_matches"] = [CodeMatch(file="a.py", snippet="x", line=1)]
    state["impact_patterns"] = [
        PatternChunk(content="padrao", source="knowledge/listagem.md#x", similarity=0.9)
    ]
    state["evidence_sources"] = [
        EvidenceSource(type="code", ref="a.py"),
        EvidenceSource(type="rag", ref="knowledge/listagem.md#x"),
        EvidenceSource(type="history", ref="PR #1"),
    ]

    results = {nodes.score_risk(state)["confidence"] for _ in range(20)}

    assert results == {100}
