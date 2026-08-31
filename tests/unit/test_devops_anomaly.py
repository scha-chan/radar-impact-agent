"""Detecção multivariada de anomalia (card 40, seção 16 do PRD)."""

from src.devops.anomaly import detect_anomalies, list_outliers
from src.devops.dataset import ExecutionRow, generate_dataset


def _row(session_id: str, **overrides) -> ExecutionRow:
    base = dict(
        duration_ms=12_000,
        retries_used=0,
        confidence=85,
        tool_errors=0,
        evidence_sources_count=2,
        human_review_required=False,
    )
    base.update(overrides)
    return ExecutionRow(session_id=session_id, **base)


def test_detect_anomalies_returns_empty_list_for_empty_input():
    assert detect_anomalies([]) == []


def test_detect_anomalies_returns_one_result_per_row():
    rows = [_row(f"r{i}") for i in range(10)]
    results = detect_anomalies(rows)
    assert len(results) == 10
    assert {r.session_id for r in results} == {row.session_id for row in rows}


def test_detect_anomalies_flags_a_combination_the_baseline_would_miss():
    # RF (card 40): confianca alta com muitos retries e erros de tool e
    # poucas fontes de evidencia - uma combinacao incomum que o baseline
    # univariado (so olha human_review_required) nunca veria, ja que
    # confidence=85 nao dispara escalacao (RF-06.1/06.2).
    normal_rows = [
        _row(
            f"normal-{i}",
            duration_ms=10_000 + i * 200,
            retries_used=0,
            confidence=85 + (i % 3),
            tool_errors=0,
            evidence_sources_count=2,
        )
        for i in range(24)
    ]
    weird_row = _row(
        "weird-1",
        duration_ms=11_000,
        retries_used=5,
        confidence=90,
        tool_errors=3,
        evidence_sources_count=0,
    )
    rows = [*normal_rows, weird_row]

    results = detect_anomalies(rows, contamination=0.05)
    outliers = list_outliers(results)

    assert any(r.session_id == "weird-1" for r in outliers)


def test_list_outliers_is_sorted_from_most_to_least_anomalous():
    rows = [_row(f"r{i}", duration_ms=10_000 + i * 100) for i in range(20)]
    rows.append(_row("weird", duration_ms=90_000, retries_used=6, tool_errors=4))

    results = detect_anomalies(rows, contamination=0.1)
    outliers = list_outliers(results)

    scores = [r.score for r in outliers]
    assert scores == sorted(scores)


def test_detect_anomalies_is_deterministic_for_the_same_random_state():
    rows = generate_dataset()
    first = detect_anomalies(rows)
    second = detect_anomalies(rows)
    assert first == second


def test_detect_anomalies_on_the_real_dataset_flags_a_minority_as_outliers():
    rows = generate_dataset()
    results = detect_anomalies(rows, contamination=0.1)
    outliers = list_outliers(results)

    # contamination=0.1 sobre 50 execucoes -> por volta de 5 outliers, uma
    # minoria clara (accuracy nao e metrica util aqui - classe rara, per PRD).
    assert 0 < len(outliers) < len(rows) / 2
