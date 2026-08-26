"""Nodes stub do grafo RADAR.

Cada node abaixo produz uma atualizacao minima e deterministica do
`AgentState`, sem chamar LLM ou API externa — o objetivo deste card e o
grafo ser executavel ponta a ponta (sequencial, condicional, paralelo,
parada) antes das integracoes reais existirem. `score_risk` e a excecao:
ja usa `src.domain.risk`, porque essa logica e determinística e ja esta
pronta (card 02).

As integracoes reais chegam nos cards 6-18: extract_requirement (LLM,
card 6), search_codebase/fetch_history (GitHub API, cards 8-9),
retrieve_rag (ChromaDB, card 13), analyze_impact (LLM, card 14),
human_approval (interrupt + checkpointer, card 15), publish_comment
(GitHub API, card 10), guard_adversarial (detector real, card 18).
"""

from __future__ import annotations

import logging
import os
import time

from src.domain.risk import (
    ConfidenceInputs,
    Probability,
    RiskItem,
    RiskLevel,
    Severity,
    aggregate_risk_level,
    calculate_confidence,
)
from src.graph import prompts
from src.graph.llm import build_chat_model
from src.graph.state import AgentState, EvidenceSource, Requirement
from src.mcp_server.tools.search_code import search_code

logger = logging.getLogger(__name__)

CONFIDENCE_THRESHOLD = int(os.getenv("CONFIDENCE_THRESHOLD", "70"))

_SEVERITY_BY_NAME = {s.name: s for s in Severity}
_PROBABILITY_BY_NAME = {p.name: p for p in Probability}
_RISK_LEVEL_NAME = {level: level.name for level in RiskLevel}


def _to_risk_item(risk) -> RiskItem:
    return RiskItem(
        description=risk.description,
        severity=_SEVERITY_BY_NAME[risk.severity],
        probability=_PROBABILITY_BY_NAME[risk.probability],
        mitigation=risk.mitigation,
    )


def extract_requirement(state: AgentState) -> dict:
    """RF-02: LLM converte texto livre em `Requirement` validado por Pydantic.

    Retry limitado por `retries_left` (RF-02.4); se todas as tentativas
    falharem (parse inválido ou erro de chamada), cai para um `Requirement`
    de fallback (feature_type="outro", sem search_terms) — o grafo continua,
    e a confiança calculada em `score_risk` penaliza o resultado degradado.
    """
    raw_requirement = state["raw_requirement"]
    structured_llm = build_chat_model().with_structured_output(Requirement)
    prompt = prompts.build_extract_requirement_prompt(raw_requirement)

    retries_left = state["retries_left"]
    attempts = max(1, retries_left + 1)

    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            requirement = structured_llm.invoke(prompt)
            return {"requirement": requirement, "retries_left": retries_left - attempt}
        except Exception as exc:  # noqa: BLE001 - parse e erro de chamada tratados igual (RF-02.4)
            last_error = exc
            logger.warning(
                "extract_requirement_parse_failed",
                extra={"attempt": attempt, "error": str(exc)},
            )

    logger.error(
        "extract_requirement_exhausted_retries",
        extra={"attempts": attempts, "error": str(last_error)},
    )
    fallback = Requirement(text=raw_requirement, feature_type="outro", search_terms=[])
    return {"requirement": fallback, "retries_left": 0}


def guard_adversarial(state: AgentState) -> dict:
    """Stub de RF-06.3: detector real chega no card 18."""
    return {"is_adversarial": False, "adversarial_reason": None}


def block(state: AgentState) -> dict:
    return {}


# Latencia de I/O simulada nos tres nodes de evidencia — existe so para o
# fan-out via Send (card 05) ser mensuravel antes das integracoes reais
# (cards 8, 9, 13) terem latencia de rede propria para medir. Remover junto
# com o ultimo stub que a usa.
STUB_IO_LATENCY_SECONDS = 0.1


def search_codebase(state: AgentState) -> dict:
    """RF-03.1: busca real via API do GitHub (`search_code`). RF-03.4: cada
    arquivo encontrado vira uma entrada em `evidence_sources`."""
    requirement = state["requirement"]
    search_terms = requirement.search_terms if requirement else []
    if not search_terms:
        return {"code_matches": [], "evidence_sources": []}

    matches = search_code(
        search_terms,
        repo=os.getenv("GITHUB_REPO", ""),
        github_token=os.getenv("GITHUB_TOKEN", ""),
    )
    evidence = [EvidenceSource(type="code", ref=match.file) for match in matches]
    return {"code_matches": matches, "evidence_sources": evidence}


def retrieve_rag(state: AgentState) -> dict:
    """Stub de RF-03.2: ChromaDB real chega no card 13."""
    time.sleep(STUB_IO_LATENCY_SECONDS)
    return {"impact_patterns": []}


def fetch_history(state: AgentState) -> dict:
    """Stub de RF-03.3: GitHub API real chega no card 9."""
    time.sleep(STUB_IO_LATENCY_SECONDS)
    return {"change_history": []}


def analyze_impact(state: AgentState) -> dict:
    """Stub de RF-04: LLM real chega no card 14."""
    return {"impacts": [], "risks": [], "dependencies": [], "recommended_tests": []}


def score_risk(state: AgentState) -> dict:
    """RF-05: determinístico de verdade — reusa `src.domain.risk` desde já."""
    risk_items = [_to_risk_item(r) for r in state["risks"]]
    risk_level = aggregate_risk_level(risk_items)

    requirement = state["requirement"]
    word_count = len(requirement.text.split()) if requirement else 0
    feature_type = requirement.feature_type if requirement else "outro"

    inputs = ConfidenceInputs(
        requirement_word_count=word_count,
        code_matches_found=bool(state["code_matches"]),
        feature_type=feature_type,
        rag_patterns_found=bool(state["impact_patterns"]),
        tools_failed_with_fallback=0,
        distinct_evidence_sources=len(state["evidence_sources"]),
        risks=risk_items,
    )
    confidence = calculate_confidence(inputs)

    return {
        "risk_level": _RISK_LEVEL_NAME[risk_level],
        "confidence": confidence,
    }


def decide_autonomy(state: AgentState) -> dict:
    """RF-06: decisão determinística de autonomia (node `route_by_confidence`)."""
    requires_review = state["risk_level"] == "CRITICAL" or (
        state["confidence"] or 0
    ) < CONFIDENCE_THRESHOLD
    return {"human_review_required": requires_review}


def route_after_decision(state: AgentState) -> str:
    return "human_approval" if state["human_review_required"] else "publish_comment"


def human_approval(state: AgentState) -> dict:
    """Stub: `interrupt` real do LangGraph + checkpointer chegam no card 15."""
    return {}


def route_after_approval(state: AgentState) -> str:
    return "publish_comment" if state["approval_decision"] == "APPROVED" else "archive"


def publish_comment(state: AgentState) -> dict:
    """Stub de RF-08: chamada real ao GitHub chega no card 10."""
    return {"published_comment_url": f"stub://issue/{state['issue_number']}/comment"}


def archive(state: AgentState) -> dict:
    return {}
