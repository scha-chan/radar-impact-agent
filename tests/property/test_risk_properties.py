"""Testes baseados em propriedade (Hypothesis, card 38) — invariantes de
`src/domain/risk.py` que exemplos isolados não capturam (seção 15 do
PRD): a fórmula de confiança nunca sai de `[0, 100]` para qualquer
combinação de entradas, `aggregate_risk_level` nunca fica abaixo do maior
risco individual da lista, e `classify_risk` é monotônico — aumentar
severidade ou probabilidade nunca reduz o `risk_level`.

`deadline=None`: os testes chamam apenas funções puras de `src.domain.risk`
(sem I/O), mas o runner de CI pode variar de velocidade o suficiente para
o prazo padrão do Hypothesis (200ms) gerar falsos "flaky" — o que importa
aqui é a propriedade se manter para todo exemplo gerado, não o tempo.
"""

from __future__ import annotations

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from src.domain.risk import (
    ConfidenceInputs,
    Probability,
    RiskItem,
    Severity,
    aggregate_risk_level,
    calculate_confidence,
    classify_risk,
)

severities = st.sampled_from(Severity)
probabilities = st.sampled_from(Probability)

risk_items = st.builds(
    RiskItem,
    description=st.text(max_size=50),
    severity=severities,
    probability=probabilities,
    mitigation=st.one_of(st.none(), st.text(max_size=50)),
)

confidence_inputs = st.builds(
    ConfidenceInputs,
    requirement_word_count=st.integers(min_value=0, max_value=1000),
    code_matches_found=st.booleans(),
    feature_type=st.text(max_size=20),
    rag_patterns_found=st.booleans(),
    tools_failed_with_fallback=st.integers(min_value=0, max_value=20),
    distinct_evidence_sources=st.integers(min_value=0, max_value=20),
    risks=st.lists(risk_items, max_size=10),
)


@settings(deadline=None)
@given(confidence_inputs)
def test_calculate_confidence_never_leaves_0_to_100(inputs):
    assert 0 <= calculate_confidence(inputs) <= 100


@settings(deadline=None)
@given(st.lists(risk_items, min_size=1, max_size=10))
def test_aggregate_risk_level_is_never_below_the_highest_individual_risk(risks):
    individual_levels = [classify_risk(r.severity, r.probability) for r in risks]
    assert aggregate_risk_level(risks) >= max(individual_levels)


@settings(deadline=None)
@given(severities, severities, probabilities)
def test_classify_risk_is_monotonic_in_severity(severity_a, severity_b, probability):
    # Aumentar a severidade (mantendo a probabilidade fixa) nunca reduz
    # o risk_level resultante.
    assume(severity_a <= severity_b)
    assert classify_risk(severity_a, probability) <= classify_risk(severity_b, probability)


@settings(deadline=None)
@given(severities, probabilities, probabilities)
def test_classify_risk_is_monotonic_in_probability(severity, probability_a, probability_b):
    # Aumentar a probabilidade (mantendo a severidade fixa) nunca reduz
    # o risk_level resultante.
    assume(probability_a <= probability_b)
    assert classify_risk(severity, probability_a) <= classify_risk(severity, probability_b)
