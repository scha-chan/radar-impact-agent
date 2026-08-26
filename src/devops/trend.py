"""Estimativa de tendência — regressão linear simples (mantida, exigida
pelo edital) sobre a taxa de escalação humana por janela (card 27, seção
16 do PRD). Projeta a janela seguinte; ultrapassar 50% emite alerta de
degradação.

A regressão da probabilidade de falha por classificador calibrado
(`HistGradientBoostingClassifier`) é o card 41 — extensão pós-rubrica,
fora de escopo aqui.
"""

from __future__ import annotations

from dataclasses import dataclass

DEGRADATION_ALERT_THRESHOLD = 0.50


@dataclass(frozen=True)
class TrendEstimate:
    slope: float
    intercept: float
    next_window_index: int
    projection: float
    alert: bool


def linear_regression(xs: list[float], ys: list[float]) -> tuple[float, float]:
    """Mínimos quadrados simples: retorna `(slope, intercept)` da reta que
    melhor ajusta `ys` em função de `xs`."""
    if len(xs) != len(ys):
        raise ValueError("xs e ys precisam ter o mesmo tamanho")
    if len(xs) < 2:
        raise ValueError("regressão linear exige pelo menos 2 pontos")

    n = len(xs)
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n

    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    denominator = sum((x - mean_x) ** 2 for x in xs)
    if denominator == 0:
        raise ValueError("todos os valores de xs são iguais — reta indefinida")

    slope = numerator / denominator
    intercept = mean_y - slope * mean_x
    return slope, intercept


def project_next_window(escalation_rates_by_window: list[float]) -> TrendEstimate:
    """Ajusta a reta sobre as taxas de escalação por janela (`window_index`
    1-based, `escalation_rate`) e projeta a janela seguinte. RF exigido
    pelo edital: se a projeção ultrapassar 50%, `alert=True` (degradação)."""
    xs = [float(i) for i in range(1, len(escalation_rates_by_window) + 1)]
    slope, intercept = linear_regression(xs, escalation_rates_by_window)

    next_index = len(escalation_rates_by_window) + 1
    projection = slope * next_index + intercept

    return TrendEstimate(
        slope=slope,
        intercept=intercept,
        next_window_index=next_index,
        projection=projection,
        alert=projection > DEGRADATION_ALERT_THRESHOLD,
    )
