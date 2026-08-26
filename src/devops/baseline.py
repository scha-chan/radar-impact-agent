"""Baseline univariado de detecção de anomalia (RF exigido pelo edital
como "estimativa simples", card 27, seção 16 do PRD): taxa de escalação
humana por janela de execuções.

Faixa esperada: 20%-40%, calibrada para o `CONFIDENCE_THRESHOLD` padrão
(70, RF-06.4). Fora dessa faixa indica calibração ruim do threshold **ou**
degradação da qualidade da evidência disponível (RAG deixou de cobrir os
tipos de requisito que chegam, ou a busca de código parou de encontrar
correspondências) — em ambos os casos a confiança cai por falta de
evidência, não por complexidade real do requisito.
"""

from __future__ import annotations

from dataclasses import dataclass

EXPECTED_MIN_RATE = 0.20
EXPECTED_MAX_RATE = 0.40
DEFAULT_WINDOW_SIZE = 10


@dataclass(frozen=True)
class WindowResult:
    start_index: int
    end_index: int
    escalation_rate: float
    is_anomalous: bool


def escalation_rate_by_window(
    human_review_flags: list[bool], window_size: int = DEFAULT_WINDOW_SIZE
) -> list[WindowResult]:
    """Uma janela por `window_size` execuções consecutivas (a última janela
    pode ficar menor se o total não for múltiplo). `is_anomalous` marca
    janelas fora da faixa 20%-40%."""
    results = []
    for start in range(0, len(human_review_flags), window_size):
        window = human_review_flags[start : start + window_size]
        if not window:
            continue
        rate = sum(window) / len(window)
        results.append(
            WindowResult(
                start_index=start,
                end_index=start + len(window) - 1,
                escalation_rate=rate,
                is_anomalous=rate > EXPECTED_MAX_RATE or rate < EXPECTED_MIN_RATE,
            )
        )
    return results
