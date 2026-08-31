"""Tracing OpenTelemetry (RF-09.2/RF-09.5/RF-09.6, seção 14 do PRD, card 35).

Terceiro sinal de observabilidade, ortogonal ao log estruturado (RF-09.1,
card 19) e à trilha de auditoria (RF-09.3, card 20) — correlacionados pelo
mesmo `session_id`/`correlation_id`, gravado como atributo em todo span.
Um span por node (RF-09.2), com `agent.version`/`prompt.version`/
`policy.version` fixos (RF-09.5, lidos do `AgentState`, não de uma
constante global direto — ver `graph/state.py`) — sem eles, uma regressão
de comportamento não é rastreável até a mudança que a causou.
"""

from __future__ import annotations

import os
from collections.abc import Callable

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

from src.graph.state import AgentState

_provider_configured = False


def configure_tracing() -> None:
    """Registra um `TracerProvider` global uma única vez (mesma ideia de
    `configure_structured_logging`, card 19) — chamar na inicialização do
    processo (API, card 30). Exporta para o console só se
    `OTEL_CONSOLE_EXPORT=true` (default desligado, para não poluir stdout
    de produção nem a saída dos testes) — trocar por um exporter OTLP real
    é só mudar este ponto, sem tocar em quem cria spans.
    """
    global _provider_configured
    if _provider_configured:
        return
    provider = TracerProvider(resource=Resource.create({"service.name": "radar-impact-agent"}))
    if os.getenv("OTEL_CONSOLE_EXPORT", "false").lower() == "true":
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    trace.set_tracer_provider(provider)
    _provider_configured = True


def get_tracer() -> trace.Tracer:
    return trace.get_tracer("radar.graph")


def version_attributes(state: AgentState) -> dict[str, str]:
    """RF-09.5: atributos fixos de versão para o span — lidos do state
    (ver docstring do módulo)."""
    return {
        "agent.version": state.get("agent_version", ""),
        "prompt.version": state.get("prompt_version", ""),
        "policy.version": state.get("policy_version", ""),
    }


NodeFn = Callable[[AgentState], dict]


def trace_node(node_name: str, fn: NodeFn) -> NodeFn:
    """Envolve um node com um span (RF-09.2), com os atributos fixos de
    versão (RF-09.5) e identificação (`session_id`/`correlation_id`) —
    mesmo ponto único de instrumentação de `log_node_execution`
    (observability/logging.py, card 19) e `count_step`
    (graph/budget.py, card 35), agora para o terceiro sinal. Atributos
    específicos do node (`gen_ai.*`, RF-09.6) são setados dentro do
    próprio node, no span corrente (`graph/nodes.py`) — este wrapper não
    sabe se o node chama LLM ou tool.
    """

    def wrapped(state: AgentState) -> dict:
        tracer = get_tracer()
        with tracer.start_as_current_span(node_name) as span:
            span.set_attribute("session.id", state.get("session_id", ""))
            span.set_attribute("correlation.id", state.get("correlation_id", ""))
            for key, value in version_attributes(state).items():
                span.set_attribute(key, value)
            return fn(state)

    return wrapped
