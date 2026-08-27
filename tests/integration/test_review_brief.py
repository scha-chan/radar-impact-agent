"""Card 49 — `brief_escalation`: resumo, gerado pela IA, das pendências
que causaram a escalação. Roda entre `decide_autonomy` e `human_approval`.
"""

from unittest.mock import MagicMock

from langgraph.types import Command

from src.graph import nodes
from src.graph.build import build_graph
from src.graph.state import Requirement, create_initial_state
from tests.helpers import mock_llm, sqlite_checkpointer

TEXT = "Adicionar autenticação por 2FA no login dos usuários existentes."


def test_escalation_populates_review_brief(tmp_path, monkeypatch):
    mock_llm(
        monkeypatch,
        feature_type="outro",
        search_terms=[],
        review_summary="A mudança pede 2FA e escalou por falta de evidência.",
        suggested_context="Diga onde já existe integração de SMS no código.",
    )
    graph = build_graph(checkpointer=sqlite_checkpointer(tmp_path / "cp.db"))
    state = create_initial_state(TEXT)
    cfg = {"configurable": {"thread_id": state["session_id"]}}

    result = graph.invoke(state, cfg)

    assert "__interrupt__" in result
    brief = result["review_brief"]
    assert "A mudança pede 2FA" in brief
    assert "O que ajudaria numa reanálise: Diga onde já existe integração" in brief


def test_review_brief_falls_back_to_deterministic_text_on_llm_failure(monkeypatch):
    # O node é exercitado isolado: a chamada ao modelo levanta -> fallback.
    failing = MagicMock()
    failing.with_structured_output.return_value.invoke.side_effect = RuntimeError("ollama down")
    monkeypatch.setattr(nodes, "build_chat_model", lambda **_: failing)

    state = create_initial_state(TEXT)
    state["requirement"] = Requirement(text=TEXT, feature_type="login", search_terms=["2fa"])
    state["human_review_required"] = True
    state["risk_level"] = "MEDIUM"
    state["confidence"] = 40

    update = nodes.brief_escalation(state)

    brief = update["review_brief"]
    assert "Escalou porque" in brief
    assert "O que ajudaria numa reanálise" in brief


def test_brief_escalation_is_noop_when_no_review_required():
    state = create_initial_state(TEXT)
    state["human_review_required"] = False
    assert nodes.brief_escalation(state) == {}


def test_brief_escalation_handles_missing_requirement(monkeypatch):
    state = create_initial_state(TEXT)
    state["requirement"] = None
    state["human_review_required"] = True
    called = MagicMock()
    monkeypatch.setattr(nodes, "build_chat_model", called)

    update = nodes.brief_escalation(state)

    assert "Escalou porque" in update["review_brief"]
    called.assert_not_called()


def test_brief_is_regenerated_on_reanalysis(tmp_path, monkeypatch):
    mock_llm(monkeypatch, feature_type="outro", search_terms=[], review_summary="primeira versão")
    graph = build_graph(checkpointer=sqlite_checkpointer(tmp_path / "cp.db"))
    state = create_initial_state(TEXT)
    cfg = {"configurable": {"thread_id": state["session_id"]}}
    first = graph.invoke(state, cfg)
    assert "primeira versão" in first["review_brief"]

    mock_llm(monkeypatch, feature_type="outro", search_terms=[], review_summary="segunda versão")
    second = graph.invoke(Command(resume={"action": "REANALYZE", "context": None}), cfg)

    assert "segunda versão" in second["review_brief"]
