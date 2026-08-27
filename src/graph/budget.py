"""Orçamento de execução (RF-06.5, card 35) — nenhuma execução roda
indefinidamente.

`count_step` incrementa `AgentState.steps_taken` a cada node concluído —
mesmo ponto único de instrumentação de `log_node_execution` (RF-09.1, card
19), mas para contar passos em vez de logar. `is_budget_exceeded` é a
checagem usada tanto pelo roteamento condicional (`graph/build.py`, entre
o fan-in de evidência e `analyze_impact`) quanto por `decide_autonomy`
(rede de segurança para o caso de o orçamento estourar durante
`analyze_impact`/`score_risk`, depois do roteamento já ter deixado passar).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

from src.graph.state import MAX_WALL_TIME_SECONDS, AgentState

NodeFn = Callable[[AgentState], dict]


def count_step(fn: NodeFn) -> NodeFn:
    """`steps_taken` soma via `operator.add` (`AgentState`) — cada node
    contribui `+1`, inclusive os três que rodam em paralelo via `Send`
    (`search_codebase`/`retrieve_rag`/`fetch_history`), do mesmo jeito que
    `evidence_sources`/`tools_failed` já somam entradas concorrentes. Se
    `fn` levantar (inclusive `GraphInterrupt`, para pausar em
    `human_approval`), a exceção propaga sem contar o passo — uma pausa
    não é um passo concluído.
    """

    def wrapped(state: AgentState) -> dict:
        result = fn(state)
        return {**result, "steps_taken": 1}

    return wrapped


def elapsed_seconds(state: AgentState) -> float:
    return (datetime.now(timezone.utc) - state["started_at"]).total_seconds()


def is_budget_exceeded(state: AgentState) -> bool:
    return (
        state["steps_taken"] >= state["max_steps"]
        or elapsed_seconds(state) >= MAX_WALL_TIME_SECONDS
    )
