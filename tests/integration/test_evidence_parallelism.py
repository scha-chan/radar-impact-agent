"""RNF-04: a coleta paralela deve ser mensuravelmente mais rápida que a
sequencial, com evidência registrada. Os três nodes de evidência têm uma
latência de I/O simulada (`nodes.STUB_IO_LATENCY_SECONDS`) só para essa
comparação ser possível antes das integrações reais (cards 8, 9, 13)
existirem.
"""

import time

from src.graph import nodes
from src.graph.build import build_graph
from src.graph.state import create_initial_state


def _run_evidence_nodes_sequentially(state) -> float:
    start = time.perf_counter()
    nodes.search_codebase(state)
    nodes.retrieve_rag(state)
    nodes.fetch_history(state)
    return time.perf_counter() - start


def test_send_fan_out_runs_evidence_nodes_concurrently():
    state = create_initial_state("Adicionar filtro por data na listagem")

    sequential_seconds = _run_evidence_nodes_sequentially(state)

    graph = build_graph()
    start = time.perf_counter()
    graph.invoke(state)
    graph_seconds = time.perf_counter() - start

    # Sequencial: ~3x STUB_IO_LATENCY_SECONDS. Paralelo via Send: ~1x, mais
    # a sobrecarga dos demais nodes do grafo (extract_requirement,
    # guard_adversarial, analyze_impact, score_risk, decide_autonomy).
    # Limiar com folga generosa para não ficar instável em CI, mas ainda
    # provando que o grafo não está apenas serializando os três nodes.
    assert graph_seconds < sequential_seconds * 0.8
