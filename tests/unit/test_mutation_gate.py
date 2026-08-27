"""RNF-10 (card 37): portão de mutation score."""

import json

import pytest

from src.quality.mutation_gate import check_mutation_score, compute_mutation_score, main


def _stats(**overrides) -> dict:
    base = {
        "killed": 8,
        "survived": 2,
        "total": 10,
        "no_tests": 0,
        "skipped": 0,
        "suspicious": 0,
        "timeout": 0,
        "check_was_interrupted_by_user": 0,
        "segfault": 0,
    }
    base.update(overrides)
    return base


def test_compute_mutation_score_is_killed_over_total():
    assert compute_mutation_score(_stats(killed=8, survived=2, total=10)) == 80.0


def test_compute_mutation_score_counts_no_tests_against_the_score():
    # RNF-10: um mutante sem nenhum teste passando por cima conta contra o
    # score, não é ignorado — é exatamente a lacuna que a métrica expõe.
    stats = _stats(killed=5, survived=0, no_tests=5, total=10)
    assert compute_mutation_score(stats) == 50.0


def test_compute_mutation_score_is_100_when_there_are_no_mutants():
    assert compute_mutation_score(_stats(killed=0, survived=0, total=0)) == 100.0


def test_check_mutation_score_passes_at_or_above_the_threshold(tmp_path, capsys):
    path = tmp_path / "stats.json"
    path.write_text(json.dumps(_stats(killed=6, survived=4, total=10)), encoding="utf-8")

    assert check_mutation_score(path, min_score=60.0) is True
    assert "OK" in capsys.readouterr().out


def test_check_mutation_score_fails_below_the_threshold(tmp_path, capsys):
    path = tmp_path / "stats.json"
    path.write_text(json.dumps(_stats(killed=5, survived=5, total=10)), encoding="utf-8")

    assert check_mutation_score(path, min_score=60.0) is False
    assert "FALHOU" in capsys.readouterr().out


def test_main_returns_zero_when_score_passes(tmp_path):
    path = tmp_path / "stats.json"
    path.write_text(json.dumps(_stats(killed=7, survived=3, total=10)), encoding="utf-8")

    assert main([str(path), "--min-score", "60"]) == 0


def test_main_returns_one_when_score_fails(tmp_path):
    path = tmp_path / "stats.json"
    path.write_text(json.dumps(_stats(killed=3, survived=7, total=10)), encoding="utf-8")

    assert main([str(path), "--min-score", "60"]) == 1


def test_main_uses_default_min_score_of_60(tmp_path):
    path = tmp_path / "stats.json"
    path.write_text(json.dumps(_stats(killed=59, survived=41, total=100)), encoding="utf-8")

    assert main([str(path)]) == 1
    assert compute_mutation_score(_stats(killed=59, survived=41, total=100)) == pytest.approx(59.0)
