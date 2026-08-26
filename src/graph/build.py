"""Monta o grafo LangGraph do RADAR a partir dos nodes de `nodes.py`.

A topologia — sequencial, ramificação condicional, paralelização via `Send`,
condição de parada — é a definitiva da seção 7 do PRD, mesmo com nodes
stub. Isolar a construção do grafo em `build_graph()` permite trocar os
stubs por implementações reais (cards 6-18) sem tocar na topologia.
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from src.graph import nodes
from src.graph.state import AgentState


def _route_after_guard(state: AgentState):
    """Ramificação condicional (bloqueio) + paralelização via `Send` (RF-03)."""
    if state["is_adversarial"]:
        return "block"
    return [
        Send("search_codebase", state),
        Send("retrieve_rag", state),
        Send("fetch_history", state),
    ]


def build_graph(checkpointer=None):
    """`checkpointer` (RF-07.1, card 15): sem ele, `human_approval` ainda
    consegue pausar (`interrupt()` não exige checkpointer para ser chamado),
    mas a pausa não sobrevive a uma nova invocação — é o que os testes que
    pré-preenchem `approval_decision` exploram para rodar o grafo inteiro
    numa única chamada, sem checkpointer nenhum. Em produção, `api/`
    (card 30) compila o grafo com `graph.checkpointer.build_checkpointer()`.
    """
    graph = StateGraph(AgentState)

    graph.add_node("extract_requirement", nodes.extract_requirement)
    graph.add_node("guard_adversarial", nodes.guard_adversarial)
    graph.add_node("block", nodes.block)
    graph.add_node("search_codebase", nodes.search_codebase)
    graph.add_node("retrieve_rag", nodes.retrieve_rag)
    graph.add_node("fetch_history", nodes.fetch_history)
    graph.add_node("analyze_impact", nodes.analyze_impact)
    graph.add_node("score_risk", nodes.score_risk)
    graph.add_node("decide_autonomy", nodes.decide_autonomy)
    graph.add_node("human_approval", nodes.human_approval)
    graph.add_node("publish_comment", nodes.publish_comment)
    graph.add_node("archive", nodes.archive)

    graph.add_edge(START, "extract_requirement")
    graph.add_edge("extract_requirement", "guard_adversarial")

    graph.add_conditional_edges(
        "guard_adversarial",
        _route_after_guard,
        ["block", "search_codebase", "retrieve_rag", "fetch_history"],
    )
    graph.add_edge("block", END)

    # Paralelização: os três nodes de evidência convergem em analyze_impact
    # (fan-in) — LangGraph so dispara analyze_impact apos os tres concluirem.
    graph.add_edge("search_codebase", "analyze_impact")
    graph.add_edge("retrieve_rag", "analyze_impact")
    graph.add_edge("fetch_history", "analyze_impact")

    graph.add_edge("analyze_impact", "score_risk")
    graph.add_edge("score_risk", "decide_autonomy")

    graph.add_conditional_edges(
        "decide_autonomy",
        nodes.route_after_decision,
        {"human_approval": "human_approval", "publish_comment": "publish_comment"},
    )

    graph.add_conditional_edges(
        "human_approval",
        nodes.route_after_approval,
        {"publish_comment": "publish_comment", "archive": "archive"},
    )

    graph.add_edge("publish_comment", END)
    graph.add_edge("archive", END)

    return graph.compile(checkpointer=checkpointer)
