"""Tool `fetch_history` — RF-03.3: busca commits e PRs recentes relacionados
aos termos do requisito, via API de busca do GitHub.

Usa os mesmos `search_terms` de `search_code` (não os arquivos que ele
encontrou) — as duas tools rodam em paralelo no fan-out via `Send` (seção 7
do PRD), então `fetch_history` não pode depender do resultado de
`search_code` sem quebrar a paralelização. `analyze_impact` correlaciona os
dois depois.

RF-03.5: timeout de 10s, até 2 retries com backoff por termo/endpoint (ver
`_http.get_with_retry`); combinação termo+endpoint que esgota as tentativas
é pulada (fallback) — a tool nunca lança exceção.
"""

from __future__ import annotations

import httpx

from src import config  # noqa: F401 - carrega .env como efeito colateral do import
from src.governance.permissions import ToolPermission
from src.graph.state import HistoryEntry
from src.mcp_server.tools._http import get_with_retry

GITHUB_API_BASE = "https://api.github.com"

# RF-08.2/card 17: leitura, não destrutiva — mesmo racional de
# SEARCH_CODE_PERMISSION em search_code.py.
FETCH_HISTORY_PERMISSION = ToolPermission(
    name="fetch_history", permission="read:history", destructive=False
)


def fetch_history(
    search_terms: list[str],
    *,
    repo: str,
    github_token: str,
    timeout_seconds: float = 10.0,
    max_retries: int = 2,
    max_terms: int = 3,
    max_results: int = 10,
    failures: list[str] | None = None,
) -> list[HistoryEntry]:
    """`failures`, se informado, recebe um item por termo/endpoint cuja
    busca esgotou as tentativas (card 11 — sinal de fallback para
    score_risk)."""
    if not repo or not github_token:
        return []

    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    entries: list[HistoryEntry] = []
    seen_refs: set[str] = set()

    with httpx.Client(base_url=GITHUB_API_BASE, headers=headers, timeout=timeout_seconds) as client:
        for term in search_terms[:max_terms]:
            for entry in [
                *_search_commits(client, term, repo, max_retries, failures),
                *_search_prs(client, term, repo, max_retries, failures),
            ]:
                if entry.ref in seen_refs:
                    continue
                seen_refs.add(entry.ref)
                entries.append(entry)
                if len(entries) >= max_results:
                    return entries

    return entries


def _search_commits(
    client: httpx.Client, term: str, repo: str, max_retries: int, failures: list[str] | None
) -> list[HistoryEntry]:
    data = get_with_retry(
        client,
        "/search/commits",
        {"q": f"{term} repo:{repo}", "per_page": 5},
        max_retries=max_retries,
        log_context={"tool": "fetch_history", "kind": "commit", "term": term},
        on_exhausted=(lambda t=term: failures.append(f"fetch_history:commit:{t}"))
        if failures is not None
        else None,
    )
    entries = []
    for item in (data or {}).get("items", []):
        sha = item.get("sha", "")
        if not sha:
            continue
        message = (item.get("commit") or {}).get("message", "")
        first_line = message.splitlines()[0] if message else ""
        entries.append(HistoryEntry(type="commit", ref=sha[:7], description=first_line))
    return entries


def _search_prs(
    client: httpx.Client, term: str, repo: str, max_retries: int, failures: list[str] | None
) -> list[HistoryEntry]:
    data = get_with_retry(
        client,
        "/search/issues",
        {"q": f"{term} repo:{repo} type:pr", "per_page": 5},
        max_retries=max_retries,
        log_context={"tool": "fetch_history", "kind": "pr", "term": term},
        on_exhausted=(lambda t=term: failures.append(f"fetch_history:pr:{t}"))
        if failures is not None
        else None,
    )
    entries = []
    for item in (data or {}).get("items", []):
        number = item.get("number")
        if number is None:
            continue
        entries.append(
            HistoryEntry(type="pr", ref=f"PR #{number}", description=item.get("title", ""))
        )
    return entries
