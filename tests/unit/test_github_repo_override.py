"""Card 43 — `_effective_github_repo`: o repositório da execução
(`state["github_repo"]`, informado na interface) sobrepõe o `GITHUB_REPO`
do ambiente, e os nodes de coleta o repassam à tool.
"""

from src.graph import nodes
from src.graph.state import Requirement, create_initial_state


def _state(github_repo=None):
    state = create_initial_state("x", github_repo=github_repo)
    state["requirement"] = Requirement(text="x", feature_type="outro", search_terms=["termo"])
    return state


def test_effective_repo_prefers_state_over_env(monkeypatch):
    monkeypatch.setenv("GITHUB_REPO", "env-owner/env-repo")
    assert nodes._effective_github_repo(_state("ui-owner/ui-repo")) == "ui-owner/ui-repo"


def test_effective_repo_falls_back_to_env(monkeypatch):
    monkeypatch.setenv("GITHUB_REPO", "env-owner/env-repo")
    assert nodes._effective_github_repo(_state(None)) == "env-owner/env-repo"


def test_effective_repo_empty_when_neither_is_set(monkeypatch):
    monkeypatch.delenv("GITHUB_REPO", raising=False)
    assert nodes._effective_github_repo(_state(None)) == ""


def test_search_codebase_passes_the_state_repo_to_the_tool(monkeypatch):
    monkeypatch.setenv("GITHUB_REPO", "env-owner/env-repo")
    seen: dict[str, str] = {}

    def _fake_search_code(_terms, *, repo, github_token, failures=None):  # noqa: ARG001
        seen["repo"] = repo
        return []

    monkeypatch.setattr(nodes, "search_code", _fake_search_code)

    nodes.search_codebase(_state("ui-owner/ui-repo"))

    assert seen["repo"] == "ui-owner/ui-repo"


def test_fetch_history_passes_the_state_repo_to_the_tool(monkeypatch):
    monkeypatch.setenv("GITHUB_REPO", "env-owner/env-repo")
    seen: dict[str, str] = {}

    def _fake_fetch_history(_terms, *, repo, github_token, failures=None):  # noqa: ARG001
        seen["repo"] = repo
        return []

    monkeypatch.setattr(nodes, "_fetch_history", _fake_fetch_history)

    nodes.fetch_history(_state("ui-owner/ui-repo"))

    assert seen["repo"] == "ui-owner/ui-repo"
