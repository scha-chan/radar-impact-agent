"""Logs estruturados JSON por node do grafo (RF-09.1, seção 14 do PRD, card 19).

Sinal 1 de observabilidade: um evento `node_completed` por execução de
node, correlacionado por `session_id`/`correlation_id`. O segundo sinal
(trilha de auditoria JSONL) e a correlação formal entre os dois sinais é o
card 20.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

import structlog
from langgraph.errors import GraphInterrupt

from src.graph.state import AgentState

NodeFn = Callable[[AgentState], dict]

_log = structlog.get_logger("radar.graph.node")


def configure_structured_logging(level: int = logging.INFO) -> None:
    """Configura structlog para emitir uma linha JSON por evento
    (timestamp ISO8601 UTC, nível, campos estruturados). Chamar uma vez na
    inicialização do processo (API, card 30, ou scripts) — os testes deste
    card usam `structlog.testing.capture_logs()` em vez de configurar o
    renderer JSON de verdade, então não precisam chamar isto.
    """
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso", utc=True, key="timestamp"),
            structlog.processors.add_log_level,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def _count_fields(result: dict) -> dict[str, int]:
    """Replica o `matches_found` do exemplo da seção 14 do PRD de forma
    genérica: qualquer campo de lista que o node devolveu vira uma
    contagem no log, sem precisar de código específico por node (ex.:
    `search_codebase` devolvendo `code_matches` gera `code_matches_count`).
    """
    return {f"{key}_count": len(value) for key, value in result.items() if isinstance(value, list)}


def log_node_execution(node_name: str, fn: NodeFn) -> NodeFn:
    """Envolve um node do grafo para emitir `node_completed` (RF-09.1)
    depois de cada execução, com `duration_ms` e `status`. Não altera o
    valor de retorno do node — só observa.

    `GraphInterrupt` (a exceção interna que o LangGraph usa para pausar em
    `interrupt()`, card 15) é tratada à parte: pausar não é uma falha, e
    logar como `status="error"` confundiria quem lesse o log depois. Toda
    outra exceção é `status="error"` e é relançada sem alteração — este
    wrapper só observa, nunca engole uma falha do node.
    """

    def wrapped(state: AgentState) -> dict:
        started_at = time.perf_counter()
        try:
            result = fn(state)
        except GraphInterrupt:
            _log.info(
                "node_completed",
                session_id=state.get("session_id"),
                correlation_id=state.get("correlation_id"),
                node=node_name,
                status="paused",
                duration_ms=_elapsed_ms(started_at),
            )
            raise
        except Exception:
            _log.error(
                "node_completed",
                session_id=state.get("session_id"),
                correlation_id=state.get("correlation_id"),
                node=node_name,
                status="error",
                duration_ms=_elapsed_ms(started_at),
            )
            raise

        _log.info(
            "node_completed",
            session_id=state.get("session_id"),
            correlation_id=state.get("correlation_id"),
            node=node_name,
            status="ok",
            duration_ms=_elapsed_ms(started_at),
            **_count_fields(result),
        )
        return result

    return wrapped


def _elapsed_ms(started_at: float) -> float:
    return round((time.perf_counter() - started_at) * 1000, 2)
