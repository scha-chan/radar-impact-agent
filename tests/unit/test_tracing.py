"""RF-09.2/RF-09.5 (card 35): um span por node, com versão fixa."""

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from src.graph.state import create_initial_state
from src.observability import tracing


def _use_in_memory_provider(monkeypatch):
    """`configure_tracing` só registra o provider global uma vez (mesma
    ideia de `configure_structured_logging`, card 19) — os testes
    precisam do próprio provider isolado para inspecionar spans exportados
    sem depender de qual processo já chamou `configure_tracing` antes."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(tracing.trace, "get_tracer", lambda name: provider.get_tracer(name))
    return exporter


def test_version_attributes_reads_from_state():
    state = create_initial_state("x")

    attrs = tracing.version_attributes(state)

    assert attrs == {
        "agent.version": state["agent_version"],
        "prompt.version": state["prompt_version"],
        "policy.version": state["policy_version"],
    }


def test_trace_node_does_not_alter_the_return_value(monkeypatch):
    _use_in_memory_provider(monkeypatch)
    wrapped = tracing.trace_node("my_node", lambda state: {"x": 1})

    result = wrapped(create_initial_state("x"))

    assert result == {"x": 1}


def test_trace_node_emits_a_span_with_fixed_version_and_id_attributes(monkeypatch):
    exporter = _use_in_memory_provider(monkeypatch)
    wrapped = tracing.trace_node("extract_requirement", lambda state: {})
    state = create_initial_state("x")

    wrapped(state)

    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    span = spans[0]
    assert span.name == "extract_requirement"
    assert span.attributes["session.id"] == state["session_id"]
    assert span.attributes["correlation.id"] == state["correlation_id"]
    assert span.attributes["agent.version"] == state["agent_version"]
    assert span.attributes["prompt.version"] == state["prompt_version"]
    assert span.attributes["policy.version"] == state["policy_version"]


def test_configure_tracing_is_idempotent():
    tracing.configure_tracing()
    tracing.configure_tracing()  # segunda chamada não deve levantar nem reconfigurar
