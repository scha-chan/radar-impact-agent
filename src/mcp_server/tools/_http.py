"""GET com timeout/retry/backoff compartilhado pelas tools que chamam a API
do GitHub (RF-03.5). Timeout é configurado no `httpx.Client` de quem chama;
aqui só o retry com backoff exponencial.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

import httpx

logger = logging.getLogger(__name__)


def get_with_retry(
    client: httpx.Client,
    path: str,
    params: dict,
    *,
    max_retries: int,
    log_context: dict,
    on_exhausted: Callable[[], None] | None = None,
) -> dict | None:
    """Retorna o JSON decodificado, ou `None` se todas as tentativas
    falharem — fallback silencioso (RF-03.5); quem chama decide o que
    fazer com `None` (normalmente: pular esse item, não abortar a tool).

    `on_exhausted`, se informado, é chamado quando as tentativas se esgotam
    — usado pelo card 11 para sinalizar ao node do grafo que uma tool caiu
    em fallback (afeta o cálculo de confiança, seção 11 do PRD).
    """
    attempts = max_retries + 1
    backoff = 0.5

    for attempt in range(attempts):
        try:
            response = client.get(path, params=params)
            response.raise_for_status()
            return response.json()
        except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.TransportError) as exc:
            logger.warning(
                "github_api_call_failed",
                extra={**log_context, "attempt": attempt, "error": str(exc)},
            )
            if attempt < attempts - 1:
                time.sleep(backoff)
                backoff *= 2

    logger.error("github_api_call_exhausted_retries", extra=log_context)
    if on_exhausted is not None:
        on_exhausted()
    return None
