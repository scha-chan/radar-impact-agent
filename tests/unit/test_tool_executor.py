import pytest

from src.governance.permissions import PermissionDeniedError, ToolPermission
from src.governance.tool_executor import ToolExecutor
from src.graph.state import create_initial_state

READ_TOOL = ToolPermission(name="read_tool", permission="read:something", destructive=False)

DESTRUCTIVE_TOOL = ToolPermission(
    name="destructive_tool",
    permission="write:something",
    destructive=True,
    requires_approval_when=lambda state: state["human_review_required"],
)


def test_execute_calls_the_tool_when_permission_is_registered():
    executor = ToolExecutor()
    executor.register(READ_TOOL)
    state = create_initial_state("x")

    result = executor.execute("read_tool", state, lambda: "ok")

    assert result == "ok"


def test_execute_refuses_unregistered_tool_without_calling_it():
    executor = ToolExecutor()
    state = create_initial_state("x")
    calls = []

    with pytest.raises(PermissionDeniedError):
        executor.execute("nao_registrada", state, lambda: calls.append("called"))

    assert calls == []


def test_execute_enforces_authorize_for_registered_destructive_tool():
    executor = ToolExecutor()
    executor.register(DESTRUCTIVE_TOOL)
    state = create_initial_state("x")
    state["human_review_required"] = True
    state["approval_decision"] = None
    calls = []

    with pytest.raises(PermissionDeniedError):
        executor.execute("destructive_tool", state, lambda: calls.append("called"))

    assert calls == []


def test_execute_allows_registered_destructive_tool_once_approved():
    executor = ToolExecutor()
    executor.register(DESTRUCTIVE_TOOL)
    state = create_initial_state("x")
    state["human_review_required"] = True
    state["approval_decision"] = "APPROVED"

    result = executor.execute("destructive_tool", state, lambda: "published")

    assert result == "published"


def test_register_overwrites_previous_permission_for_same_name():
    executor = ToolExecutor()
    executor.register(ToolPermission(name="x", permission="read:a", destructive=False))
    executor.register(ToolPermission(name="x", permission="read:b", destructive=False))
    state = create_initial_state("x")

    # não levanta - o segundo registro venceu, e nenhum dos dois é destrutivo.
    executor.execute("x", state, lambda: None)
