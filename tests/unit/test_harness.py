"""RF-11.2 (card 39): camada determinística — risk_level/confidence sem
LLM."""

from src.eval.golden_set import GoldenEntry
from src.eval.harness import evaluate_deterministic_layer


def _entry() -> GoldenEntry:
    return GoldenEntry(
        id="e1",
        scenario="feliz",
        raw_requirement="x",
        expected_risk_level="LOW",
        expected_confidence=100,
        requirement_summary="y",
        recommended_tests=["t1"],
        human_notes={"resumo_fiel": 3, "testes_sustentados": 3},
    )


def test_passes_on_exact_match():
    result = evaluate_deterministic_layer(
        _entry(), candidate_risk_level="LOW", candidate_confidence=100
    )
    assert result.risk_level_match is True
    assert result.confidence_within_tolerance is True
    assert result.passed is True


def test_fails_on_risk_level_mismatch():
    result = evaluate_deterministic_layer(
        _entry(), candidate_risk_level="HIGH", candidate_confidence=100
    )
    assert result.risk_level_match is False
    assert result.passed is False


def test_passes_within_confidence_tolerance():
    result = evaluate_deterministic_layer(
        _entry(), candidate_risk_level="LOW", candidate_confidence=90
    )
    assert result.confidence_within_tolerance is True
    assert result.passed is True


def test_fails_outside_confidence_tolerance():
    result = evaluate_deterministic_layer(
        _entry(), candidate_risk_level="LOW", candidate_confidence=85
    )
    assert result.confidence_within_tolerance is False
    assert result.passed is False


def test_confidence_tolerance_boundary_is_inclusive():
    entry = _entry()
    from src.eval.harness import CONFIDENCE_TOLERANCE

    boundary = entry.expected_confidence - CONFIDENCE_TOLERANCE
    result = evaluate_deterministic_layer(
        entry, candidate_risk_level="LOW", candidate_confidence=boundary
    )
    assert result.confidence_within_tolerance is True
