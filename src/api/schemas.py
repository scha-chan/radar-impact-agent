"""Contratos HTTP da interface mínima (RF-01.2, RF-07.2, RF-09.4, RF-10,
card 30). Modelos de request/response, separados do `AgentState` interno
do grafo — a API expõe só o que faz sentido para um client HTTP, não o
state inteiro do LangGraph."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from src.graph.state import EvidenceSource, Impact, Risk

AnalysisStatus = Literal["published", "blocked", "pending_approval", "archived"]


class AnalyzeRequest(BaseModel):
    """RF-01.2/RF-01.4: texto livre, 1 a 8000 caracteres."""

    text: str = Field(min_length=1, max_length=8000)
    issue_number: int | None = None


class AnalyzeResponse(BaseModel):
    session_id: str
    status: AnalysisStatus
    risk_level: str | None
    # False quando o parecer escalou sem impacto/risco identificado (card 46):
    # `risk_level` traz o piso MEDIUM, mas a tela mostra "não avaliado".
    risk_assessed: bool
    confidence: int | None
    human_review_required: bool
    published_comment_url: str | None
    is_adversarial: bool
    adversarial_reason: str | None


class ApprovalDecisionRequest(BaseModel):
    """RF-07.2. `REANALYZE` (card 47): em vez de encerrar, o revisor manda
    o grafo reanalisar — `context` (opcional) é o que faltou, entra como
    evidência na nova rodada de `analyze_impact`."""

    decision: Literal["APPROVED", "REJECTED", "REANALYZE"]
    context: str | None = Field(default=None, max_length=8000)


class PendingApproval(BaseModel):
    """RF-10.2: um item do painel de aprovações pendentes — derivado da
    trilha de auditoria (`list_pending_sessions`)."""

    session_id: str
    risk_level: str | None
    # False quando a sessão escalou sem avaliação (card 46) — decisão de
    # auditoria `ESCALATED_NOT_ASSESSED` ou `ESCALATED_BUDGET_EXCEEDED`.
    risk_assessed: bool
    confidence: int | None
    threshold: int | None
    escalated_at: str


class EscalationDetail(BaseModel):
    """Card 47: o "retorno" completo de uma sessão escalada, para o painel
    de detalhe — o parecer parcial (do state congelado no checkpointer) e
    `gaps`, o que faltou para a análise fechar."""

    session_id: str
    risk_level: str | None
    risk_assessed: bool
    confidence: int | None
    threshold: int | None
    escalation_reason: str
    requirement_summary: str | None
    impacts: list[Impact]
    risks: list[Risk]
    dependencies: list[str]
    recommended_tests: list[str]
    evidence_sources: list[EvidenceSource]
    gaps: list[str]
    review_rounds: int
    max_review_rounds: int


class AuditEntry(BaseModel):
    """RF-09.4: um registro da trilha de auditoria de uma sessão (mesmo
    schema de `AuditRecord.to_dict()`, `src/observability/audit.py`)."""

    timestamp: str
    session_id: str
    decision: str
    risk_level: str | None = None
    confidence: int | None = None
    threshold: int | None = None
    actor: str
    tool_authorized: str | None = None
    reason: str | None = None
