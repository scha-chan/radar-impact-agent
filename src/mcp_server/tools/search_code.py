"""Tool `search_code` — RF-03.1: busca no repositório os termos extraídos
do requisito e retorna arquivos e trechos.

Usa a API de busca de código do GitHub (`/search/code`), que exige
autenticação mesmo para repositórios públicos. RF-03.5: timeout de 10s e
até 2 retries com backoff por termo buscado; um termo que esgota as
tentativas é pulado (fallback) — a tool nunca lança exceção para o grafo,
na pior das hipóteses retorna lista vazia.
"""

from __future__ import annotations

import logging
import time

import httpx

from src import config  # noqa: F401 - carrega .env como efeito colateral do import
from src.graph.state import CodeMatch

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"


def search_code(
    search_terms: list[str],
    *,
    repo: str,
    github_token: str,
    timeout_seconds: float = 10.0,
    max_retries: int = 2,
    max_terms: int = 3,
    max_results: int = 10,
) -> list[CodeMatch]:
    if not repo or not github_token:
        logger.warning(
            "search_code_missing_config",
            extra={"has_repo": bool(repo), "has_token": bool(github_token)},
        )
        return []

    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github.text-match+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    matches: list[CodeMatch] = []
    seen_files: set[str] = set()

    with httpx.Client(base_url=GITHUB_API_BASE, headers=headers, timeout=timeout_seconds) as client:
        for term in search_terms[:max_terms]:
            for item in _search_term_with_retry(client, term, repo, max_retries):
                path = item.get("path", "")
                if not path or path in seen_files:
                    continue
                seen_files.add(path)
                matches.append(CodeMatch(file=path, snippet=_extract_snippet(item), line=None))
                if len(matches) >= max_results:
                    return matches

    return matches


def _search_term_with_retry(
    client: httpx.Client, term: str, repo: str, max_retries: int
) -> list[dict]:
    query = f"{term} repo:{repo}"
    attempts = max_retries + 1
    backoff = 0.5

    for attempt in range(attempts):
        try:
            response = client.get("/search/code", params={"q": query, "per_page": 5})
            response.raise_for_status()
            return response.json().get("items", [])
        except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.TransportError) as exc:
            logger.warning(
                "search_code_term_failed",
                extra={"term": term, "attempt": attempt, "error": str(exc)},
            )
            if attempt < attempts - 1:
                time.sleep(backoff)
                backoff *= 2

    logger.error("search_code_term_exhausted_retries", extra={"term": term})
    return []


def _extract_snippet(item: dict) -> str:
    text_matches = item.get("text_matches") or []
    if text_matches:
        return text_matches[0].get("fragment", "")
    return ""
