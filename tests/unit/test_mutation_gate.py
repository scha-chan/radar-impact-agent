"""RNF-10 (card 37): portão de mutation score, a partir do relatório
JUnit XML gerado por `mutmut junitxml`."""

import pytest

from src.quality.mutation_gate import (
    check_mutation_score,
    compute_mutation_score,
    main,
    parse_junitxml,
)


def _write_junitxml(tmp_path, *, tests: int, failures: int = 0, errors: int = 0):
    path = tmp_path / "mutmut-report.xml"
    path.write_text(
        f'<?xml version="1.0" ?>\n'
        f'<testsuites disabled="0" errors="{errors}" failures="{failures}" tests="{tests}" time="0.0">'
        f"</testsuites>",
        encoding="utf-8",
    )
    return path


def test_compute_mutation_score_is_killed_over_total():
    assert compute_mutation_score(total=10, not_killed=2) == 80.0


def test_compute_mutation_score_counts_timeouts_against_the_score():
    # RNF-10: um mutante em timeout também não foi percebido pelos
    # testes — conta contra o score do mesmo jeito que um sobrevivente.
    assert compute_mutation_score(total=10, not_killed=5) == 50.0


def test_compute_mutation_score_is_100_when_there_are_no_mutants():
    assert compute_mutation_score(total=0, not_killed=0) == 100.0


def test_parse_junitxml_reads_totals_from_the_root_element(tmp_path):
    path = _write_junitxml(tmp_path, tests=148, failures=50)

    total, not_killed = parse_junitxml(path)

    assert total == 148
    assert not_killed == 50


def test_parse_junitxml_sums_failures_and_errors(tmp_path):
    # failures = sobreviveu; errors = timeout (mutmut junitxml) — os dois
    # contam contra o score, então parse_junitxml soma os dois.
    path = _write_junitxml(tmp_path, tests=20, failures=3, errors=2)

    total, not_killed = parse_junitxml(path)

    assert total == 20
    assert not_killed == 5


def test_check_mutation_score_passes_at_or_above_the_threshold(tmp_path, capsys):
    path = _write_junitxml(tmp_path, tests=10, failures=4)

    assert check_mutation_score(path, min_score=60.0) is True
    assert "OK" in capsys.readouterr().out


def test_check_mutation_score_fails_below_the_threshold(tmp_path, capsys):
    path = _write_junitxml(tmp_path, tests=10, failures=5)

    assert check_mutation_score(path, min_score=60.0) is False
    assert "FALHOU" in capsys.readouterr().out


def test_main_returns_zero_when_score_passes(tmp_path):
    path = _write_junitxml(tmp_path, tests=10, failures=3)

    assert main([str(path), "--min-score", "60"]) == 0


def test_main_returns_one_when_score_fails(tmp_path):
    path = _write_junitxml(tmp_path, tests=10, failures=7)

    assert main([str(path), "--min-score", "60"]) == 1


def test_main_uses_default_min_score_of_60(tmp_path):
    path = _write_junitxml(tmp_path, tests=100, failures=41)

    assert main([str(path)]) == 1
    assert compute_mutation_score(total=100, not_killed=41) == pytest.approx(59.0)
