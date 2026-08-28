"""Interface mínima do RADAR (RF-10, card 30): API FastAPI + uma página
única (RF-10.1/10.2/10.3) para submeter um requisito, ver pareceres
aguardando aprovação e inspecionar a trilha de auditoria de uma sessão.

O grafo e o checkpointer são construídos uma vez, no `lifespan` do app, e
reutilizados por todas as requisições — é o que faz `POST
/approvals/{session_id}` conseguir retomar uma execução pausada por
`POST /analyze` numa requisição anterior (RF-07.1/07.2, cards 15/16).
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
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
from src.graph.escalation import describe_gaps, escalation_reason, last_escalation_decision
from src.graph.state import MAX_REVIEW_ROUNDS, AgentState, create_initial_state
from src.observability.audit import list_pending_sessions, read_audit_trail
from src.observability.tracing import configure_tracing

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent / "static"

# Card 51: mesmo diretório que `publish_comment._write_dry_run_file` usa por
# padrão. Em DRY_RUN (ou sem `issue_number`) o parecer é gravado aqui e
# servido por `GET /comment/{session_id}` — um link `file://` não abre a
# partir de uma página http.
DRY_RUN_COMMENT_DIR = "audit/dry_run"

# Card 50: chaves do `AgentState` adicionadas depois da primeira versão que
# pausava em `human_approval`. Um checkpoint gravado por uma versão antiga
# não as tem, e retomá-lo daria `KeyError` num node — aqui completamos o
# state congelado com o default antes de retomar.
_RESUME_SCHEMA_DEFAULTS: dict[str, object] = {
    "github_repo": None,
    "risk_assessed": True,
    "reviewer_context": [],
    "review_rounds": 0,
    "reanalysis_requested": False,
    "review_brief": None,
}


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


def _comment_url(session_id: str, result: dict) -> str | None:
    """Card 51: o `publish_comment` devolve `https://...` quando publica de
    verdade na Issue, e `file://audit/dry_run/...` em DRY_RUN. O `file://`
    não abre no navegador — troca pelo endpoint `GET /comment/{id}`."""
    url = result.get("published_comment_url")
    if url and url.startswith("file://"):
        return f"/comment/{session_id}"
    return url


def _to_analyze_response(session_id: str, result: dict) -> AnalyzeResponse:
    return AnalyzeResponse(
        session_id=session_id,
        status=_status_from_result(result),
        github_repo=result.get("github_repo") or os.getenv("GITHUB_REPO") or None,
        risk_level=result.get("risk_level"),
        risk_assessed=bool(result.get("risk_assessed", True)),
        confidence=result.get("confidence"),
        human_review_required=bool(result.get("human_review_required")),
        published_comment_url=_comment_url(session_id, result),
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
    state: AgentState = create_initial_state(
        request.text, issue_number=request.issue_number, github_repo=request.repo
    )
    config_dict = {"configurable": {"thread_id": state["session_id"]}}

    result = app.state.graph.invoke(state, config=config_dict)

    return _to_analyze_response(state["session_id"], result)


def _is_paused_for_approval(snapshot) -> bool:
    return snapshot.next == ("human_approval",)


@app.get("/approvals", response_model=list[PendingApproval])
def list_approvals() -> list[PendingApproval]:
    """RF-10.2: painel de pareceres aguardando aprovação. Card 50: só lista
    sessões cujo checkpoint ainda existe e está de fato pausado em
    `human_approval` — as que a trilha de auditoria marca como escaladas
    mas cujo checkpoint foi perdido (ex.: banco recriado) não aparecem,
    porque não dá para agir sobre elas. Cada item traz o `review_brief`
    (card 49) lido do state congelado."""
    items: list[PendingApproval] = []
    for entry in list_pending_sessions():
        session_id = entry["session_id"]
        snapshot = app.state.graph.get_state({"configurable": {"thread_id": session_id}})
        if not _is_paused_for_approval(snapshot):
            continue
        items.append(
            PendingApproval(
                session_id=session_id,
                risk_level=entry.get("risk_level"),
                risk_assessed=entry["decision"] == "ESCALATED",
                confidence=entry.get("confidence"),
                threshold=entry.get("threshold"),
                escalated_at=entry["timestamp"],
                review_brief=snapshot.values.get("review_brief") if snapshot.values else None,
            )
        )
    return items


def _pending_snapshot_or_404(session_id: str):
    config_dict = {"configurable": {"thread_id": session_id}}
    snapshot = app.state.graph.get_state(config_dict)
    if not _is_paused_for_approval(snapshot):
        raise HTTPException(
            status_code=404,
            detail=f"sessão {session_id!r} não encontrada ou não está aguardando aprovação",
        )
    return config_dict, snapshot


def _backfill_missing_state(config_dict: dict, values: dict) -> None:
    """Card 50: completa o state congelado com as chaves de `AgentState`
    que uma versão antiga do agente não gravou, antes de retomar."""
    missing = {k: v for k, v in _RESUME_SCHEMA_DEFAULTS.items() if k not in values}
    if missing:
        logger.warning(
            "approval_state_backfilled",
            extra={"thread_id": config_dict["configurable"]["thread_id"], "keys": list(missing)},
        )
        app.state.graph.update_state(config_dict, missing)


@app.get("/approvals/{session_id}", response_model=EscalationDetail)
def get_escalation_detail(session_id: str) -> EscalationDetail:
    """Cards 47/49: o parecer parcial de uma sessão escalada, `gaps` (o que
    faltou) e o `review_brief` (resumo gerado pela IA). Lê o `AgentState`
    congelado no checkpointer."""
    _config_dict, snapshot = _pending_snapshot_or_404(session_id)
    values = snapshot.values
    entries = read_audit_trail(session_id)
    last_decision = last_escalation_decision(entries)
    threshold = next(
        (e.get("threshold") for e in reversed(entries) if e.get("threshold") is not None), None
    )
    requirement = values.get("requirement")
    return EscalationDetail(
        session_id=session_id,
        risk_level=values.get("risk_level"),
        risk_assessed=bool(values.get("risk_assessed", True)),
        confidence=values.get("confidence"),
        threshold=threshold,
        escalation_reason=escalation_reason(last_decision),
        review_brief=values.get("review_brief"),
        requirement_summary=requirement.text if requirement else None,
        impacts=values.get("impacts", []),
        risks=values.get("risks", []),
        dependencies=values.get("dependencies", []),
        recommended_tests=values.get("recommended_tests", []),
        evidence_sources=values.get("evidence_sources", []),
        gaps=describe_gaps(values, last_decision),
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
    _backfill_missing_state(config_dict, snapshot.values)

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

    try:
        result = app.state.graph.invoke(Command(resume=resume), config=config_dict)
    except Exception as exc:  # noqa: BLE001 - card 50: retomada falhou -> 409, não 500
        logger.exception("approval_resume_failed", extra={"session_id": session_id})
        raise HTTPException(
            status_code=409,
            detail=(
                f"não foi possível retomar a sessão {session_id!r} — provavelmente foi "
                "criada por uma versão anterior do agente. Descarte-a e submeta o requisito de novo."
            ),
        ) from exc

    return _to_analyze_response(session_id, result)


@app.get("/audit/{session_id}", response_model=list[AuditEntry])
def get_audit_trail(session_id: str) -> list[AuditEntry]:
    """RF-09.4: reconstrói a trilha de auditoria de uma sessão."""
    entries = read_audit_trail(session_id)
    if not entries:
        raise HTTPException(status_code=404, detail=f"nenhuma auditoria para {session_id!r}")
    return entries


@app.get("/comment/{session_id}", response_class=PlainTextResponse, include_in_schema=False)
def get_dry_run_comment(session_id: str) -> PlainTextResponse:
    """Card 51: serve o parecer gravado em DRY_RUN
    (`audit/dry_run/{session_id}.md`) — o link "Ver comentário publicado" da
    página aponta para cá quando não houve publicação real na Issue."""
    path = Path(DRY_RUN_COMMENT_DIR) / f"{session_id}.md"
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"nenhum comentário para {session_id!r}")
    return PlainTextResponse(
        path.read_text(encoding="utf-8"), media_type="text/markdown; charset=utf-8"
    )
