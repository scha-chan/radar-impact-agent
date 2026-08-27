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
from src.graph.budget import count_step, is_budget_exceeded
from src.graph.state import AgentState
from src.observability.logging import log_node_execution
from src.observability.tracing import trace_node


def _route_after_guard(state: AgentState):
    """Ramificação condicional (bloqueio) + paralelização via `Send` (RF-03)."""
    if state["is_adversarial"]:
        return "block"
    return [
        Send("search_codebase", state),
        Send("retrieve_rag", state),
        Send("fetch_history", state),
    ]


def _route_after_budget_gate(state: AgentState) -> str:
    """RF-06.5 (card 35, cenário 5): se o orçamento já estourou antes de
    `analyze_impact` começar, pula direto para `decide_autonomy` — ver
    docstring de `nodes.budget_gate`."""
    return "decide_autonomy" if is_budget_exceeded(state) else "analyze_impact"


def build_graph(checkpointer=None):
    """`checkpointer` (RF-07.1, card 15): sem ele, `human_approval` ainda
    consegue pausar (`interrupt()` não exige checkpointer para ser chamado),
    mas a pausa não sobrevive a uma nova invocação — é o que os testes que
    pré-preenchem `approval_decision` exploram para rodar o grafo inteiro
    numa única chamada, sem checkpointer nenhum. Em produção, `api/`
    (card 30) compila o grafo com `graph.checkpointer.build_checkpointer()`.
    """
    graph = StateGraph(AgentState)

    # RF-09.1 (card 19): todo node passa por log_node_execution — um único
    # ponto de instrumentação em vez de cada node logar sua própria entrada
    # e saída, para o log ficar uniforme (mesmos campos, sempre) e não
    # exigir tocar nodes.py sempre que um node novo for adicionado. Mesma
    # ideia para count_step (RF-06.5, card 35, orçamento) e trace_node
    # (RF-09.2/09.5, spans com versão fixa) — os três sinais de
    # observabilidade compartilham este único ponto de instrumentação.
    node_fns: dict[str, object] = {
        "extract_requirement": nodes.extract_requirement,
        "guard_adversarial": nodes.guard_adversarial,
        "block": nodes.block,
        "search_codebase": nodes.search_codebase,
        "retrieve_rag": nodes.retrieve_rag,
        "fetch_history": nodes.fetch_history,
        "budget_gate": nodes.budget_gate,
        "analyze_impact": nodes.analyze_impact,
        "score_risk": nodes.score_risk,
        "decide_autonomy": nodes.decide_autonomy,
        "human_approval": nodes.human_approval,
        "publish_comment": nodes.publish_comment,
        "archive": nodes.archive,
    }
    for name, fn in node_fns.items():
        graph.add_node(name, log_node_execution(name, trace_node(name, count_step(fn))))

    graph.add_edge(START, "extract_requirement")
    graph.add_edge("extract_requirement", "guard_adversarial")

    graph.add_conditional_edges(
        "guard_adversarial",
        _route_after_guard,
        ["block", "search_codebase", "retrieve_rag", "fetch_history"],
    )
    graph.add_edge("block", END)

    # Paralelização: os três nodes de evidência convergem em budget_gate
    # (fan-in) — LangGraph so dispara budget_gate apos os tres concluirem.
    # RF-06.5 (card 35): budget_gate decide se segue para analyze_impact
    # (caminho normal) ou pula direto para decide_autonomy (orçamento já
    # estourado — ver _route_after_budget_gate).
    graph.add_edge("search_codebase", "budget_gate")
    graph.add_edge("retrieve_rag", "budget_gate")
    graph.add_edge("fetch_history", "budget_gate")

    graph.add_conditional_edges(
        "budget_gate",
        _route_after_budget_gate,
        {"analyze_impact": "analyze_impact", "decide_autonomy": "decide_autonomy"},
    )

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
