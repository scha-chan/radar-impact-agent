import httpx
import respx

from src.mcp_server.tools.fetch_history import fetch_history


def test_fetch_history_returns_empty_without_repo_or_token():
    assert fetch_history(["risk"], repo="", github_token="tok") == []
    assert fetch_history(["risk"], repo="owner/repo", github_token="") == []


@respx.mock
def test_fetch_history_parses_commits_and_prs():
    respx.get("https://api.github.com/search/commits").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    {
                        "sha": "abcdef1234567890",
                        "commit": {"message": "fix: corrige matriz de risco\n\ndetalhes"},
                    }
                ]
            },
        )
    )
    respx.get("https://api.github.com/search/issues").mock(
        return_value=httpx.Response(
            200, json={"items": [{"number": 42, "title": "Ajusta score_risk"}]}
        )
    )

    entries = fetch_history(["risk"], repo="owner/repo", github_token="tok")

    assert {e.type for e in entries} == {"commit", "pr"}
    commit = next(e for e in entries if e.type == "commit")
    assert commit.ref == "abcdef1"
    assert commit.description == "fix: corrige matriz de risco"
    pr = next(e for e in entries if e.type == "pr")
    assert pr.ref == "PR #42"
    assert pr.description == "Ajusta score_risk"


@respx.mock
def test_fetch_history_dedupes_across_terms():
    respx.get("https://api.github.com/search/commits").mock(
        return_value=httpx.Response(
            200, json={"items": [{"sha": "abcdef1234567890", "commit": {"message": "x"}}]}
        )
    )
    respx.get("https://api.github.com/search/issues").mock(
        return_value=httpx.Response(200, json={"items": []})
    )

    entries = fetch_history(["risk", "confidence"], repo="owner/repo", github_token="tok")

    assert len(entries) == 1


@respx.mock
def test_fetch_history_falls_back_when_commit_search_fails(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda *_: None)

    commits_route = respx.get("https://api.github.com/search/commits").mock(
        return_value=httpx.Response(500)
    )
    respx.get("https://api.github.com/search/issues").mock(
        return_value=httpx.Response(200, json={"items": [{"number": 1, "title": "x"}]})
    )

    entries = fetch_history(["risk"], repo="owner/repo", github_token="tok", max_retries=1)

    assert commits_route.call_count == 2  # 1 tentativa + 1 retry
    assert len(entries) == 1
    assert entries[0].type == "pr"


@respx.mock
def test_fetch_history_respects_max_results():
    respx.get("https://api.github.com/search/commits").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    {"sha": f"{i:07x}" + "0" * 33, "commit": {"message": "x"}} for i in range(20)
                ]
            },
        )
    )
    respx.get("https://api.github.com/search/issues").mock(
        return_value=httpx.Response(200, json={"items": []})
    )

    entries = fetch_history(["a", "b", "c"], repo="owner/repo", github_token="tok", max_results=3)

    assert len(entries) == 3


@respx.mock
def test_fetch_history_skips_commit_items_without_sha():
    respx.get("https://api.github.com/search/commits").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    {"sha": "", "commit": {"message": "sem sha"}},
                    {"sha": "abcdef1234567890", "commit": {"message": "com sha"}},
                ]
            },
        )
    )
    respx.get("https://api.github.com/search/issues").mock(
        return_value=httpx.Response(200, json={"items": []})
    )

    entries = fetch_history(["risk"], repo="owner/repo", github_token="tok")

    assert len(entries) == 1
    assert entries[0].description == "com sha"


@respx.mock
def test_fetch_history_skips_pr_items_without_number():
    respx.get("https://api.github.com/search/commits").mock(
        return_value=httpx.Response(200, json={"items": []})
    )
    respx.get("https://api.github.com/search/issues").mock(
        return_value=httpx.Response(
            200,
            json={"items": [{"title": "sem numero"}, {"number": 7, "title": "com numero"}]},
        )
    )

    entries = fetch_history(["risk"], repo="owner/repo", github_token="tok")

    assert len(entries) == 1
    assert entries[0].ref == "PR #7"


@respx.mock
def test_fetch_history_records_failure_when_both_endpoints_exhaust_retries(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda *_: None)
    respx.get("https://api.github.com/search/commits").mock(return_value=httpx.Response(403))
    respx.get("https://api.github.com/search/issues").mock(return_value=httpx.Response(403))

    failures: list[str] = []
    entries = fetch_history(
        ["risk"], repo="owner/repo", github_token="tok", max_retries=2, failures=failures
    )

    assert entries == []
    assert failures == ["fetch_history:commit:risk", "fetch_history:pr:risk"]
