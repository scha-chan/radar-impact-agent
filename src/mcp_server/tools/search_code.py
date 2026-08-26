"""Tool `search_code` — RF-03.1: busca no repositório os termos extraídos
do requisito e retorna arquivos e trechos.

Usa a API de busca de código do GitHub (`/search/code`), que exige
autenticação mesmo para repositórios públicos. RF-03.5: timeout de 10s e
até 2 retries com backoff por termo buscado (ver `_http.get_with_retry`);
um termo que esgota as tentativas é pulado (fallback) — a tool nunca lança
exceção para o grafo, na pior das hipóteses retorna lista vazia.
"""

from __future__ import annotations

import logging

import httpx

from src import config  # noqa: F401 - carrega .env como efeito colateral do import
from src.graph.state import CodeMatch
from src.mcp_server.tools._http import get_with_retry

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
            data = get_with_retry(
                client,
                "/search/code",
                {"q": f"{term} repo:{repo}", "per_page": 5},
                max_retries=max_retries,
                log_context={"tool": "search_code", "term": term},
            )
            for item in (data or {}).get("items", []):
                path = item.get("path", "")
                if not path or path in seen_files:
                    continue
                seen_files.add(path)
                matches.append(CodeMatch(file=path, snippet=_extract_snippet(item), line=None))
                if len(matches) >= max_results:
                    return matches

    return matches


def _extract_snippet(item: dict) -> str:
    text_matches = item.get("text_matches") or []
    if text_matches:
        return text_matches[0].get("fragment", "")
    return ""
