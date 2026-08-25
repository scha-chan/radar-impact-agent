"""Contrato do grafo LangGraph do RADAR: AgentState e os modelos que o compoem.

Os modelos Pydantic descrevem o formato de cada peca de evidencia e da saida
final (`ImpactAnalysis`), replicando o schema documentado no PRD (secao 8).
`AgentState` e um TypedDict porque e o formato que o LangGraph espera para
estado compartilhado entre nodes; os campos individuais usam esses modelos
para validacao.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal, TypedDict

from pydantic import BaseModel, Field

FeatureType = Literal[
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

SeverityLevel = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
ProbabilityLevel = Literal["RARE", "POSSIBLE", "LIKELY", "ALMOST_CERTAIN"]
RiskLevelLiteral = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
EvidenceType = Literal["code", "rag", "history"]
ApprovalDecision = Literal["APPROVED", "REJECTED"]


class Requirement(BaseModel):
    """Requisito extraido do texto bruto (RF-02)."""

    text: str
    feature_type: FeatureType
    search_terms: list[str] = Field(default_factory=list)


class CodeMatch(BaseModel):
    """Um trecho de codigo encontrado por `search_code` (RF-03.1)."""

    file: str
    snippet: str
    line: int | None = None


class PatternChunk(BaseModel):
    """Um padrao de impacto recuperado do RAG por `retrieve_patterns` (RF-03.2)."""

    content: str
    source: str
    similarity: float


class HistoryEntry(BaseModel):
    """Um commit ou PR relacionado, retornado por `fetch_history` (RF-03.3)."""

    type: Literal["commit", "pr"]
    ref: str
    description: str


class EvidenceSource(BaseModel):
    """Origem rastreavel de uma afirmacao do parecer (RF-04.5)."""

    type: EvidenceType
    ref: str


class Impact(BaseModel):
    """Impacto classificado por area, com evidencia associada (RF-04.1)."""

    area: str
    description: str
    severity: SeverityLevel
    evidence: str


class Risk(BaseModel):
    """Risco enumerado com severidade, probabilidade e mitigacao (RF-04.2)."""

    description: str
    severity: SeverityLevel
    probability: ProbabilityLevel
    mitigation: str | None = None


class ImpactAnalysis(BaseModel):
    """Saida principal do RADAR, publicada como comentario na Issue de origem."""

    session_id: str
    issue_number: int | None
    requirement_summary: str
    risk_level: RiskLevelLiteral
    confidence: int = Field(ge=0, le=100)
    human_review_required: bool
    impacts: list[Impact] = Field(default_factory=list)
    risks: list[Risk] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    recommended_tests: list[str] = Field(default_factory=list)
    evidence_sources: list[EvidenceSource] = Field(default_factory=list)
    generated_at: datetime


class AgentState(TypedDict):
    """Estado compartilhado do grafo — contrato entre todos os nodes (secao 8)."""

    # identificacao e rastreio
    session_id: str
    correlation_id: str
    issue_number: int | None

    # entrada
    raw_requirement: str
    requirement: Requirement | None

    # controle de fluxo
    is_adversarial: bool
    adversarial_reason: str | None
    retries_left: int
    approval_expires_at: datetime | None

    # evidencia coletada (populada em paralelo)
    code_matches: list[CodeMatch]
    impact_patterns: list[PatternChunk]
    change_history: list[HistoryEntry]
    evidence_sources: list[EvidenceSource]

    # analise
    impacts: list[Impact]
    risks: list[Risk]
    dependencies: list[str]
    recommended_tests: list[str]

    # decisao
    risk_level: RiskLevelLiteral | None
    confidence: int | None
    human_review_required: bool
    approval_decision: ApprovalDecision | None

    # saida
    analysis: ImpactAnalysis | None
    published_comment_url: str | None


def create_initial_state(
    raw_requirement: str,
    *,
    issue_number: int | None = None,
    max_retries: int = 2,
) -> AgentState:
    """Monta o estado inicial do grafo a partir de um requisito bruto.

    `session_id` e `correlation_id` compartilham o mesmo valor para permitir
    correlacionar logs, trilha de auditoria e trace de uma mesma execucao
    (secao 14 do PRD).
    """
    session_id = uuid.uuid4().hex[:8]
    return AgentState(
        session_id=session_id,
        correlation_id=session_id,
        issue_number=issue_number,
        raw_requirement=raw_requirement,
        requirement=None,
        is_adversarial=False,
        adversarial_reason=None,
        retries_left=max_retries,
        approval_expires_at=None,
        code_matches=[],
        impact_patterns=[],
        change_history=[],
        evidence_sources=[],
        impacts=[],
        risks=[],
        dependencies=[],
        recommended_tests=[],
        risk_level=None,
        confidence=None,
        human_review_required=False,
        approval_decision=None,
        analysis=None,
        published_comment_url=None,
    )
