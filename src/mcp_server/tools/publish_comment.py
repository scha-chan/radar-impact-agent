"""Tool `publish_comment` — RF-08: publica o parecer como comentário
markdown na Issue de origem. A primeira ação irreversível do RADAR;
protegida por `governance.permissions.authorize` (RF-08.2/RF-08.3) e por
`DRY_RUN` (RF-08.4).

Sem retry automático na chamada real ao GitHub — diferente de
`search_code`/`fetch_history` (idempotentes, só leitura), reenviar um
POST após timeout arrisca duplicar o comentário se a primeira tentativa
tiver sucedido do lado do servidor sem a resposta chegar. Timeout ainda
se aplica (RF-03.5 é sobre tools em geral); só o retry automático fica
de fora aqui, por ser mais arriscado que útil numa ação não-idempotente.
"""

from __future__ import annotations

import logging
import os

import httpx

from src import config  # noqa: F401 - carrega .env como efeito colateral do import
from src.governance.permissions import ToolPermission, authorize
from src.graph.state import AgentState
from src.mcp_server.tools._http import traceparent_headers

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"

PUBLISH_COMMENT_PERMISSION = ToolPermission(
    name="publish_comment",
    permission="write:issue_comment",
    destructive=True,
    requires_approval_when=lambda state: state["human_review_required"],
)


def render_comment(state: AgentState) -> str:
    """Corpo markdown do parecer.

    Provisório: compõe a partir dos campos já disponíveis no state
    (risk_level, confidence, requirement). A composição definitiva a
    partir de `ImpactAnalysis` (prompt `04-compose-report`, seção 18 do
    PRD) — incluindo impacts/risks/dependencies/recommended_tests, que
    `analyze_impact` já produz desde o card 44 — é o card 45.
    """
    requirement = state["requirement"]
    lines = [
        "## Parecer RADAR",
        "",
        f"**Nível de risco:** {state['risk_level']}",
        f"**Confiança:** {state['confidence']}",
        f"**Revisão humana necessária:** {'sim' if state['human_review_required'] else 'não'}",
    ]
    if requirement is not None:
        lines += ["", f"**Tipo de feature identificado:** {requirement.feature_type}"]
    lines += ["", f"_session_id: {state['session_id']}_"]
    return "\n".join(lines)


def publish_comment(
    state: AgentState,
    *,
    repo: str,
    github_token: str,
    dry_run: bool,
    timeout_seconds: float = 10.0,
    dry_run_dir: str = "audit/dry_run",
) -> str | None:
    authorize(PUBLISH_COMMENT_PERMISSION, state)

    body = render_comment(state)
    issue_number = state["issue_number"]

    if dry_run or issue_number is None:
        return _write_dry_run_file(state, body, dry_run_dir)

    return _publish_via_github_api(
        body,
        repo=repo,
        issue_number=issue_number,
        github_token=github_token,
        timeout_seconds=timeout_seconds,
    )


def _write_dry_run_file(state: AgentState, body: str, dry_run_dir: str) -> str:
    os.makedirs(dry_run_dir, exist_ok=True)
    path = os.path.join(dry_run_dir, f"{state['session_id']}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(body)
    logger.info("publish_comment_dry_run", extra={"path": path, "session_id": state["session_id"]})
    return f"file://{path}"


def _publish_via_github_api(
    body: str, *, repo: str, issue_number: int, github_token: str, timeout_seconds: float
) -> str | None:
    if not repo or not github_token:
        logger.error(
            "publish_comment_missing_config",
            extra={"has_repo": bool(repo), "has_token": bool(github_token)},
        )
        return None

    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        **traceparent_headers(),
    }

    try:
        response = httpx.post(
            f"{GITHUB_API_BASE}/repos/{repo}/issues/{issue_number}/comments",
            headers=headers,
            json={"body": body},
            timeout=timeout_seconds,
        )
        response.raise_for_status()
    except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.TransportError) as exc:
        logger.error(
            "publish_comment_failed", extra={"issue_number": issue_number, "error": str(exc)}
        )
        return None

    return response.json().get("html_url")
