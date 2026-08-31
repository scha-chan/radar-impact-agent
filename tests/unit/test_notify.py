"""Card 52: `notify_analysis_done` é best-effort — sem URL configurada é
no-op, e nenhuma falha do POST (exceção de rede ou HTTP não-2xx) propaga
para quem chama (o node `publish_comment`)."""

import httpx
import pytest

import src.observability.notify as notify


def _kwargs(**over):
    base = dict(
        session_id="s1",
        status="published",
        risk_level="LOW",
        confidence=80,
        human_review_required=False,
        parecer_markdown="## Parecer RADAR\n\nresumo...",
        report_ref="file://audit/dry_run/s1.md",
    )
    base.update(over)
    return base


class _RecordingThread:
    """Substitui threading.Thread rodando o target de forma síncrona, para
    o teste conseguir observar o efeito sem corrida."""

    instances: list["_RecordingThread"] = []

    def __init__(self, target, args=(), kwargs=None, name=None, daemon=None):
        self._target, self._args, self._kwargs = target, args, kwargs or {}
        self.daemon = daemon
        _RecordingThread.instances.append(self)

    def start(self):
        self._target(*self._args, **self._kwargs)


@pytest.fixture(autouse=True)
def _sync_threads(monkeypatch):
    _RecordingThread.instances = []
    monkeypatch.setattr(notify.threading, "Thread", _RecordingThread)


def test_no_url_is_a_noop(monkeypatch):
    monkeypatch.setenv("N8N_NOTIFY", "false")

    def _boom(*a, **k):
        raise AssertionError("não deveria postar quando N8N_NOTIFY=false")

    monkeypatch.setattr(notify.httpx, "post", _boom)

    notify.notify_analysis_done(**_kwargs())

    assert _RecordingThread.instances == []


def test_blank_base_url_is_a_noop(monkeypatch):
    monkeypatch.setenv("N8N_NOTIFY", "true")
    monkeypatch.setenv("N8N_BASE_URL", "")

    def _boom(*a, **k):
        raise AssertionError("não deveria postar sem base URL")

    monkeypatch.setattr(notify.httpx, "post", _boom)

    notify.notify_analysis_done(**_kwargs())

    assert _RecordingThread.instances == []


def test_posts_expected_payload_when_enabled(monkeypatch):
    monkeypatch.setenv("N8N_NOTIFY", "true")
    monkeypatch.setenv("N8N_BASE_URL", "http://n8n.test:5678/")
    monkeypatch.setenv("N8N_WEBHOOK_PATH", "/webhook/radar-parecer")
    sent = {}

    def _capture(url, json, timeout):
        sent["url"] = url
        sent["json"] = json
        return httpx.Response(204)

    monkeypatch.setattr(notify.httpx, "post", _capture)

    notify.notify_analysis_done(**_kwargs(session_id="abc"))

    assert sent["url"] == "http://n8n.test:5678/webhook/radar-parecer"
    assert sent["json"]["source"] == "radar-internal"
    assert sent["json"]["session_id"] == "abc"
    assert sent["json"]["parecer"].startswith("## Parecer RADAR")


def test_connection_error_never_propagates(monkeypatch):
    monkeypatch.setenv("N8N_NOTIFY", "true")

    def _raise(*a, **k):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(notify.httpx, "post", _raise)

    notify.notify_analysis_done(**_kwargs())  # não levanta


def test_non_2xx_never_propagates(monkeypatch):
    monkeypatch.setenv("N8N_NOTIFY", "true")
    monkeypatch.setattr(notify.httpx, "post", lambda *a, **k: httpx.Response(404))

    notify.notify_analysis_done(**_kwargs())  # 404 do webhook-test desarmado — engolido
