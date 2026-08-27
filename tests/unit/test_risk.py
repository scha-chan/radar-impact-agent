from dataclasses import FrozenInstanceError

import pytest

from src.domain.risk import (
    ConfidenceInputs,
    Probability,
    RiskItem,
    RiskLevel,
    Severity,
    aggregate_risk_level,
    calculate_confidence,
    classify_risk,
)


# --- valores dos IntEnum (card 37, RNF-10 — mutation testing expôs que os
# testes acima cobrem comportamento por nome, nunca o valor inteiro
# subjacente; nada detectava um valor trocado por engano) -----------------


def test_severity_values_are_ordered_1_to_4():
    assert (Severity.LOW, Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL) == (1, 2, 3, 4)


def test_probability_values_are_ordered_1_to_4():
    assert (
        Probability.RARE,
        Probability.POSSIBLE,
        Probability.LIKELY,
        Probability.ALMOST_CERTAIN,
    ) == (1, 2, 3, 4)


def test_risk_level_values_are_ordered_1_to_4():
    assert (RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL) == (1, 2, 3, 4)


def test_risk_item_is_immutable():
    item = RiskItem("x", Severity.LOW, Probability.RARE)
    with pytest.raises(FrozenInstanceError):
        item.description = "y"


# --- classify_risk: matriz completa (PRD secao 11) ---------------------

MATRIX_CASES = [
    (Severity.CRITICAL, Probability.RARE, RiskLevel.HIGH),
    (Severity.CRITICAL, Probability.POSSIBLE, RiskLevel.HIGH),
    (Severity.CRITICAL, Probability.LIKELY, RiskLevel.CRITICAL),
    (Severity.CRITICAL, Probability.ALMOST_CERTAIN, RiskLevel.CRITICAL),
    (Severity.HIGH, Probability.RARE, RiskLevel.MEDIUM),
    (Severity.HIGH, Probability.POSSIBLE, RiskLevel.HIGH),
    (Severity.HIGH, Probability.LIKELY, RiskLevel.HIGH),
    (Severity.HIGH, Probability.ALMOST_CERTAIN, RiskLevel.CRITICAL),
    (Severity.MEDIUM, Probability.RARE, RiskLevel.LOW),
    (Severity.MEDIUM, Probability.POSSIBLE, RiskLevel.MEDIUM),
    (Severity.MEDIUM, Probability.LIKELY, RiskLevel.MEDIUM),
    (Severity.MEDIUM, Probability.ALMOST_CERTAIN, RiskLevel.HIGH),
    (Severity.LOW, Probability.RARE, RiskLevel.LOW),
    (Severity.LOW, Probability.POSSIBLE, RiskLevel.LOW),
    (Severity.LOW, Probability.LIKELY, RiskLevel.LOW),
    (Severity.LOW, Probability.ALMOST_CERTAIN, RiskLevel.MEDIUM),
]


@pytest.mark.parametrize("severity,probability,expected", MATRIX_CASES)
def test_classify_risk_matrix(severity, probability, expected):
    assert classify_risk(severity, probability) == expected


def test_classify_risk_is_deterministic():
    # RF-05.3: mesma entrada -> mesma saida, sempre.
    results = {classify_risk(Severity.HIGH, Probability.LIKELY) for _ in range(50)}
    assert results == {RiskLevel.HIGH}


# --- aggregate_risk_level -----------------------------------------------


def test_aggregate_risk_level_picks_the_highest():
    risks = [
        RiskItem("baixo", Severity.LOW, Probability.RARE),
        RiskItem("critico", Severity.CRITICAL, Probability.LIKELY),
        RiskItem("medio", Severity.MEDIUM, Probability.POSSIBLE),
    ]
    assert aggregate_risk_level(risks) == RiskLevel.CRITICAL


def test_aggregate_risk_level_empty_is_low():
    assert aggregate_risk_level([]) == RiskLevel.LOW


# --- calculate_confidence -------------------------------------------------


def _full_confidence_inputs(**overrides) -> ConfidenceInputs:
    base = dict(
        requirement_word_count=20,
        code_matches_found=True,
        feature_type="login",
        rag_patterns_found=True,
        tools_failed_with_fallback=0,
        distinct_evidence_sources=3,
        risks=[],
    )
    base.update(overrides)
    return ConfidenceInputs(**base)


