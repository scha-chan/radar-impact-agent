"""Card 15 — RF-07.1: suspende a execução com `interrupt()` do LangGraph,
preservando o `AgentState` no checkpointer, e retoma com a decisão humana
(RF-07.2 chega via API no card 30 — aqui simulamos a retomada diretamente
com `Command(resume=...)`, que é o mecanismo que a rota vai chamar).
"""

import sqlite3
from unittest.mock import MagicMock

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from src.graph import nodes
from src.graph.build import build_graph
from src.graph.state import Requirement, create_initial_state


def _mock_llm(monkeypatch):
    # Requisito curto, sem search_terms -> nenhuma evidência encontrada
    # (search_code/retrieve_patterns/fetch_history mockados ou reais com
    # search_terms=[] retornam vazio) -> confiança abaixo do threshold,
    # mesmo cenário de baixa evidência de test_graph.py.
    fake_requirement = Requirement(
        text="Adicionar filtro por data na listagem", feature_type="outro", search_terms=[]
    )
    chat_model = MagicMock()
    chat_model.with_structured_output.return_value.invoke.return_value = fake_requirement
    monkeypatch.setattr(nodes, "build_chat_model", lambda **_: chat_model)


def _checkpointer(db_path) -> SqliteSaver:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    return SqliteSaver(conn)


def test_human_approval_pauses_the_graph_when_confidence_is_low(tmp_path, monkeypatch):
    _mock_llm(monkeypatch)
    graph = build_graph(checkpointer=_checkpointer(tmp_path / "checkpoints.db"))
    state = create_initial_state("Adicionar filtro por data na listagem")
    config = {"configurable": {"thread_id": state["session_id"]}}

    result = graph.invoke(state, config=config)

    assert "__interrupt__" in result
    assert result["approval_decision"] is None
    assert result["published_comment_url"] is None
    assert graph.get_state(config).next == ("human_approval",)


def test_human_approval_resumes_and_publishes_on_approval(tmp_path, monkeypatch):
    _mock_llm(monkeypatch)
    monkeypatch.chdir(tmp_path)
    graph = build_graph(checkpointer=_checkpointer(tmp_path / "checkpoints.db"))
    state = create_initial_state("Adicionar filtro por data na listagem")
    config = {"configurable": {"thread_id": state["session_id"]}}
    graph.invoke(state, config=config)

    result = graph.invoke(Command(resume="APPROVED"), config=config)

    assert "__interrupt__" not in result
    assert result["approval_decision"] == "APPROVED"
    assert result["published_comment_url"] is not None
    assert result["published_comment_url"].startswith("file://")


def test_human_approval_resumes_and_archives_on_rejection(tmp_path, monkeypatch):
    _mock_llm(monkeypatch)
    graph = build_graph(checkpointer=_checkpointer(tmp_path / "checkpoints.db"))
    state = create_initial_state("Adicionar filtro por data na listagem")
    config = {"configurable": {"thread_id": state["session_id"]}}
    graph.invoke(state, config=config)

    result = graph.invoke(Command(resume="REJECTED"), config=config)

    assert result["approval_decision"] == "REJECTED"
    assert result["published_comment_url"] is None


def test_checkpointer_persists_state_across_reconnection(tmp_path, monkeypatch):
    """RF-07.1 de verdade: o state sobrevive ao processo que o pausou. Fecha
    a conexão e reabre a partir do mesmo arquivo — simulando o servidor
    reiniciando entre a pausa e a aprovação chegando (RF-07.2) — e ainda
    assim consegue retomar. Sem isso, `SqliteSaver` não seria diferente de
    um checkpointer em memória."""
    _mock_llm(monkeypatch)
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / "checkpoints.db"

    conn1 = sqlite3.connect(db_path, check_same_thread=False)
    graph1 = build_graph(checkpointer=SqliteSaver(conn1))
    state = create_initial_state("Adicionar filtro por data na listagem")
    config = {"configurable": {"thread_id": state["session_id"]}}
    graph1.invoke(state, config=config)
    conn1.close()

    conn2 = sqlite3.connect(db_path, check_same_thread=False)
    graph2 = build_graph(checkpointer=SqliteSaver(conn2))
    result = graph2.invoke(Command(resume="APPROVED"), config=config)

    assert result["approval_decision"] == "APPROVED"
    assert result["published_comment_url"] is not None
