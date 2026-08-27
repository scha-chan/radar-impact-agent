"""Cenário 5 do PRD (seção 12) — Orçamento de execução estourado (RF-06.5,
card 35).

Entrada equivalente a "Issue #45, com retrieve_rag e fetch_history
respondendo lentamente o suficiente para a execução ultrapassar
max_steps antes de analyze_impact concluir": em vez de simular lentidão de
verdade (frágil e lento em CI), fixa `max_steps=0` em `create_initial_state`
— o efeito observável é o mesmo, o orçamento já está estourado quando
`budget_gate` roda, antes de `analyze_impact` sequer começar.
"""

from src.graph.build import build_graph
from src.graph.state import create_initial_state
from src.observability.audit import list_pending_sessions, read_audit_trail
from tests.helpers import mock_llm

REQUIREMENT_TEXT = "Adicionar filtro por data na listagem de pedidos."


def test_scenario_5_budget_exceeded_forces_review_and_never_runs_analyze_impact(monkeypatch):
    mock_llm(monkeypatch, feature_type="outro", search_terms=[])

    graph = build_graph()
    state = create_initial_state(REQUIREMENT_TEXT, max_steps=0, issue_number=45)

    result = graph.invoke(state)

    # 1: steps_taken >= max_steps antes de analyze_impact concluir (aqui,
    # antes mesmo de começar — budget_gate intercepta primeiro).
    # 2: nunca deixa passar como se tivesse sido totalmente analisado —
    # analyze_impact/score_risk não rodam, risk_level vai direto pra MEDIUM.
    assert result["risk_level"] == "MEDIUM"
    assert result["human_review_required"] is True
    assert result["impacts"] == []
    assert result["risks"] == []
    assert "__interrupt__" in result
    assert result["published_comment_url"] is None

    # 3: auditoria registra ESCALATED_BUDGET_EXCEEDED com steps_taken/
    # max_steps e a duração real.
    entries = read_audit_trail(result["session_id"])
    assert entries[-1]["decision"] == "ESCALATED_BUDGET_EXCEEDED"
    assert entries[-1]["steps_taken"] is not None
    assert entries[-1]["max_steps"] == 0
    assert entries[-1]["duration_seconds"] is not None


def test_scenario_5_budget_exceeded_session_shows_up_as_pending_approval(monkeypatch):
    mock_llm(monkeypatch, feature_type="outro", search_terms=[])

    graph = build_graph()
    state = create_initial_state(REQUIREMENT_TEXT, max_steps=0)

    result = graph.invoke(state)

    pending_ids = {entry["session_id"] for entry in list_pending_sessions()}
    assert result["session_id"] in pending_ids
