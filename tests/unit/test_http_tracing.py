"""RF-09.6 (card 35): W3C Trace Context (`traceparent`) nas chamadas HTTP
de saída — search_code/fetch_history (via `get_with_retry`) e
publish_comment (POST direto). Ver docstring de
`mcp_server/tools/_http.py::traceparent_headers` para a decisão de
arquitetura (sem servidor MCP real sobre HTTP hoje — instrumenta-se a
chamada de rede que de fato existe)."""

import httpx
import respx
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider

from src.mcp_server.tools._http import traceparent_headers
from src.mcp_server.tools.publish_comment import _publish_via_github_api
from src.mcp_server.tools.search_code import search_code


def test_traceparent_headers_empty_without_an_active_span():
    trace.set_tracer_provider(TracerProvider())
    assert traceparent_headers() == {}


def test_traceparent_headers_carries_the_current_span_context():
    provider = TracerProvider()
    trace.set_tracer_provider(provider)
    tracer = provider.get_tracer("test")

    with tracer.start_as_current_span("node"):
        headers = traceparent_headers()

    assert "traceparent" in headers


@respx.mock
def test_search_code_sends_traceparent_header_when_a_span_is_active():
    provider = TracerProvider()
    trace.set_tracer_provider(provider)
    tracer = provider.get_tracer("test")

    route = respx.get("https://api.github.com/search/code").mock(
        return_value=httpx.Response(200, json={"items": []})
    )

    with tracer.start_as_current_span("search_codebase"):
        search_code(["risk"], repo="owner/repo", github_token="tok")

    assert "traceparent" in route.calls.last.request.headers


@respx.mock
def test_publish_comment_sends_traceparent_header_when_a_span_is_active():
    provider = TracerProvider()
    trace.set_tracer_provider(provider)
    tracer = provider.get_tracer("test")

    route = respx.post("https://api.github.com/repos/owner/repo/issues/1/comments").mock(
        return_value=httpx.Response(201, json={"html_url": "https://example.com/1"})
    )

    with tracer.start_as_current_span("publish_comment"):
        _publish_via_github_api(
            "corpo", repo="owner/repo", issue_number=1, github_token="tok", timeout_seconds=5.0
        )

    assert "traceparent" in route.calls.last.request.headers
