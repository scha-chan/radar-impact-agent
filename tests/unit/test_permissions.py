import pytest

from src.governance.permissions import PermissionDeniedError, ToolPermission, authorize
from src.graph.state import create_initial_state

DESTRUCTIVE_TOOL = ToolPermission(
    name="destructive_tool",
    permission="write:something",
    destructive=True,
    requires_approval_when=lambda state: state["human_review_required"],
)

NON_DESTRUCTIVE_TOOL = ToolPermission(
    name="read_tool", permission="read:something", destructive=False
)


def test_authorize_denies_when_review_required_and_not_approved():
    state = create_initial_state("x")
    state["human_review_required"] = True
    state["approval_decision"] = None

    with pytest.raises(PermissionDeniedError):
        authorize(DESTRUCTIVE_TOOL, state)


def test_authorize_denies_when_review_required_and_rejected():
    state = create_initial_state("x")
    state["human_review_required"] = True
    state["approval_decision"] = "REJECTED"

    with pytest.raises(PermissionDeniedError):
        authorize(DESTRUCTIVE_TOOL, state)


def test_authorize_allows_when_review_required_and_approved():
    state = create_initial_state("x")
    state["human_review_required"] = True
    state["approval_decision"] = "APPROVED"

    authorize(DESTRUCTIVE_TOOL, state)  # não deve levantar


def test_authorize_allows_when_review_not_required():
    state = create_initial_state("x")
    state["human_review_required"] = False
    state["approval_decision"] = None

    authorize(DESTRUCTIVE_TOOL, state)  # não deve levantar


def test_authorize_ignores_non_destructive_tools():
    state = create_initial_state("x")
    state["human_review_required"] = True
    state["approval_decision"] = None

    authorize(NON_DESTRUCTIVE_TOOL, state)  # sem requires_approval_when, nunca bloqueia
