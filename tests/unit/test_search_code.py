import httpx
import respx

from src.mcp_server.tools.search_code import search_code


def test_search_code_returns_empty_without_repo_or_token():
    assert search_code(["risk"], repo="", github_token="tok") == []
    assert search_code(["risk"], repo="owner/repo", github_token="") == []


@respx.mock
def test_search_code_parses_matches_with_snippet():
    respx.get("https://api.github.com/search/code").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    {
                        "path": "src/domain/risk.py",
                        "text_matches": [{"fragment": "def classify_risk(...)"}],
                    }
                ]
            },
        )
    )

    matches = search_code(["risk"], repo="owner/repo", github_token="tok")

    assert len(matches) == 1
    assert matches[0].file == "src/domain/risk.py"
    assert matches[0].snippet == "def classify_risk(...)"


@respx.mock
def test_search_code_dedupes_matches_across_terms():
    respx.get("https://api.github.com/search/code").mock(
        return_value=httpx.Response(
            200, json={"items": [{"path": "src/domain/risk.py", "text_matches": []}]}
        )
    )

    matches = search_code(["risk", "confidence"], repo="owner/repo", github_token="tok")

    assert len(matches) == 1


@respx.mock
def test_search_code_retries_then_succeeds(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda *_: None)  # nao esperar de verdade no teste

    route = respx.get("https://api.github.com/search/code")
    route.side_effect = [
        httpx.Response(500),
        httpx.Response(200, json={"items": [{"path": "a.py", "text_matches": []}]}),
    ]

    matches = search_code(["risk"], repo="owner/repo", github_token="tok", max_retries=2)

    assert len(matches) == 1
    assert route.call_count == 2


@respx.mock
def test_search_code_falls_back_to_empty_after_exhausting_retries(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda *_: None)

    route = respx.get("https://api.github.com/search/code").mock(
        return_value=httpx.Response(500)
    )

    matches = search_code(["risk"], repo="owner/repo", github_token="tok", max_retries=2)

    assert matches == []
    assert route.call_count == 3  # 1 tentativa original + 2 retries


@respx.mock
def test_search_code_respects_max_results():
    respx.get("https://api.github.com/search/code").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    {"path": f"file_{i}.py", "text_matches": []} for i in range(20)
                ]
            },
        )
    )

    matches = search_code(
        ["termo1", "termo2", "termo3"],
        repo="owner/repo",
        github_token="tok",
        max_results=3,
    )

    assert len(matches) == 3


@respx.mock
def test_search_code_records_failure_when_term_exhausts_retries(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda *_: None)
    respx.get("https://api.github.com/search/code").mock(return_value=httpx.Response(403))

    failures: list[str] = []
    matches = search_code(
        ["risk"], repo="owner/repo", github_token="tok", max_retries=2, failures=failures
    )

    assert matches == []
    assert failures == ["search_code:risk"]


@respx.mock
def test_search_code_does_not_record_failure_when_term_succeeds_with_no_results():
    respx.get("https://api.github.com/search/code").mock(
        return_value=httpx.Response(200, json={"items": []})
    )

    failures: list[str] = []
    search_code(["risk"], repo="owner/repo", github_token="tok", failures=failures)

    assert failures == []
