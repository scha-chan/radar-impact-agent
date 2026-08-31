"""Regressão de eval (RF-11.5, card 39): dispara quando `prompt_version`,
`policy_version` ou `LLM_MODEL` mudam, comparando o resultado por camada
contra a execução anterior salva.

A chamada real ao juiz (`rubric.judge`) continua exigindo Ollama rodando
— indisponível no runner de CI (mesma limitação de todo teste marcado
`RUN_OLLAMA_TESTS=1`, ex.: `tests/integration/test_extract_requirement_
ollama.py`, card 6). Este módulo cobre só o MECANISMO de detecção de
mudança de versão e o diff contra o baseline — testável sem LLM nenhum;
rodar a avaliação de verdade (`calibrate_criterion`) continua um passo
manual local, documentado em `docs/qa/eval-llm-judge.md`.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from src.graph.llm import LLM_MODEL
from src.graph.state import POLICY_VERSION, PROMPT_VERSION


@dataclass(frozen=True)
class EvalVersionFingerprint:
    prompt_version: str
    policy_version: str
    llm_model: str

    @staticmethod
    def current() -> EvalVersionFingerprint:
        return EvalVersionFingerprint(
            prompt_version=PROMPT_VERSION,
            policy_version=POLICY_VERSION,
            llm_model=LLM_MODEL,
        )


def load_baseline(path: str | Path) -> dict[str, Any] | None:
    target = Path(path)
    if not target.exists():
        return None
    return json.loads(target.read_text(encoding="utf-8"))


def save_baseline(
    path: str | Path, fingerprint: EvalVersionFingerprint, result_by_layer: dict[str, Any]
) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(
            {"fingerprint": asdict(fingerprint), "result_by_layer": result_by_layer},
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def needs_rerun(baseline: dict[str, Any] | None, fingerprint: EvalVersionFingerprint) -> bool:
    """RF-11.5: sem baseline salvo ainda, sempre roda (primeira execução).
    Com baseline, só dispara se algum dos três campos do fingerprint
    mudou desde a última vez."""
    if baseline is None:
        return True
    return baseline.get("fingerprint") != asdict(fingerprint)


def diff_against_baseline(
    baseline: dict[str, Any] | None, result_by_layer: dict[str, Any]
) -> dict[str, Any]:
    """Compara o resultado atual, camada por camada, contra o baseline
    salvo — devolve só as camadas cujo valor mudou (dict vazio = nenhuma
    regressão)."""
    if baseline is None:
        return {"new_baseline": True}
    previous = baseline.get("result_by_layer", {})
    return {
        layer: {"previous": previous.get(layer), "current": value}
        for layer, value in result_by_layer.items()
        if previous.get(layer) != value
    }
