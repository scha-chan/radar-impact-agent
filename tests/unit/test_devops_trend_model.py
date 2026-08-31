"""Classificador calibrado de probabilidade de escalação (card 41, seção
16 do PRD, RNF-11)."""

from src.devops.dataset import ExecutionRow, generate_dataset
from src.devops.trend_model import (
    ESCALATION_PROBABILITY_GATE_THRESHOLD,
    CalibrationReport,
    effective_confidence_threshold,
    evaluate_calibration,
    predict_escalation_probability,
    train_escalation_classifier,
)


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


def test_train_escalation_classifier_fits_without_error_on_the_real_dataset():
    model = train_escalation_classifier(generate_dataset())
    assert model is not None


def test_predict_escalation_probability_returns_a_value_between_0_and_1():
    model = train_escalation_classifier(generate_dataset())
    probability = predict_escalation_probability(model, _row("next", confidence=50))
    assert 0.0 <= probability <= 1.0


def test_predict_escalation_probability_is_higher_for_low_confidence_execution():
    model = train_escalation_classifier(generate_dataset())

    high_confidence = _row(
        "a", confidence=95, retries_used=0, tool_errors=0, evidence_sources_count=3
    )
    low_confidence = _row(
        "b", confidence=10, retries_used=2, tool_errors=2, evidence_sources_count=0
    )

    prob_high = predict_escalation_probability(model, high_confidence)
    prob_low = predict_escalation_probability(model, low_confidence)

    assert prob_low > prob_high


def test_evaluate_calibration_returns_a_well_formed_report():
    report = evaluate_calibration(generate_dataset())

    assert isinstance(report, CalibrationReport)
    assert 0.0 <= report.roc_auc <= 1.0
    assert 0.0 <= report.average_precision <= 1.0
    assert 0.0 <= report.brier_score <= 1.0


def test_effective_confidence_threshold_unchanged_below_the_gate():
    result = effective_confidence_threshold(70, predicted_escalation_probability=0.5)
    assert result == 70


def test_effective_confidence_threshold_rises_above_the_gate():
    result = effective_confidence_threshold(
        70, predicted_escalation_probability=0.85, conservative_bump=10
    )
    assert result == 80


def test_effective_confidence_threshold_is_unchanged_exactly_at_the_gate():
    # Estritamente maior que o limiar, não >= (seção 16 do PRD: "ultrapassar 70%").
    result = effective_confidence_threshold(
        70, predicted_escalation_probability=ESCALATION_PROBABILITY_GATE_THRESHOLD
    )
    assert result == 70


def test_effective_confidence_threshold_uses_default_bump_of_10():
    result = effective_confidence_threshold(70, predicted_escalation_probability=0.99)
    assert result == 80
