"""RF-12 (card 36): score de risco computável por módulo."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.quality.risk_score import (
    ImpactClassification,
    ModuleSignals,
    classify_impact,
    collect_signals,
    compute_probability_scores,
    cyclomatic_complexity,
    git_churn,
    git_distinct_authors,
    impact_score,
    load_coverage_percentages,
    load_weights,
    rank_modules_by_risk,
)


def _run_git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _init_repo_with_two_authors(tmp_path: Path) -> Path:
    """Repositório git real e isolado (não o do RADAR) — determinístico,
    não depende da história real evoluir. `_isolate_cwd` (conftest.py) já
    move o cwd do processo para `tmp_path`, mas `git_churn`/
    `git_distinct_authors` recebem `repo_root` explícito, independente do
    cwd do processo."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _run_git(repo, "init", "-q")
    _run_git(repo, "config", "user.email", "a@example.com")
    _run_git(repo, "config", "user.name", "Autor A")

    module = repo / "mod.py"
    module.write_text("x = 1\n", encoding="utf-8")
    _run_git(repo, "add", "mod.py")
    _run_git(repo, "commit", "-q", "-m", "primeiro commit")

    _run_git(repo, "config", "user.email", "b@example.com")
    _run_git(repo, "config", "user.name", "Autor B")
    module.write_text("x = 2\n", encoding="utf-8")
    _run_git(repo, "add", "mod.py")
    _run_git(repo, "commit", "-q", "-m", "segundo commit")

    return repo


def test_git_churn_counts_commits_touching_the_module(tmp_path):
    repo = _init_repo_with_two_authors(tmp_path)

    assert git_churn("mod.py", repo_root=repo) == 2


def test_git_churn_is_zero_for_a_module_never_committed(tmp_path):
    repo = _init_repo_with_two_authors(tmp_path)

    assert git_churn("never_existed.py", repo_root=repo) == 0


def test_git_distinct_authors_counts_unique_emails(tmp_path):
    repo = _init_repo_with_two_authors(tmp_path)

    assert git_distinct_authors("mod.py", repo_root=repo) == 2


def test_cyclomatic_complexity_reflects_branching(tmp_path):
    repo = tmp_path
    simple = repo / "simple.py"
    simple.write_text("def f():\n    return 1\n", encoding="utf-8")
    branchy = repo / "branchy.py"
    branchy.write_text(
        "def f(x):\n"
        "    if x > 0:\n"
        "        if x > 10:\n"
        "            return 1\n"
        "        return 2\n"
        "    elif x < 0:\n"
        "        return 3\n"
        "    return 0\n",
        encoding="utf-8",
    )

    assert cyclomatic_complexity("simple.py", repo_root=repo) < cyclomatic_complexity(
        "branchy.py", repo_root=repo
    )


def test_cyclomatic_complexity_is_zero_for_a_module_without_functions(tmp_path):
    module = tmp_path / "constants.py"
    module.write_text("X = 1\nY = 2\n", encoding="utf-8")

    assert cyclomatic_complexity("constants.py", repo_root=tmp_path) == 0.0


def test_load_weights_reads_the_versioned_toml():
    weights = load_weights()

    assert set(weights) == {"churn", "complexity", "authors", "coverage_gap"}
    assert all(isinstance(v, float) for v in weights.values())


def test_load_coverage_percentages_parses_coverage_json(tmp_path):
    path = tmp_path / "coverage.json"
    path.write_text(
        '{"files": {"src/a.py": {"summary": {"percent_covered": 87.5}}, '
        '"src/b.py": {"summary": {"percent_covered": 40.0}}}}',
        encoding="utf-8",
    )

    result = load_coverage_percentages(path)

    assert result == {"src/a.py": 87.5, "src/b.py": 40.0}


def test_load_coverage_percentages_normalizes_windows_separators(tmp_path):
    # coverage.py grava a chave com "\\" no Windows — normalizado para "/"
    # (mesmo separador usado em git_churn/cyclomatic_complexity), senão o
    # cruzamento por caminho nunca bate nesse SO.
    path = tmp_path / "coverage.json"
    path.write_text(
        '{"files": {"src\\\\domain\\\\risk.py": {"summary": {"percent_covered": 71.0}}}}',
        encoding="utf-8",
    )

    result = load_coverage_percentages(path)

    assert result == {"src/domain/risk.py": 71.0}


