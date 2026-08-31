"""RF-11.4 (card 39): Kappa de Cohen e calibração do juiz contra o
golden set (juiz mockado — o smoke test com Ollama real fica em
tests/integration/test_eval_calibration_ollama.py)."""

from unittest.mock import patch

import pytest

from src.eval.calibration import (
    KAPPA_BLOCK_THRESHOLD,
    CriterionCalibration,
    calibrate_criterion,
    cohen_kappa,
)
from src.eval.golden_set import GoldenEntry
from src.eval.rubric import Veredito


def test_cohen_kappa_is_1_for_perfect_agreement():
    assert cohen_kappa([1, 2, 3, 1, 2, 3], [1, 2, 3, 1, 2, 3]) == pytest.approx(1.0)


def test_cohen_kappa_is_1_when_both_sides_have_no_variation():
    # Sem variação nenhuma (todo mundo "3" dos dois lados), a fórmula
    # padrão divide por zero — tratado como concordância perfeita.
    assert cohen_kappa([3, 3, 3], [3, 3, 3]) == 1.0


def test_cohen_kappa_is_negative_for_systematic_disagreement():
    # Cada rótulo "1" do lado A vira "3" do lado B e vice-versa - pior
    # que o acaso (categorias sempre trocadas, nunca coincidem).
    assert cohen_kappa([1, 1, 3, 3], [3, 3, 1, 1]) < 0


def test_cohen_kappa_raises_on_mismatched_lengths():
    with pytest.raises(ValueError, match="mesmo tamanho"):
        cohen_kappa([1, 2], [1, 2, 3])


def test_cohen_kappa_raises_on_empty_input():
    with pytest.raises(ValueError, match="sem rótulos"):
        cohen_kappa([], [])


def _entry(entry_id: str, criterion_note: int) -> GoldenEntry:
    return GoldenEntry(
        id=entry_id,
        scenario="feliz",
        raw_requirement="x",
        expected_risk_level="LOW",
        expected_confidence=100,
        requirement_summary="y",
        recommended_tests=["t1"],
        human_notes={"resumo_fiel": criterion_note, "testes_sustentados": criterion_note},
    )


def test_calibrate_criterion_agrees_with_a_perfect_judge():
    entries = [_entry("e1", 3), _entry("e2", 1), _entry("e3", 2)]
    # Juiz "perfeito": os veredictos são fornecidos na mesma ordem das
    # entradas, cada um repetindo a nota humana correspondente.
    fake_veredicts = [
        Veredito(
            criterio="resumo_fiel",
            evidencia="ok",
            nota=entry.human_notes["resumo_fiel"],
            confianca=90,
        )
        for entry in entries
    ]

    with patch("src.eval.calibration.judge", side_effect=fake_veredicts):
        result = calibrate_criterion("resumo_fiel", entries)

    assert isinstance(result, CriterionCalibration)
    assert result.kappa == pytest.approx(1.0)
    assert result.disagreements == []
    assert result.is_reliable is True


def test_calibrate_criterion_reports_disagreements():
    entries = [_entry("e1", 3), _entry("e2", 1)]
    fake_veredicts = [
        Veredito(criterio="resumo_fiel", evidencia="ok", nota=3, confianca=90),
        Veredito(criterio="resumo_fiel", evidencia="discordo", nota=3, confianca=60),
    ]

    with patch("src.eval.calibration.judge", side_effect=fake_veredicts):
        result = calibrate_criterion("resumo_fiel", entries)

    assert result.disagreements == [("e2", 1, 3)]


def test_criterion_calibration_is_reliable_at_the_threshold():
    calibration = CriterionCalibration(
        criterion="resumo_fiel",
        kappa=KAPPA_BLOCK_THRESHOLD,
        human_notes=[],
        judge_notes=[],
        disagreements=[],
    )
    assert calibration.is_reliable is True


def test_criterion_calibration_is_not_reliable_below_the_threshold():
    calibration = CriterionCalibration(
        criterion="resumo_fiel",
        kappa=KAPPA_BLOCK_THRESHOLD - 0.01,
        human_notes=[],
        judge_notes=[],
        disagreements=[],
    )
    assert calibration.is_reliable is False
