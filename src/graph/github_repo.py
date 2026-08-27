"""Normalização do repositório do GitHub informado por execução.

O `GITHUB_REPO` do ambiente é o padrão; a interface (card 43) pode passar
outro repositório por análise, para testar o agente contra fontes
diferentes. Aceita `owner/repo`, a URL `https://github.com/owner/repo`
(com ou sem `.git`/barra final) e o formato SSH `git@github.com:owner/repo`.
"""

from __future__ import annotations

import re

_SLUG = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_URL = re.compile(
    r"^(?:https?://)?(?:git@)?(?:www\.)?github\.com[/:]"
    r"(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+?)(?:\.git)?/?$",
    re.IGNORECASE,
)


def normalize_github_repo(value: str | None) -> str | None:
    """Devolve `owner/repo` a partir de um slug ou URL do GitHub; `None` se
    a entrada for vazia. Levanta `ValueError` se não reconhecer o formato."""
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None

    if _SLUG.match(text) and "github.com" not in text.lower():
        return text.removesuffix(".git")

    match = _URL.match(text)
    if match:
        return f"{match.group('owner')}/{match.group('repo')}"

    raise ValueError(
        f"repositório do GitHub inválido: {value!r} — use 'owner/repo' ou a URL do repositório"
    )
