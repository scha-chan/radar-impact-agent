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
    PendingApproval,
)
from src.graph.build import build_graph
from src.graph.checkpointer import build_checkpointer
from src.graph.state import AgentState, create_initial_state
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


@app.post("/approvals/{session_id}", response_model=AnalyzeResponse)
def submit_approval(session_id: str, request: ApprovalDecisionRequest) -> AnalyzeResponse:
    """RF-07.2: aprova ou rejeita uma sessão pausada em `human_approval`.
    404 se a sessão não existe ou já não está mais aguardando aprovação —
    `graph.get_state` devolve `next=()` nos dois casos (thread desconhecida
    ou já resolvida), então não dá para distinguir um do outro sem
    consultar a trilha de auditoria; a mensagem de erro reflete isso."""
    config_dict = {"configurable": {"thread_id": session_id}}
    snapshot = app.state.graph.get_state(config_dict)
    if snapshot.next != ("human_approval",):
        raise HTTPException(
            status_code=404,
            detail=f"sessão {session_id!r} não encontrada ou não está aguardando aprovação",
        )

    result = app.state.graph.invoke(Command(resume=request.decision), config=config_dict)

    return _to_analyze_response(session_id, result)


@app.get("/audit/{session_id}", response_model=list[AuditEntry])
def get_audit_trail(session_id: str) -> list[AuditEntry]:
    """RF-09.4: reconstrói a trilha de auditoria de uma sessão."""
    entries = read_audit_trail(session_id)
    if not entries:
        raise HTTPException(status_code=404, detail=f"nenhuma auditoria para {session_id!r}")
    return entries
