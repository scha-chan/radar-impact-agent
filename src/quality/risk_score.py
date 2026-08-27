"""Score de risco computável por módulo (RF-12, card 36) — prioriza a
fila de testes no CI e onde aplicar mutation testing (RNF-10), sem
depender de reordenação manual.

Risco de módulo = probabilidade (computada, sem LLM) × impacto
(classificado pelo LLM, que nunca calcula o número final — mesmo
princípio de `domain/risk.py`: "se dá para computar, compute"; o LLM só
alimenta a classificação de entrada).
"""

from __future__ import annotations

import json
import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from src.quality.prompts import build_impact_classification_prompt

REPO_ROOT = Path(__file__).resolve().parents[2]
WEIGHTS_PATH = Path(__file__).parent / "weights.toml"

ImpactLevel = Literal["LOW", "MEDIUM", "HIGH"]
_LEVEL_VALUE = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}
_MAX_LEVEL_VALUE = 3


class ImpactClassification(BaseModel):
    """RF-12.2: saída do LLM — só classifica, nunca calcula o score final."""

    module: str
    criticality: ImpactLevel
    blast_radius: ImpactLevel
    reversibility: ImpactLevel
    rationale: str


@dataclass(frozen=True)
class ModuleSignals:
    module: str
    churn: int
    authors: int
    complexity: float
    coverage_percent: float


@dataclass(frozen=True)
class ModuleRisk:
    module: str
    probability: float
    impact: float
    risk: float


def load_weights(path: Path | None = None) -> dict[str, float]:
    with (path or WEIGHTS_PATH).open("rb") as f:
        data = tomllib.load(f)
    return data["probability_weights"]


def git_churn(module: str, *, since_days: int = 30, repo_root: Path | None = None) -> int:
    """RF-12.1: commits que tocaram `module` nos últimos `since_days` dias."""
    result = subprocess.run(
        ["git", "log", f"--since={since_days} days ago", "--oneline", "--", module],
        cwd=repo_root or REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return len([line for line in result.stdout.splitlines() if line.strip()])


def git_distinct_authors(module: str, *, repo_root: Path | None = None) -> int:
    """RF-12.1: número de autores distintos que já tocaram `module`."""
    result = subprocess.run(
        ["git", "log", "--format=%ae", "--", module],
        cwd=repo_root or REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    authors = {line.strip() for line in result.stdout.splitlines() if line.strip()}
    return len(authors)


def cyclomatic_complexity(module: str, *, repo_root: Path | None = None) -> float:
    """RF-12.1: complexidade ciclomática média das funções/classes do
    módulo — via biblioteca `radon.complexity` (mesma métrica de
    `radon cc -s`, sem depender do binário `radon` estar no PATH)."""
    from radon.complexity import average_complexity, cc_visit

    path = (repo_root or REPO_ROOT) / module
    blocks = cc_visit(path.read_text(encoding="utf-8"))
    return average_complexity(blocks) if blocks else 0.0


def load_coverage_percentages(coverage_json_path: str | Path) -> dict[str, float]:
    """Lê `coverage.json` (`pytest --cov --cov-report=json`) e devolve
    `{caminho_relativo_do_arquivo: percentual_coberto}`. `coverage.py`
    grava a chave com o separador do SO (`\\` no Windows) — normalizado
    aqui para `/`, o mesmo separador usado nos argumentos de `git_churn`/
    `cyclomatic_complexity`/`collect_signals`, senão o cruzamento por
    caminho nunca bate no Windows."""
    data = json.loads(Path(coverage_json_path).read_text(encoding="utf-8"))
    return {
        file.replace("\\", "/"): info["summary"]["percent_covered"]
        for file, info in data.get("files", {}).items()
    }


def collect_signals(
    modules: list[str],
    *,
    coverage_by_module: dict[str, float] | None = None,
    repo_root: Path | None = None,
) -> list[ModuleSignals]:
    coverage_by_module = coverage_by_module or {}
    return [
        ModuleSignals(
            module=module,
            churn=git_churn(module, repo_root=repo_root),
            authors=git_distinct_authors(module, repo_root=repo_root),
            complexity=cyclomatic_complexity(module, repo_root=repo_root),
            coverage_percent=coverage_by_module.get(module, 0.0),
        )
        for module in modules
    ]


def _percentile_ranks(values: list[float]) -> list[float]:
    """RF-12.1: normalização por percentil, não pelo valor bruto — evita
    que uma métrica de escala maior (ex.: complexidade média em ponto
    flutuante) domine a combinação sobre outra de escala menor (ex.: churn
    em contagem inteira pequena). Cada posição vira a fração de valores do
    conjunto estritamente menores que ela — empates recebem o mesmo
    percentil."""
    n = len(values)
    if n <= 1:
        return [0.0 for _ in values]
    return [sum(1 for v in values if v < value) / (n - 1) for value in values]


def compute_probability_scores(
    signals: list[ModuleSignals], *, weights: dict[str, float] | None = None
) -> dict[str, float]:
    """RF-12.1: combina os quatro sinais normalizados por percentil com
    pesos versionados (`weights.toml`). Cobertura entra invertida
    (`coverage_gap` = 1 - percentil de cobertura) — é a FALTA de cobertura
    que é o sinal de risco, não a cobertura em si."""
    weights = weights or load_weights()
    churn_pct = _percentile_ranks([s.churn for s in signals])
    complexity_pct = _percentile_ranks([s.complexity for s in signals])
    authors_pct = _percentile_ranks([s.authors for s in signals])
    coverage_gap_pct = [1 - p for p in _percentile_ranks([s.coverage_percent for s in signals])]

    return {
        s.module: (
            weights["churn"] * churn_pct[i]
            + weights["complexity"] * complexity_pct[i]
            + weights["authors"] * authors_pct[i]
            + weights["coverage_gap"] * coverage_gap_pct[i]
        )
        for i, s in enumerate(signals)
    }


def impact_score(classification: ImpactClassification) -> float:
    """RF-12.2: score determinístico a partir da classificação do LLM —
    média das três dimensões, normalizada para [0, 1] (o LLM classifica,
    o Python computa — mesmo princípio de `aggregate_risk_level`)."""
    values = [
        _LEVEL_VALUE[classification.criticality],
        _LEVEL_VALUE[classification.blast_radius],
        _LEVEL_VALUE[classification.reversibility],
    ]
    return sum(values) / (len(values) * _MAX_LEVEL_VALUE)


def classify_impact(module: str, *, code_excerpt: str) -> ImpactClassification:
    """RF-12.2: chama o LLM só para classificar as três dimensões — nunca
    para calcular o score final (isso é `impact_score`, puro)."""
    from src.graph.llm import build_chat_model

    structured_llm = build_chat_model().with_structured_output(ImpactClassification)
    prompt = build_impact_classification_prompt(module, code_excerpt)
    return structured_llm.invoke(prompt)


def rank_modules_by_risk(
    probability_scores: dict[str, float], impact_scores: dict[str, float]
) -> list[ModuleRisk]:
    """RF-12.3: risco de módulo = probabilidade × impacto — decide a
    ordem de execução dos testes no CI e onde aplicar mutation testing
    (RNF-10). Ordenado do maior risco para o menor."""
    risks = [
        ModuleRisk(
            module=module,
            probability=probability,
            impact=impact_scores.get(module, 0.0),
            risk=probability * impact_scores.get(module, 0.0),
        )
        for module, probability in probability_scores.items()
    ]
    return sorted(risks, key=lambda r: r.risk, reverse=True)
