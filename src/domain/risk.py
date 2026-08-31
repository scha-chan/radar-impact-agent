"""Matriz de risco e formula de confianca do RADAR.

Logica pura e deterministica (RF-05): dada a mesma entrada, produz sempre a
mesma saida. O LLM nao participa desta etapa (RF-05.4) — ele so alimenta os
dados de entrada (severidade, probabilidade, evidencias coletadas). Ver PRD
secao 11.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum


class Severity(IntEnum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class Probability(IntEnum):
    RARE = 1
    POSSIBLE = 2
    LIKELY = 3
    ALMOST_CERTAIN = 4


class RiskLevel(IntEnum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


# Matriz severidade x probabilidade (PRD secao 11).
_RISK_MATRIX: dict[tuple[Severity, Probability], RiskLevel] = {
    (Severity.CRITICAL, Probability.RARE): RiskLevel.HIGH,
    (Severity.CRITICAL, Probability.POSSIBLE): RiskLevel.HIGH,
    (Severity.CRITICAL, Probability.LIKELY): RiskLevel.CRITICAL,
    (Severity.CRITICAL, Probability.ALMOST_CERTAIN): RiskLevel.CRITICAL,
    (Severity.HIGH, Probability.RARE): RiskLevel.MEDIUM,
    (Severity.HIGH, Probability.POSSIBLE): RiskLevel.HIGH,
    (Severity.HIGH, Probability.LIKELY): RiskLevel.HIGH,
    (Severity.HIGH, Probability.ALMOST_CERTAIN): RiskLevel.CRITICAL,
    (Severity.MEDIUM, Probability.RARE): RiskLevel.LOW,
    (Severity.MEDIUM, Probability.POSSIBLE): RiskLevel.MEDIUM,
    (Severity.MEDIUM, Probability.LIKELY): RiskLevel.MEDIUM,
    (Severity.MEDIUM, Probability.ALMOST_CERTAIN): RiskLevel.HIGH,
    (Severity.LOW, Probability.RARE): RiskLevel.LOW,
    (Severity.LOW, Probability.POSSIBLE): RiskLevel.LOW,
    (Severity.LOW, Probability.LIKELY): RiskLevel.LOW,
    (Severity.LOW, Probability.ALMOST_CERTAIN): RiskLevel.MEDIUM,
}


@dataclass(frozen=True)
class RiskItem:
    """Um risco identificado na analise de impacto (PRD secao 8, `Risk`)."""

    description: str
    severity: Severity
    probability: Probability
    mitigation: str | None = None


def classify_risk(severity: Severity, probability: Probability) -> RiskLevel:
    """Aplica a matriz severidade x probabilidade a um unico risco."""
    return _RISK_MATRIX[(severity, probability)]


def aggregate_risk_level(risks: list[RiskItem]) -> RiskLevel:
    """`risk_level` da analise: o maior nivel entre todos os riscos.

    Sem riscos identificados, o nivel agregado e LOW.
    """
    if not risks:
        return RiskLevel.LOW
    return max(classify_risk(r.severity, r.probability) for r in risks)


@dataclass(frozen=True)
class ConfidenceInputs:
    """Sinais usados na formula de confianca (PRD secao 11)."""

    requirement_word_count: int
    code_matches_found: bool
    feature_type: str
    rag_patterns_found: bool
    tools_failed_with_fallback: int = 0
    distinct_evidence_sources: int = 0
    risks: list[RiskItem] = field(default_factory=list)


# Deducoes da formula de confianca (PRD secao 11) — nomeadas para que cada
# uma mapeie de volta a uma linha especifica da tabela do PRD, em vez de um
# numero solto dentro de calculate_confidence (card 24, code review do PR #2).
SHORT_REQUIREMENT_WORD_THRESHOLD = 15
SHORT_REQUIREMENT_PENALTY = 20
NO_CODE_MATCH_PENALTY = 25
FEATURE_TYPE_OUTRO_PENALTY = 15
NO_RAG_PATTERN_PENALTY = 20
TOOL_FAILED_WITH_FALLBACK_PENALTY = 15
MIN_DISTINCT_EVIDENCE_SOURCES = 2
FEW_EVIDENCE_SOURCES_PENALTY = 10
RISK_WITHOUT_MITIGATION_PENALTY = 5
RISK_WITHOUT_MITIGATION_PENALTY_CAP = 15


def calculate_confidence(inputs: ConfidenceInputs) -> int:
    """Confianca (0-100): mede a qualidade da evidencia disponivel, nao a
    certeza do modelo. Comeca em 100 e sofre deducoes cumulativas; piso 0,
    teto 100.
    """
    score = 100

    if inputs.requirement_word_count < SHORT_REQUIREMENT_WORD_THRESHOLD:
        score -= SHORT_REQUIREMENT_PENALTY
    if not inputs.code_matches_found:
        score -= NO_CODE_MATCH_PENALTY
    if inputs.feature_type == "outro":
        score -= FEATURE_TYPE_OUTRO_PENALTY
    if not inputs.rag_patterns_found:
        score -= NO_RAG_PATTERN_PENALTY

    score -= TOOL_FAILED_WITH_FALLBACK_PENALTY * inputs.tools_failed_with_fallback

    if inputs.distinct_evidence_sources < MIN_DISTINCT_EVIDENCE_SOURCES:
        score -= FEW_EVIDENCE_SOURCES_PENALTY

    risks_without_mitigation = sum(1 for r in inputs.risks if not r.mitigation)
    score -= min(
        RISK_WITHOUT_MITIGATION_PENALTY * risks_without_mitigation,
        RISK_WITHOUT_MITIGATION_PENALTY_CAP,
    )

    return max(0, min(100, score))
