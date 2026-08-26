import os

import httpx
import pytest
import respx

from src.governance.permissions import PermissionDeniedError
from src.graph.state import create_initial_state
from src.mcp_server.tools.publish_comment import publish_comment


def _approved_state(**overrides):
    state = create_initial_state("Adicionar filtro por data", issue_number=41)
    state["risk_level"] = "LOW"
    state["confidence"] = 90
    state["human_review_required"] = False
    state.update(overrides)
    return state


def test_publish_comment_denies_without_approval(tmp_path):
    state = _approved_state(human_review_required=True, approval_decision=None)

    with pytest.raises(PermissionDeniedError):
        publish_comment(state, repo="owner/repo", github_token="tok", dry_run=True)


def test_publish_comment_writes_dry_run_file(tmp_path):
    dry_dir = str(tmp_path / "audit")
    state = _approved_state()

    url = publish_comment(
        state, repo="owner/repo", github_token="tok", dry_run=True, dry_run_dir=dry_dir
    )

    assert url == f"file://{os.path.join(dry_dir, state['session_id'] + '.md')}"
    content = open(url.removeprefix("file://"), encoding="utf-8").read()
    assert "LOW" in content
    assert "90" in content
    assert state["session_id"] in content


def test_publish_comment_writes_file_when_no_issue_number_even_without_dry_run(tmp_path):
    dry_dir = str(tmp_path / "audit")
    state = _approved_state(issue_number=None)

    url = publish_comment(
        state, repo="owner/repo", github_token="tok", dry_run=False, dry_run_dir=dry_dir
    )

    assert url.startswith("file://")


@respx.mock
def test_publish_comment_calls_github_api_when_not_dry_run():
    respx.post("https://api.github.com/repos/owner/repo/issues/41/comments").mock(
        return_value=httpx.Response(
            201, json={"html_url": "https://github.com/owner/repo/issues/41#comment"}
        )
    )
    state = _approved_state()

    url = publish_comment(state, repo="owner/repo", github_token="tok", dry_run=False)

    assert url == "https://github.com/owner/repo/issues/41#comment"


@respx.mock
def test_publish_comment_returns_none_on_api_failure():
    respx.post("https://api.github.com/repos/owner/repo/issues/41/comments").mock(
        return_value=httpx.Response(500)
    )
    state = _approved_state()

    url = publish_comment(state, repo="owner/repo", github_token="tok", dry_run=False)

    assert url is None


def test_publish_comment_returns_none_without_config():
    state = _approved_state()

    url = publish_comment(state, repo="", github_token="", dry_run=False)

    assert url is None
