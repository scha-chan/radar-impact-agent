"""Detecção multivariada de anomalia (card 40, seção 16 do PRD): o
baseline univariado (`baseline.py`, card 27) não captura combinações
incomuns de sinais — ex. confiança alta com muitos retries, indício de
uma tool mascarando falha. As features são normalizadas (`StandardScaler`)
e alimentam um **Isolation Forest** (`contamination` configurável)
treinado sobre o dataset de execuções (`dataset.py`, card 27).

`human_review_required` fica de fora das features de propósito — é quase
determinístico a partir de `confidence` (RF-06.1/06.2), então incluí-lo
faria o modelo "redizer" o que o baseline já cobre; o valor de uma
detecção multivariada está em achar combinações incomuns entre as
demais features, não a mesma coisa por outro caminho.
"""

from __future__ import annotations

from dataclasses import dataclass

from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from src.devops.dataset import ExecutionRow

DEFAULT_CONTAMINATION = 0.1
DEFAULT_RANDOM_STATE = 42

FEATURE_NAMES = [
    "duration_ms",
    "retries_used",
    "confidence",
    "tool_errors",
    "evidence_sources_count",
]


def _to_feature_matrix(rows: list[ExecutionRow]) -> list[list[float]]:
    return [
        [
            float(row.duration_ms),
            float(row.retries_used),
            float(row.confidence),
            float(row.tool_errors),
            float(row.evidence_sources_count),
        ]
        for row in rows
    ]


@dataclass(frozen=True)
class AnomalyResult:
    session_id: str
    score: float  # score_samples do Isolation Forest — quanto menor, mais anômalo
    is_outlier: bool


def detect_anomalies(
    rows: list[ExecutionRow],
    *,
    contamination: float = DEFAULT_CONTAMINATION,
    random_state: int = DEFAULT_RANDOM_STATE,
) -> list[AnomalyResult]:
    if not rows:
        return []

    scaled = StandardScaler().fit_transform(_to_feature_matrix(rows))
    model = IsolationForest(contamination=contamination, random_state=random_state)
    predictions = model.fit_predict(scaled)  # -1 = outlier, 1 = inlier
    scores = model.score_samples(scaled)

    return [
        AnomalyResult(session_id=row.session_id, score=float(score), is_outlier=prediction == -1)
        for row, score, prediction in zip(rows, scores, predictions)
    ]


def list_outliers(results: list[AnomalyResult]) -> list[AnomalyResult]:
    """Só os outliers, do mais anômalo (score mais baixo) para o menos."""
    return sorted((r for r in results if r.is_outlier), key=lambda r: r.score)
