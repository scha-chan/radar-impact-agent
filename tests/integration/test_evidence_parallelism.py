"""RNF-04: a coleta paralela deve ser mensuravelmente mais rápida que a
sequencial, com evidência registrada.

`retrieve_rag` ainda é stub (card 13) e usa `STUB_IO_LATENCY_SECONDS`.
`search_codebase` e `fetch_history` já são reais (cards 8-9) — mocamos as
chamadas de rede subjacentes (`search_code`/`_fetch_history`) com a mesma
latência simulada, para a comparação continuar válida independente de
haver ou não `GITHUB_TOKEN` configurado no ambiente de teste.
"""

import time
from unittest.mock import MagicMock

from src.graph import nodes
from src.graph.build import build_graph
from src.graph.state import Requirement, create_initial_state


def _fake_io_call(*_args, **_kwargs):
    time.sleep(nodes.STUB_IO_LATENCY_SECONDS)
    return []


def _run_evidence_nodes_sequentially(state) -> float:
    start = time.perf_counter()
    nodes.search_codebase(state)
    nodes.retrieve_rag(state)
    nodes.fetch_history(state)
    return time.perf_counter() - start


def test_send_fan_out_runs_evidence_nodes_concurrently(monkeypatch):
    # extract_requirement chama um LLM real; mockado aqui para o benchmark
    # medir só o fan-out via Send, não latência de rede do Ollama.
    fake_requirement = Requirement(
        text="x", feature_type="outro", search_terms=["termo"]
    )
    chat_model = MagicMock()
    chat_model.with_structured_output.return_value.invoke.return_value = fake_requirement
    monkeypatch.setattr(nodes, "build_chat_model", lambda **_: chat_model)

    # search_codebase e fetch_history já são reais (cards 8-9); simulamos a
    # latência de rede deles para o benchmark não depender de GITHUB_TOKEN.
    monkeypatch.setattr(nodes, "search_code", _fake_io_call)
    monkeypatch.setattr(nodes, "_fetch_history", _fake_io_call)

    state = create_initial_state("Adicionar filtro por data na listagem")
    # search_codebase/fetch_history só chamam a rede se houver search_terms;
    # graph.invoke() preenche isso via extract_requirement (mockado acima),
    # mas a medição sequencial chama os nodes direto, sem passar por ele.
    state["requirement"] = fake_requirement

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
