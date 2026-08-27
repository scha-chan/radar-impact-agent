"""Avaliação em camadas (RF-11.2, card 39): `risk_level`/`confidence` são
comparados por igualdade/tolerância exata contra o golden set, sem LLM —
só a saída aberta (`requirement_summary`/`recommended_tests`) passa pelo
juiz (`rubric.py`/`calibration.py`). Determinístico porque é possível
computar; o mesmo princípio de `domain/risk.py`.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.eval.golden_set import GoldenEntry

# Tolerância da camada determinística: a fórmula de confiança é
# determinística, mas pequenas variações na evidência coletada entre
# execuções (contagem de fontes, penalidades acumuladas) não deveriam
# reprovar o golden set por 1-2 pontos de diferença sem significado.
CONFIDENCE_TOLERANCE = 10


@dataclass(frozen=True)
class DeterministicResult:
    entry_id: str
    risk_level_match: bool
    confidence_within_tolerance: bool

    @property
    def passed(self) -> bool:
        return self.risk_level_match and self.confidence_within_tolerance


def evaluate_deterministic_layer(
    entry: GoldenEntry, *, candidate_risk_level: str, candidate_confidence: int
) -> DeterministicResult:
    return DeterministicResult(
        entry_id=entry.id,
        risk_level_match=candidate_risk_level == entry.expected_risk_level,
        confidence_within_tolerance=(
            abs(candidate_confidence - entry.expected_confidence) <= CONFIDENCE_TOLERANCE
        ),
    )
