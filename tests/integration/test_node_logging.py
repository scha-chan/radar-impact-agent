"""Card 19: prova que a instrumentação de `build_graph()` (não só o
wrapper isolado, `tests/unit/test_structured_logging.py`) realmente emite
um evento `node_completed` por node executado, numa corrida real do grafo.
"""

from structlog.testing import capture_logs

from src.graph.build import build_graph
from src.graph.state import create_initial_state
from tests.helpers import mock_llm


def test_graph_run_emits_node_completed_for_every_node_reached(monkeypatch):
    mock_llm(monkeypatch, feature_type="outro", search_terms=[])

    graph = build_graph()
    state = create_initial_state("Adicionar filtro por data na listagem")

    with capture_logs() as logs:
        result = graph.invoke(state)

    node_events = {log["node"]: log for log in logs if log["event"] == "node_completed"}

    # extract_requirement, guard_adversarial e os tres nodes de evidencia
    # sempre rodam neste caminho (sem search_terms -> confianca baixa ->
    # pausa em human_approval).
    for expected_node in (
        "extract_requirement",
        "guard_adversarial",
        "search_codebase",
        "retrieve_rag",
        "fetch_history",
        "analyze_impact",
        "score_risk",
        "decide_autonomy",
    ):
        assert expected_node in node_events, f"faltou log de {expected_node}"
        assert node_events[expected_node]["status"] == "ok"
        assert "duration_ms" in node_events[expected_node]

    # human_approval pausa (interrupt) - status "paused", nao "ok" nem "error".
    assert node_events["human_approval"]["status"] == "paused"
    assert "__interrupt__" in result

    # o node que causaria efeito colateral (publish_comment) nunca roda.
    assert "publish_comment" not in node_events
