"""Notificação best-effort do parecer para um webhook do n8n, que
distribui no Discord (card 52).

O fluxo iniciado por Issue (webhook do GitHub → n8n → `POST /analyze` →
Discord) já entrega o card no Discord; uma análise submetida pela página
(card 30) nunca passa pelo n8n e por isso nunca chegava lá. Este módulo
fecha a lacuna: ao fim de uma análise que publicou parecer (auto ou após
aprovação), o próprio backend chama um webhook do n8n com o texto
completo do parecer — o mesmo markdown gravado em `audit/dry_run/`.

É um efeito colateral não-crítico. O POST roda numa thread daemon e
qualquer erro é engolido (n8n fora do ar, `webhook-test` desarmado
devolvendo 404, timeout) — nunca propaga para o grafo nem para a resposta
HTTP. Desligado com `N8N_NOTIFY=false` ou sem URL configurada.

Config (`.env`, lido após `docker compose up`):
  N8N_NOTIFY        "true" (padrão) | "false" desliga
  N8N_BASE_URL      http://localhost:5678 (padrão); dentro do compose: http://n8n:5678
  N8N_WEBHOOK_PATH  webhook/radar-parecer (padrão)
"""

from __future__ import annotations

import logging
import os
import threading

import httpx

from src import config  # noqa: F401 - carrega .env como efeito colateral do import

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 3.0


def _webhook_url() -> str | None:
    if os.getenv("N8N_NOTIFY", "true").strip().lower() == "false":
        return None
    base = os.getenv("N8N_BASE_URL", "http://localhost:5678").strip().rstrip("/")
    path = os.getenv("N8N_WEBHOOK_PATH", "webhook/radar-parecer").strip().lstrip("/")
    if not base or not path:
        return None
    return f"{base}/{path}"


def notify_analysis_done(
    *,
    session_id: str,
    status: str,
    risk_level: str | None,
    confidence: int | None,
    human_review_required: bool,
    parecer_markdown: str,
    report_ref: str | None,
) -> None:
    """Dispara o POST numa thread daemon e retorna na hora — quem chama
    (o node `publish_comment`) nunca espera a rede nem vê exceção."""
    url = _webhook_url()
    if not url:
        return
    payload = {
        # marcador para o n8n rotear direto ao Discord, sem re-chamar /analyze
        "source": "radar-internal",
        "session_id": session_id,
        "status": status,
        "risk_level": risk_level,
        "confidence": confidence,
        "human_review_required": human_review_required,
        # markdown completo — o mesmo body gravado em audit/dry_run/{id}.md
        "parecer": parecer_markdown,
        "report_ref": report_ref,
    }
    threading.Thread(
        target=_post_quietly,
        args=(url, payload, session_id),
        name=f"n8n-notify-{session_id}",
        daemon=True,
    ).start()


def _post_quietly(url: str, payload: dict, session_id: str) -> None:
    try:
        response = httpx.post(url, json=payload, timeout=_TIMEOUT_SECONDS)
    except Exception as exc:  # noqa: BLE001 - efeito colateral não-crítico, engole tudo
        logger.warning("n8n_notify_failed", extra={"session_id": session_id, "error": str(exc)})
        return
    if response.status_code >= 300:
        logger.warning(
            "n8n_notify_failed",
            extra={"session_id": session_id, "status_code": response.status_code},
        )
    else:
        logger.info(
            "n8n_notify_sent",
            extra={"session_id": session_id, "status_code": response.status_code},
        )
