"""RF-06.5 (card 35): orçamento de execução."""

from datetime import datetime, timedelta, timezone

from src.graph.budget import count_step, elapsed_seconds, is_budget_exceeded
from src.graph.state import create_initial_state


def test_count_step_adds_steps_taken_without_altering_other_fields():
    wrapped = count_step(lambda state: {"a": 1, "b": [1, 2]})

    result = wrapped({})

    assert result == {"a": 1, "b": [1, 2], "steps_taken": 1}


def test_count_step_propagates_exceptions_without_counting_a_step():
    def _boom(state):
        raise ValueError("kaboom")

    wrapped = count_step(_boom)

    try:
        wrapped({})
        raise AssertionError("deveria ter levantado")
    except ValueError:
        pass


def test_elapsed_seconds_reflects_time_since_started_at():
    state = create_initial_state("x")
    state["started_at"] = datetime.now(timezone.utc) - timedelta(seconds=10)

    assert elapsed_seconds(state) >= 10


def test_is_budget_exceeded_false_by_default():
    state = create_initial_state("x")
    assert is_budget_exceeded(state) is False


def test_is_budget_exceeded_true_when_steps_taken_reaches_max_steps():
    state = create_initial_state("x", max_steps=2)
    state["steps_taken"] = 2

    assert is_budget_exceeded(state) is True


def test_is_budget_exceeded_true_when_wall_time_exceeded():
    state = create_initial_state("x")
    state["started_at"] = datetime.now(timezone.utc) - timedelta(hours=1)

    assert is_budget_exceeded(state) is True
