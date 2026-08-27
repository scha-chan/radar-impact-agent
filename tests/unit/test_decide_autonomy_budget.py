"""RF-06.5 (card 35, cenário 5): decide_autonomy força human_review_required
e risk_level mínimo MEDIUM quando o orçamento estoura, e budget_gate roteia
direto para decide_autonomy nesse caso."""

from src.graph import nodes
from src.graph.build import _route_after_budget_gate
from src.graph.state import create_initial_state
from src.observability.audit import read_audit_trail


def _state_with_budget_exceeded(**overrides):
    state = create_initial_state("x", max_steps=1)
    state["steps_taken"] = 1
    state["risk_level"] = "LOW"
    state["confidence"] = 90
    state.update(overrides)
    return state


def test_budget_gate_is_a_no_op_node():
    assert nodes.budget_gate(create_initial_state("x")) == {}


def test_route_after_budget_gate_goes_to_analyze_impact_when_budget_ok():
    state = create_initial_state("x")
    assert _route_after_budget_gate(state) == "analyze_impact"


def test_route_after_budget_gate_goes_to_decide_autonomy_when_budget_exceeded():
    state = _state_with_budget_exceeded()
    assert _route_after_budget_gate(state) == "decide_autonomy"


def test_decide_autonomy_forces_medium_risk_and_review_when_budget_exceeded():
    state = _state_with_budget_exceeded(risk_level="LOW", confidence=95)

    update = nodes.decide_autonomy(state)

    assert update["human_review_required"] is True
    assert update["risk_level"] == "MEDIUM"

    entries = read_audit_trail(state["session_id"])
    assert entries[-1]["decision"] == "ESCALATED_BUDGET_EXCEEDED"
    assert entries[-1]["risk_level"] == "MEDIUM"
    assert entries[-1]["steps_taken"] == 1
    assert entries[-1]["max_steps"] == 1
    assert entries[-1]["duration_seconds"] >= 0


def test_decide_autonomy_never_downgrades_a_risk_level_already_above_medium():
    state = _state_with_budget_exceeded(risk_level="CRITICAL", confidence=95)

    update = nodes.decide_autonomy(state)

    assert "risk_level" not in update  # já era CRITICAL, não regride pra MEDIUM


def test_decide_autonomy_does_not_report_budget_exceeded_when_within_budget():
    state = create_initial_state("x")
    state["risk_level"] = "CRITICAL"
    state["confidence"] = 95

    nodes.decide_autonomy(state)

    entries = read_audit_trail(state["session_id"])
    assert entries[-1]["decision"] == "ESCALATED"
    assert "steps_taken" not in entries[-1]
