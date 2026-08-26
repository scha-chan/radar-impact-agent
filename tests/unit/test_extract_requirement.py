from unittest.mock import MagicMock

from src.graph import nodes
from src.graph.state import Requirement, create_initial_state


def _fake_structured_llm(*, invoke_side_effect):
    chat_model = MagicMock()
    structured = MagicMock()
    structured.invoke.side_effect = invoke_side_effect
    chat_model.with_structured_output.return_value = structured
    return chat_model


def test_extract_requirement_returns_llm_result_on_first_try(monkeypatch):
    expected = Requirement(text="x", feature_type="listagem", search_terms=["pedidos"])
    chat_model = _fake_structured_llm(invoke_side_effect=[expected])
    monkeypatch.setattr(nodes, "build_chat_model", lambda **_: chat_model)

    state = create_initial_state("Adicionar filtro por data na listagem de pedidos")
    result = nodes.extract_requirement(state)

    assert result["requirement"] == expected
    assert result["retries_left"] == state["retries_left"]


def test_extract_requirement_retries_once_then_succeeds(monkeypatch):
    expected = Requirement(text="x", feature_type="login", search_terms=["login"])
    chat_model = _fake_structured_llm(
        invoke_side_effect=[ValueError("json invalido"), expected]
    )
    monkeypatch.setattr(nodes, "build_chat_model", lambda **_: chat_model)

    state = create_initial_state("Adicionar 2FA no login", max_retries=2)
    result = nodes.extract_requirement(state)

    assert result["requirement"] == expected
    assert result["retries_left"] == 1  # gastou 1 das 2 tentativas extras


def test_extract_requirement_falls_back_after_exhausting_retries(monkeypatch):
    chat_model = _fake_structured_llm(
        invoke_side_effect=ValueError("sempre falha")
    )
    monkeypatch.setattr(nodes, "build_chat_model", lambda **_: chat_model)

    state = create_initial_state("texto qualquer", max_retries=2)
    result = nodes.extract_requirement(state)

    fallback = result["requirement"]
    assert fallback.feature_type == "outro"
    assert fallback.search_terms == []
    assert fallback.text == state["raw_requirement"]
    assert result["retries_left"] == 0


def test_extract_requirement_calls_llm_the_right_number_of_times(monkeypatch):
    chat_model = _fake_structured_llm(invoke_side_effect=ValueError("falha"))
    monkeypatch.setattr(nodes, "build_chat_model", lambda **_: chat_model)

    state = create_initial_state("texto", max_retries=3)
    nodes.extract_requirement(state)

    # max_retries=3 -> retries_left=3 -> ate 4 tentativas (1 original + 3 retries)
    structured = chat_model.with_structured_output.return_value
    assert structured.invoke.call_count == 4
