"""Card 43 — `normalize_github_repo`: aceita slug e URL, devolve `owner/repo`."""

import pytest

from src.graph.github_repo import normalize_github_repo


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, None),
        ("", None),
        ("   ", None),
        ("owner/repo", "owner/repo"),
        ("  owner/repo  ", "owner/repo"),
        ("owner/repo.git", "owner/repo"),
        ("scha-chan/radar-impact-agent", "scha-chan/radar-impact-agent"),
        ("https://github.com/owner/repo", "owner/repo"),
        ("https://github.com/owner/repo/", "owner/repo"),
        ("https://github.com/owner/repo.git", "owner/repo"),
        ("http://www.github.com/owner/repo", "owner/repo"),
        ("github.com/owner/repo", "owner/repo"),
        ("git@github.com:owner/repo.git", "owner/repo"),
    ],
)
def test_normalize_accepts_slugs_and_urls(raw, expected):
    assert normalize_github_repo(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "just-a-name",
        "owner/repo/extra",
        "https://gitlab.com/owner/repo",
        "https://github.com/owner",
        "not a repo",
    ],
)
def test_normalize_rejects_unrecognized_input(raw):
    with pytest.raises(ValueError, match="repositório do GitHub inválido"):
        normalize_github_repo(raw)
