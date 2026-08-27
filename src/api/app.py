"""Interface mínima do RADAR (RF-10, card 30): API FastAPI + uma página
única (RF-10.1/10.2/10.3) para submeter um requisito, ver pareceres
aguardando aprovação e inspecionar a trilha de auditoria de uma sessão.

O grafo e o checkpointer são construídos uma vez, no `lifespan` do app, e
reutilizados por todas as requisições — é o que faz `POST
/approvals/{session_id}` conseguir retomar uma execução pausada por
`POST /analyze` numa requisição anterior (RF-07.1/07.2, cards 15/16).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from langgraph.types import Command

from src import config  # noqa: F401 - carrega .env como efeito colateral do import
from src.api.schemas import (
    AnalysisStatus,
    AnalyzeRequest,
    AnalyzeResponse,
    ApprovalDecisionRequest,
    AuditEntry,
    EscalationDetail,
    PendingApproval,
)
from src.governance.adversarial import detect_by_pattern
from src.graph.build import build_graph
from src.graph.checkpointer import build_checkpointer
from src.graph.state import MAX_REVIEW_ROUNDS, AgentState, create_initial_state
from src.observability.audit import list_pending_sessions, read_audit_trail
from src.observability.tracing import configure_tracing

STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_tracing()
    checkpointer = build_checkpointer()
    app.state.graph = build_graph(checkpointer=checkpointer)
    yield
    checkpointer.conn.close()


app = FastAPI(title="RADAR — Agente de Análise de Impacto e Risco", lifespan=lifespan)

# Só o JS compilado (a partir de src/api/static/ts/, ver package.json) é
# exposto em /static — as fontes TypeScript não precisam ser servidas ao
# navegador.
app.mount("/static", StaticFiles(directory=STATIC_DIR / "js"), name="static")


def _status_from_result(result: dict) -> AnalysisStatus:
    if result.get("is_adversarial"):
        return "blocked"
    if "__interrupt__" in result:
        return "pending_approval"
    if result.get("published_comment_url"):
        return "published"
    return "archived"


def _to_analyze_response(session_id: str, result: dict) -> AnalyzeResponse:
    return AnalyzeResponse(
        session_id=session_id,
        status=_status_from_result(result),
        risk_level=result.get("risk_level"),
        risk_assessed=bool(result.get("risk_assessed", True)),
        confidence=result.get("confidence"),
        human_review_required=bool(result.get("human_review_required")),
        published_comment_url=result.get("published_comment_url"),
        is_adversarial=bool(result.get("is_adversarial")),
        adversarial_reason=result.get("adversarial_reason"),
    )


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    """RF-01.2: submete um requisito em texto livre. Roda o grafo até
    publicar, arquivar, bloquear (cenário 3) ou pausar para aprovação
    (cenário 2) — o que acontecer primeiro."""
    state: AgentState = create_initial_state(request.text, issue_number=request.issue_number)
    config_dict = {"configurable": {"thread_id": state["session_id"]}}

    result = app.state.graph.invoke(state, config=config_dict)

    return _to_analyze_response(state["session_id"], result)


@app.get("/approvals", response_model=list[PendingApproval])
def list_approvals() -> list[PendingApproval]:
    """RF-10.2: painel de pareceres aguardando aprovação."""
    return [
        PendingApproval(
            session_id=entry["session_id"],
            risk_level=entry.get("risk_level"),
            risk_assessed=entry["decision"] == "ESCALATED",
            confidence=entry.get("confidence"),
            threshold=entry.get("threshold"),
            escalated_at=entry["timestamp"],
        )
        for entry in list_pending_sessions()
    ]


_ESCALATION_REASONS = {
    "ESCALATED": "confiança abaixo do threshold ou risco crítico",
    "ESCALATED_BUDGET_EXCEEDED": "orçamento de execução estourado",
    "ESCALATED_NOT_ASSESSED": "análise não produziu impactos nem riscos (evidência insuficiente)",
}


def _pending_snapshot_or_404(session_id: str):
    config_dict = {"configurable": {"thread_id": session_id}}
    snapshot = app.state.graph.get_state(config_dict)
    if snapshot.next != ("human_approval",):
        raise HTTPException(
            status_code=404,
            detail=f"sessão {session_id!r} não encontrada ou não está aguardando aprovação",
        )
    return config_dict, snapshot


def _derive_gaps(values: dict, last_decision: str | None) -> list[str]:
    gaps: list[str] = []
    if not values.get("code_matches"):
        gaps.append("Nenhuma evidência de código (busca no repositório vazia).")
    if not values.get("impact_patterns"):
        gaps.append("Nenhum padrão de impacto recuperado do RAG.")
    if not values.get("change_history"):
        gaps.append("Nenhum histórico de mudanças relacionado.")
    if values.get("tools_failed"):
        gaps.append(f"Ferramentas com falha: {', '.join(values['tools_failed'])}.")
    if last_decision == "ESCALATED_BUDGET_EXCEEDED":
        gaps.append("Orçamento de execução estourado antes de a análise concluir.")
    if last_decision == "ESCALATED_NOT_ASSESSED":
        gaps.append("A análise não classificou nenhum impacto ou risco.")
    return gaps


@app.get("/approvals/{session_id}", response_model=EscalationDetail)
def get_escalation_detail(session_id: str) -> EscalationDetail:
    """Card 47: o parecer parcial de uma sessão escalada + `gaps` (o que
    faltou). Lê o `AgentState` congelado no checkpointer."""
    _config_dict, snapshot = _pending_snapshot_or_404(session_id)
    values = snapshot.values
    entries = read_audit_trail(session_id)
    escalations = [e for e in entries if e["decision"] in _ESCALATION_REASONS]
    last_decision = escalations[-1]["decision"] if escalations else None
    requirement = values.get("requirement")
    return EscalationDetail(
        session_id=session_id,
        risk_level=values.get("risk_level"),
        risk_assessed=bool(values.get("risk_assessed", True)),
        confidence=values.get("confidence"),
        threshold=escalations[-1].get("threshold") if escalations else None,
        escalation_reason=_ESCALATION_REASONS.get(last_decision, "escalado para revisão humana"),
        requirement_summary=requirement.text if requirement else None,
        impacts=values.get("impacts", []),
        risks=values.get("risks", []),
        dependencies=values.get("dependencies", []),
        recommended_tests=values.get("recommended_tests", []),
        evidence_sources=values.get("evidence_sources", []),
        gaps=_derive_gaps(values, last_decision),
        review_rounds=values.get("review_rounds", 0),
        max_review_rounds=MAX_REVIEW_ROUNDS,
    )


@app.post("/approvals/{session_id}", response_model=AnalyzeResponse)
def submit_approval(session_id: str, request: ApprovalDecisionRequest) -> AnalyzeResponse:
    """RF-07.2: aprova, rejeita ou pede reanálise (card 47) de uma sessão
    pausada em `human_approval`. 404 se a sessão não existe ou já não está
    mais aguardando aprovação — `graph.get_state` devolve `next=()` nos dois
    casos (thread desconhecida ou já resolvida)."""
    config_dict, snapshot = _pending_snapshot_or_404(session_id)

    if request.decision == "REANALYZE":
        context = (request.context or "").strip()
        check = detect_by_pattern(context)
        if check.is_adversarial:
            raise HTTPException(
                status_code=400,
                detail=f"contexto recusado: parece conter instrução dirigida ao agente ({check.reason})",
            )
        if snapshot.values.get("review_rounds", 0) >= MAX_REVIEW_ROUNDS:
            raise HTTPException(
                status_code=409,
                detail=f"limite de {MAX_REVIEW_ROUNDS} reanálises atingido; aprove ou rejeite",
            )
        resume: object = {"action": "REANALYZE", "context": context or None}
    else:
        resume = request.decision

    result = app.state.graph.invoke(Command(resume=resume), config=config_dict)

    return _to_analyze_response(session_id, result)


@app.get("/audit/{session_id}", response_model=list[AuditEntry])
def get_audit_trail(session_id: str) -> list[AuditEntry]:
    """RF-09.4: reconstrói a trilha de auditoria de uma sessão."""
    entries = read_audit_trail(session_id)
    if not entries:
        raise HTTPException(status_code=404, detail=f"nenhuma auditoria para {session_id!r}")
    return entries
