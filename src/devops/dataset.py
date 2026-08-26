"""Dataset simulado de execuções do RADAR (card 27, seção 16 do PRD).

50 execuções simuladas em duas fases: as primeiras 35 com evidência
"normal" (busca de código e RAG encontrando resultados na maior parte das
vezes), as últimas 15 com evidência degradada — simula o cenário de
anomalia que o baseline (RF exigido pelo edital como "estimativa
simples") deve detectar: a base RAG parou de cobrir os tipos de requisito
que chegam, ou a busca de código parou de encontrar correspondências, e a
taxa de escalação humana sobe consistentemente acima de 40%.

Metodologia: `confidence` de cada execução é calculado pela fórmula REAL
de produção (`calculate_confidence`, `src/domain/risk.py`, card 02) a
partir de sinais de evidência simulados — não é um número sorteado
diretamente. Isso faz o dataset refletir o comportamento real do sistema
diante de evidência boa/ruim, em vez de uma distribuição arbitrária sem
relação com a lógica do produto. `human_review_required` é derivado da
mesma regra de RF-06.1/06.2 (`confidence < CONFIDENCE_THRESHOLD`).
`duration_ms` simula a latência dominada por chamadas de LLM (achado real
do card 21: ~88% do tempo de uma execução são as duas chamadas de LLM,
`extract_requirement` + `guard_adversarial`), com custo extra por retry.
"""

from __future__ import annotations

import csv
import random
from dataclasses import dataclass
from pathlib import Path

from src.domain.risk import ConfidenceInputs, calculate_confidence

CONFIDENCE_THRESHOLD = 70
NORMAL_PHASE_EXECUTIONS = 35
TOTAL_EXECUTIONS = 50
DEFAULT_SEED = 42

FEATURE_TYPES = [
    "login",
    "cadastro",
    "formulario",
    "api",
    "upload",
    "dashboard",
    "listagem",
    "notificacao",
    "integracao",
    "outro",
]

DATASET_PATH = (
    Path(__file__).resolve().parent.parent.parent / "docs" / "devops" / "dataset-execucoes.csv"
)

CSV_COLUMNS = [
    "session_id",
    "duration_ms",
    "retries_used",
    "confidence",
    "tool_errors",
    "evidence_sources_count",
    "human_review_required",
]


@dataclass(frozen=True)
class ExecutionRow:
    session_id: str
    duration_ms: int
    retries_used: int
    confidence: int
    tool_errors: int
    evidence_sources_count: int
    human_review_required: bool


def _simulate_execution(index: int, rng: random.Random, *, degraded: bool) -> ExecutionRow:
    # Fase degradada: mais requisitos caem em "outro" (o classificador não
    # reconhece o tipo) e a evidência de código/RAG falha com mais frequência.
    feature_type = (
        rng.choices(FEATURE_TYPES[:-1] + ["outro"], weights=[1] * 9 + [3])[0]
        if degraded
        else rng.choice(FEATURE_TYPES)
    )
    code_matches_found = rng.random() > (0.7 if degraded else 0.15)
    rag_patterns_found = rng.random() > (0.75 if degraded else 0.1)
    tools_failed = rng.choices([0, 1, 2], weights=[50, 35, 15] if degraded else [85, 12, 3])[0]
    evidence_sources = sum([code_matches_found, rag_patterns_found, rng.random() > 0.3])
    word_count = rng.randint(6, 30)

    inputs = ConfidenceInputs(
        requirement_word_count=word_count,
        code_matches_found=code_matches_found,
        feature_type=feature_type,
        rag_patterns_found=rag_patterns_found,
        tools_failed_with_fallback=tools_failed,
        distinct_evidence_sources=evidence_sources,
        risks=[],
    )
    confidence = calculate_confidence(inputs)

    retries_used = rng.choices([0, 1, 2], weights=[70, 25, 5])[0]
    base_ms = rng.randint(8_000, 18_000)
    duration_ms = base_ms + retries_used * rng.randint(3_000, 6_000)

    return ExecutionRow(
        session_id=f"sim-{index:03d}",
        duration_ms=duration_ms,
        retries_used=retries_used,
        confidence=confidence,
        tool_errors=tools_failed,
        evidence_sources_count=evidence_sources,
        human_review_required=confidence < CONFIDENCE_THRESHOLD,
    )


def generate_dataset(seed: int = DEFAULT_SEED) -> list[ExecutionRow]:
    rng = random.Random(seed)
    return [
        _simulate_execution(i, rng, degraded=i > NORMAL_PHASE_EXECUTIONS)
        for i in range(1, TOTAL_EXECUTIONS + 1)
    ]


def write_csv(rows: list[ExecutionRow], path: Path = DATASET_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_COLUMNS)
        for row in rows:
            writer.writerow(
                [
                    row.session_id,
                    row.duration_ms,
                    row.retries_used,
                    row.confidence,
                    row.tool_errors,
                    row.evidence_sources_count,
                    row.human_review_required,
                ]
            )


def read_csv(path: Path = DATASET_PATH) -> list[ExecutionRow]:
    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [
            ExecutionRow(
                session_id=r["session_id"],
                duration_ms=int(r["duration_ms"]),
                retries_used=int(r["retries_used"]),
                confidence=int(r["confidence"]),
                tool_errors=int(r["tool_errors"]),
                evidence_sources_count=int(r["evidence_sources_count"]),
                human_review_required=r["human_review_required"] == "True",
            )
            for r in reader
        ]


if __name__ == "__main__":
    write_csv(generate_dataset())