def test_collect_signals_builds_one_module_signals_per_module(tmp_path):
    repo = _init_repo_with_two_authors(tmp_path)

    signals = collect_signals(["mod.py"], coverage_by_module={"mod.py": 55.0}, repo_root=repo)

    assert signals == [
        ModuleSignals(module="mod.py", churn=2, authors=2, complexity=0.0, coverage_percent=55.0)
    ]


def test_compute_probability_scores_with_a_single_module_has_no_churn_complexity_or_authors_signal():
    # Com um único módulo, _percentile_ranks devolve 0.0 para todo mundo
    # (não há com quem comparar) — só o peso de coverage_gap sobra, porque
    # ele é invertido (1 - percentil) em vez de usar o percentil direto.
    signals = [
        ModuleSignals(module="only.py", churn=5, authors=3, complexity=6.0, coverage_percent=50.0)
    ]

    scores = compute_probability_scores(signals)

    assert scores == {"only.py": pytest.approx(load_weights()["coverage_gap"])}


def test_compute_probability_scores_ranks_riskier_module_higher():
    signals = [
        ModuleSignals(
            module="risky.py", churn=10, authors=5, complexity=8.0, coverage_percent=20.0
        ),
        ModuleSignals(module="calm.py", churn=1, authors=1, complexity=1.0, coverage_percent=95.0),
    ]

    scores = compute_probability_scores(signals)

    assert scores["risky.py"] > scores["calm.py"]


def test_compute_probability_scores_returns_zero_to_one_range():
    signals = [
        ModuleSignals(module="a.py", churn=3, authors=2, complexity=4.0, coverage_percent=60.0),
        ModuleSignals(module="b.py", churn=7, authors=4, complexity=9.0, coverage_percent=30.0),
        ModuleSignals(module="c.py", churn=0, authors=1, complexity=1.0, coverage_percent=100.0),
    ]

    scores = compute_probability_scores(signals)

    assert all(0.0 <= score <= 1.0 for score in scores.values())


def test_impact_score_high_on_every_dimension_reaches_the_maximum():
    classification = ImpactClassification(
        module="src/mcp_server/tools/publish_comment.py",
        criticality="HIGH",
        blast_radius="HIGH",
        reversibility="HIGH",
        rationale="publica externamente, sem como desfazer",
    )

    assert impact_score(classification) == 1.0


def test_impact_score_low_on_every_dimension_reaches_the_minimum():
    classification = ImpactClassification(
        module="docs/README_snippet.py",
        criticality="LOW",
        blast_radius="LOW",
        reversibility="LOW",
        rationale="script de exemplo, sem uso em produção",
    )

    assert impact_score(classification) == pytest.approx(1 / 3)


def test_classify_impact_invokes_the_llm_with_structured_output(monkeypatch):
    fake_classification = ImpactClassification(
        module="src/domain/risk.py",
        criticality="HIGH",
        blast_radius="HIGH",
        reversibility="MEDIUM",
        rationale="decide autonomia de publicação",
    )
    chat_model = MagicMock()
    chat_model.with_structured_output.return_value.invoke.return_value = fake_classification
    monkeypatch.setattr("src.graph.llm.build_chat_model", lambda **_: chat_model)

    result = classify_impact("src/domain/risk.py", code_excerpt="def classify_risk(...): ...")

    assert result == fake_classification
    chat_model.with_structured_output.assert_called_once_with(ImpactClassification)


def test_rank_modules_by_risk_orders_descending_by_probability_times_impact():
    probability_scores = {"a.py": 0.9, "b.py": 0.2}
    impact_scores = {"a.py": 0.3, "b.py": 1.0}

    ranked = rank_modules_by_risk(probability_scores, impact_scores)

    # a.py: 0.9*0.3=0.27 ; b.py: 0.2*1.0=0.2 -> a.py primeiro.
    assert [r.module for r in ranked] == ["a.py", "b.py"]
    assert ranked[0].risk == pytest.approx(0.27)


def test_rank_modules_by_risk_defaults_missing_impact_to_zero():
    ranked = rank_modules_by_risk({"only_prob.py": 0.8}, {})

    assert ranked[0].impact == 0.0
    assert ranked[0].risk == 0.0
