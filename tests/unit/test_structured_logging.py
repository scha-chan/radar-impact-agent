"""RF-09.1 (card 19): um evento `node_completed` por execução de node,
com `session_id`, `correlation_id`, `node`, `status`, `duration_ms`.
"""

import pytest
from langgraph.errors import GraphInterrupt
from structlog.testing import capture_logs

from src.observability.logging import log_node_execution


def _state():
    return {"session_id": "abc123", "correlation_id": "abc123"}


def test_log_node_execution_emits_ok_event_with_required_fields():
    wrapped = log_node_execution("my_node", lambda state: {"x": 1})

    with capture_logs() as logs:
        result = wrapped(_state())

    assert result == {"x": 1}
    assert len(logs) == 1
    event = logs[0]
    assert event["event"] == "node_completed"
    assert event["session_id"] == "abc123"
    assert event["correlation_id"] == "abc123"
    assert event["node"] == "my_node"
    assert event["status"] == "ok"
    assert event["log_level"] == "info"
    assert isinstance(event["duration_ms"], (int, float))
    assert event["duration_ms"] >= 0


def test_log_node_execution_does_not_alter_the_return_value():
    wrapped = log_node_execution("n", lambda state: {"a": [1, 2], "b": "x"})

    with capture_logs():
        result = wrapped(_state())

    assert result == {"a": [1, 2], "b": "x"}


def test_log_node_execution_adds_count_fields_for_list_results():
    wrapped = log_node_execution(
        "search_codebase", lambda state: {"code_matches": [1, 2, 3], "evidence_sources": []}
    )

    with capture_logs() as logs:
        wrapped(_state())

    event = logs[0]
    assert event["code_matches_count"] == 3
    assert event["evidence_sources_count"] == 0


def test_log_node_execution_emits_error_status_and_reraises():
    def _boom(state):
        raise ValueError("kaboom")

    wrapped = log_node_execution("failing_node", _boom)

    with capture_logs() as logs, pytest.raises(ValueError, match="kaboom"):
        wrapped(_state())

    event = logs[0]
    assert event["status"] == "error"
    assert event["log_level"] == "error"
    assert event["node"] == "failing_node"


def test_log_node_execution_emits_paused_status_for_graph_interrupt_and_reraises():
    def _pause(state):
        raise GraphInterrupt([])

    wrapped = log_node_execution("human_approval", _pause)

    with capture_logs() as logs, pytest.raises(GraphInterrupt):
        wrapped(_state())

    event = logs[0]
    assert event["status"] == "paused"
    assert event["log_level"] == "info"
    assert event["node"] == "human_approval"
