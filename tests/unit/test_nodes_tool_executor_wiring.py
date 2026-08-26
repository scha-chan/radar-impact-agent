"""Card 17: prova que search_codebase/fetch_history/publish_comment
realmente passam pelo `ToolExecutor` do módulo (`nodes._tool_executor`),
não chamam a tool direto por baixo dele — troca o executor por um vazio
(sem nenhuma permissão registrada) e confirma que a chamada é recusada,
não só coincidentemente compatível com o comportamento esperado.
"""

import pytest

from src.governance.permissions import PermissionDeniedError
from src.governance.tool_executor import ToolExecutor
from src.graph import nodes
from src.graph.state import Requirement, create_initial_state


@pytest.fixture
def empty_executor(monkeypatch):
    monkeypatch.setattr(nodes, "_tool_executor", ToolExecutor())


def _state_with_search_terms():
    state = create_initial_state("x")
    state["requirement"] = Requirement(text="x", feature_type="outro", search_terms=["termo"])
    return state


def test_search_codebase_is_refused_when_tool_is_unregistered(empty_executor):
    with pytest.raises(PermissionDeniedError):
        nodes.search_codebase(_state_with_search_terms())


def test_fetch_history_is_refused_when_tool_is_unregistered(empty_executor):
    with pytest.raises(PermissionDeniedError):
        nodes.fetch_history(_state_with_search_terms())


def test_publish_comment_node_returns_none_when_tool_is_unregistered(empty_executor):
    result = nodes.publish_comment(create_initial_state("x"))

    assert result == {"published_comment_url": None}