def test_confidence_inputs_defaults_when_omitted():
    # card 37 (RNF-10): os testes acima sempre passam todo campo opcional
    # explicitamente via _full_confidence_inputs — nada exercitava os
    # defaults reais da dataclass (tools_failed_with_fallback=0,
    # distinct_evidence_sources=0, risks=[]).
    inputs = ConfidenceInputs(
        requirement_word_count=20,
        code_matches_found=True,
        feature_type="login",
        rag_patterns_found=True,
    )
    assert inputs.tools_failed_with_fallback == 0
    assert inputs.distinct_evidence_sources == 0
    assert inputs.risks == []
    # 0 fontes distintas < MIN_DISTINCT_EVIDENCE_SOURCES (2) -> deduz 10.
    assert calculate_confidence(inputs) == 90


def test_confidence_is_100_with_no_deductions():
    assert calculate_confidence(_full_confidence_inputs()) == 100


def test_confidence_deducts_20_for_short_requirement():
    inputs = _full_confidence_inputs(requirement_word_count=5)
    assert calculate_confidence(inputs) == 80


def test_confidence_deducts_25_when_no_code_match():
    inputs = _full_confidence_inputs(code_matches_found=False)
    assert calculate_confidence(inputs) == 75


def test_confidence_deducts_15_for_feature_type_outro():
    inputs = _full_confidence_inputs(feature_type="outro")
    assert calculate_confidence(inputs) == 85


def test_confidence_deducts_20_when_no_rag_pattern():
    inputs = _full_confidence_inputs(rag_patterns_found=False)
    assert calculate_confidence(inputs) == 80


def test_confidence_deducts_15_per_failed_tool():
    inputs = _full_confidence_inputs(tools_failed_with_fallback=2)
    assert calculate_confidence(inputs) == 70


def test_confidence_deducts_10_for_fewer_than_two_sources():
    inputs = _full_confidence_inputs(distinct_evidence_sources=1)
    assert calculate_confidence(inputs) == 90


def test_confidence_no_deduction_at_exact_evidence_source_threshold():
    # card 37 (RNF-10): limite exato (2 fontes) não deduz — só abaixo dele.
    # Também trava o operador de comparação (`<`, não `<=`).
    inputs = _full_confidence_inputs(distinct_evidence_sources=2)
    assert calculate_confidence(inputs) == 100


def test_confidence_no_deduction_at_exact_word_threshold():
    # card 37 (RNF-10): limite exato (15 palavras) não deduz — só abaixo
    # dele. Também trava o operador de comparação (`<`, não `<=`).
    inputs = _full_confidence_inputs(requirement_word_count=15)
    assert calculate_confidence(inputs) == 100


def test_confidence_deducts_5_per_risk_without_mitigation():
    risks = [
        RiskItem("r1", Severity.LOW, Probability.RARE, mitigation=None),
        RiskItem("r2", Severity.LOW, Probability.RARE, mitigation="ok"),
    ]
    inputs = _full_confidence_inputs(risks=risks)
    assert calculate_confidence(inputs) == 95


def test_confidence_caps_mitigation_deduction_at_15():
    risks = [RiskItem(f"r{i}", Severity.LOW, Probability.RARE, mitigation=None) for i in range(4)]
    inputs = _full_confidence_inputs(risks=risks)
    # 4 riscos sem mitigacao -> 4*5=20, mas o teto e -15.
    assert calculate_confidence(inputs) == 85


def test_confidence_treats_empty_string_mitigation_as_missing():
    # Code review do PR #2 (card 24): mitigation="" e mitigation=None
    # tem que ser equivalentes (ambos falsy) - trava isso com um teste
    # explicito para uma futura mudanca de `if not r.mitigation` para
    # `if r.mitigation is None` quebrar aqui, nao silenciosamente.
    risks = [RiskItem("r1", Severity.LOW, Probability.RARE, mitigation="")]
    inputs = _full_confidence_inputs(risks=risks)
    assert calculate_confidence(inputs) == 95


def test_confidence_floor_is_zero():
    inputs = _full_confidence_inputs(
        requirement_word_count=2,
        code_matches_found=False,
        feature_type="outro",
        rag_patterns_found=False,
        tools_failed_with_fallback=5,
        distinct_evidence_sources=0,
    )
    assert calculate_confidence(inputs) == 0


def test_confidence_is_deterministic():
    inputs = _full_confidence_inputs(requirement_word_count=5)
    results = {calculate_confidence(inputs) for _ in range(50)}
    assert results == {80}
