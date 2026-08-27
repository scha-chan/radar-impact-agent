"""Calibração do juiz LLM contra o golden set via Kappa de Cohen
(RF-11.4, card 39). Kappa abaixo de 0,4 bloqueia o uso do juiz como gate
até a rubrica ser revisada.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.eval.golden_set import GoldenEntry, JudgeCriterion, load_golden_set
from src.eval.rubric import judge

KAPPA_BLOCK_THRESHOLD = 0.4


def cohen_kappa(labels_a: list[int], labels_b: list[int]) -> float:
    """Kappa de Cohen genérico sobre rótulos categóricos (aqui, notas
    1-3): `1.0` é concordância perfeita, `0.0` é a concordância observada
    exatamente igual à esperada por acaso, negativo é pior que o acaso.
    """
    if len(labels_a) != len(labels_b):
        raise ValueError("labels_a e labels_b precisam ter o mesmo tamanho")
    n = len(labels_a)
    if n == 0:
        raise ValueError("não é possível calcular Kappa sem rótulos")

    categories = sorted(set(labels_a) | set(labels_b))
    index = {category: i for i, category in enumerate(categories)}
    k = len(categories)

    confusion = [[0] * k for _ in range(k)]
    for a, b in zip(labels_a, labels_b):
        confusion[index[a]][index[b]] += 1

    observed_agreement = sum(confusion[i][i] for i in range(k)) / n

    row_totals = [sum(row) / n for row in confusion]
    col_totals = [sum(confusion[i][j] for i in range(k)) / n for j in range(k)]
    expected_agreement = sum(row_totals[i] * col_totals[i] for i in range(k))

    if expected_agreement == 1.0:
        # Toda entrada tem o mesmo rotulo dos dois lados (sem variação
        # nenhuma) - a formula padrao divide por zero aqui; concordancia
        # total sem variação é tratada como Kappa perfeito (1.0), não erro.
        return 1.0
    return (observed_agreement - expected_agreement) / (1 - expected_agreement)


@dataclass(frozen=True)
class CriterionCalibration:
    criterion: JudgeCriterion
    kappa: float
    human_notes: list[int]
    judge_notes: list[int]
    # (entry_id, nota_humana, nota_do_juiz) para toda discordância.
    disagreements: list[tuple[str, int, int]]

    @property
    def is_reliable(self) -> bool:
        return self.kappa >= KAPPA_BLOCK_THRESHOLD


def calibrate_criterion(
    criterion: JudgeCriterion, entries: list[GoldenEntry] | None = None
) -> CriterionCalibration:
    """RF-11.3/11.4: roda o juiz LLM (uma chamada por entrada) contra o
    golden set e compara com o rótulo manual via Kappa."""
    entries = entries if entries is not None else load_golden_set()
    human_notes = [entry.human_notes[criterion] for entry in entries]
    veredicts = [
        judge(
            criterion,
            raw_requirement=entry.raw_requirement,
            requirement_summary=entry.requirement_summary,
            recommended_tests=entry.recommended_tests,
        )
        for entry in entries
    ]
    judge_notes = [veredict.nota for veredict in veredicts]
    disagreements = [
        (entry.id, human, judged)
        for entry, human, judged in zip(entries, human_notes, judge_notes)
        if human != judged
    ]
    return CriterionCalibration(
        criterion=criterion,
        kappa=cohen_kappa(human_notes, judge_notes),
        human_notes=human_notes,
        judge_notes=judge_notes,
        disagreements=disagreements,
    )
