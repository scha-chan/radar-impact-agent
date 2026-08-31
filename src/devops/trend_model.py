"""Classificador calibrado de probabilidade de escalação (card 41, seção
16 do PRD): complementa a regressão linear simples (`trend.py`, card 28,
mantida) com uma estimativa probabilística **por execução**, treinada
sobre as mesmas features do Isolation Forest (`anomaly.py`, card 40).

Calibrado, não só discriminativo (RNF-11): um modelo pode separar bem as
classes (ROC-AUC alto) e ainda assim errar grosseiramente a
*probabilidade* que atribui a cada previsão — o Brier score mede
justamente isso, e é o que importa para decidir um threshold de ação
(`effective_confidence_threshold`, abaixo), não a discriminação sozinha.
"""

from __future__ import annotations

from dataclasses import dataclass

from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.model_selection import train_test_split

from src.devops.dataset import ExecutionRow, to_feature_matrix

DEFAULT_RANDOM_STATE = 42
# `HistGradientBoostingClassifier` usa `min_samples_leaf=20` por padrão —
# adequado para datasets grandes, mas maior que o total de amostras que
# sobra em cada dobra interna do `CalibratedClassifierCV` sobre um
# dataset de 50 execuções (~27-35 por dobra de treino). Com o padrão, a
# árvore não consegue fazer nenhuma divisão útil e colapsa para um
# previsor quase constante — descoberto medindo ROC-AUC=0,47 (pior que
# aleatório) e as probabilidades calibradas convergindo para dois valores
# só (~0,476/~0,5). Reduzir para 5 restaura discriminação real (ver
# evidência real documentada em docs/evidencias/card-41-*.md).
MIN_SAMPLES_LEAF = 5
# Seção 16 do PRD: acima desse limiar, a exigência de confiança sobe
# temporariamente (action gating, abaixo).
ESCALATION_PROBABILITY_GATE_THRESHOLD = 0.70
DEFAULT_CONSERVATIVE_BUMP = 10


def _labels(rows: list[ExecutionRow]) -> list[int]:
    return [int(row.human_review_required) for row in rows]


def train_escalation_classifier(
    rows: list[ExecutionRow], *, random_state: int = DEFAULT_RANDOM_STATE
) -> CalibratedClassifierCV:
    """`HistGradientBoostingClassifier` calibrado via
    `CalibratedClassifierCV` (método `sigmoid` — Platt scaling; o método
    `isotonic` exigiria mais dados para não sobreajustar, dado o volume
    pequeno de 50 amostras, seção 16 do PRD)."""
    base_model = HistGradientBoostingClassifier(
        random_state=random_state, min_samples_leaf=MIN_SAMPLES_LEAF
    )
    calibrated = CalibratedClassifierCV(base_model, method="sigmoid", cv=5)
    calibrated.fit(to_feature_matrix(rows), _labels(rows))
    return calibrated


def predict_escalation_probability(model: CalibratedClassifierCV, row: ExecutionRow) -> float:
    """Probabilidade calibrada de `human_review_required=True` para uma
    execução — tipicamente a próxima, ainda sem esse rótulo observado."""
    [[_, probability_positive]] = model.predict_proba(to_feature_matrix([row]))
    return float(probability_positive)


@dataclass(frozen=True)
class CalibrationReport:
    """RNF-11: `roc_auc`/`average_precision` medem discriminação;
    `brier_score` mede calibração — as duas coisas, não uma no lugar da
    outra."""

    roc_auc: float
    average_precision: float
    brier_score: float


def evaluate_calibration(
    rows: list[ExecutionRow], *, test_size: float = 0.3, random_state: int = DEFAULT_RANDOM_STATE
) -> CalibrationReport:
    X = to_feature_matrix(rows)
    y = _labels(rows)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=y
    )

    base_model = HistGradientBoostingClassifier(
        random_state=random_state, min_samples_leaf=MIN_SAMPLES_LEAF
    )
    calibrated = CalibratedClassifierCV(base_model, method="sigmoid", cv=3)
    calibrated.fit(X_train, y_train)

    probabilities = calibrated.predict_proba(X_test)[:, 1]

    return CalibrationReport(
        roc_auc=roc_auc_score(y_test, probabilities),
        average_precision=average_precision_score(y_test, probabilities),
        brier_score=brier_score_loss(y_test, probabilities),
    )


def effective_confidence_threshold(
    base_threshold: int,
    *,
    predicted_escalation_probability: float,
    conservative_bump: int = DEFAULT_CONSERVATIVE_BUMP,
) -> int:
    """Action gating (seção 16 do PRD): se a probabilidade prevista de
    escalação da próxima execução ultrapassar 70%, `CONFIDENCE_THRESHOLD`
    efetivo sobe temporariamente (mais conservador) até a taxa observada
    normalizar — paralelo simplificado ao padrão VALIDATE: o sistema não
    bloqueia execuções (isso seria RESTRICT/PAUSE), só eleva a exigência
    de confiança."""
    if predicted_escalation_probability > ESCALATION_PROBABILITY_GATE_THRESHOLD:
        return base_threshold + conservative_bump
    return base_threshold
