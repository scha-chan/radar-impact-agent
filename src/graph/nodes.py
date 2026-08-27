"""Nodes do grafo RADAR.

Cada node produz uma atualizacao do `AgentState`. A topologia foi montada
com nodes stub (card 04) e as integracoes reais entraram depois:
extract_requirement (LLM, card 6), search_codebase/fetch_history (GitHub
API, cards 8-9), retrieve_rag (ChromaDB, card 13), analyze_impact (LLM,
card 44), score_risk (Python puro, card 02), human_approval (interrupt +
checkpointer, card 15), publish_comment (GitHub API, card 10),
guard_adversarial (detector real, card 18). `budget_gate` continua sendo
so um ponto de checagem (card 35).
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone

from langgraph.types import interrupt
from opentelemetry import trace as otel_trace

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
from src.governance.adversarial import AdversarialVerdict, detect_by_pattern, render_block_message
from src.governance.permissions import PermissionDeniedError
from src.governance.tool_executor import ToolExecutor
from src.observability.audit import AuditRecord, read_audit_trail, record_audit
from src.graph.budget import elapsed_seconds, is_budget_exceeded
from src.graph.escalation import describe_gaps, escalation_reason, last_escalation_decision
from src.graph.llm import LLM_MODEL
from src.graph.state import (
    MAX_REVIEW_ROUNDS,
    AgentState,
    ComposedReport,
    EvidenceSource,
    ImpactAnalysis,
    ImpactAnalysisResult,
    Requirement,
    ReviewBrief,
)
from src.mcp_server.tools.fetch_history import FETCH_HISTORY_PERMISSION
from src.mcp_server.tools.fetch_history import fetch_history as _fetch_history
from src.mcp_server.tools.publish_comment import PUBLISH_COMMENT_PERMISSION, render_comment
from src.mcp_server.tools.publish_comment import publish_comment as _publish_comment
from src.mcp_server.tools.search_code import SEARCH_CODE_PERMISSION, search_code
from src.rag.retriever import retrieve_patterns

logger = logging.getLogger(__name__)

CONFIDENCE_THRESHOLD = int(os.getenv("CONFIDENCE_THRESHOLD", "70"))
APPROVAL_TTL_HOURS = int(os.getenv("APPROVAL_TTL_HOURS", "24"))

# RF-08.2 generalizado (card 17, seção 13 do PRD): toda tool com efeito
# externo (busca no GitHub, publicação) passa por aqui. retrieve_rag não
# está registrada por não ser uma tool MCP externa (é ChromaDB local, sem
# side effect fora do processo) — ver docstring de retrieve_rag.
_tool_executor = ToolExecutor()
_tool_executor.register(SEARCH_CODE_PERMISSION)
_tool_executor.register(FETCH_HISTORY_PERMISSION)
_tool_executor.register(PUBLISH_COMMENT_PERMISSION)

_SEVERITY_BY_NAME = {s.name: s for s in Severity}
_PROBABILITY_BY_NAME = {p.name: p for p in Probability}
_RISK_LEVEL_NAME = {level: level.name for level in RiskLevel}


def _set_gen_ai_span_attributes() -> None:
    """RF-09.6: convenções semânticas GenAI da OpenTelemetry no span do
    node atual (aberto por `graph/tracing.py::trace_node`, um por node,
    RF-09.2). `gen_ai.usage.*` fica de fora — `with_structured_output`
    (LangChain) devolve o Pydantic já parseado, não o `AIMessage` com
    `usage_metadata`; adicionar exigiria trocar a chamada por uma sem
    saída estruturada só para capturar contagem de tokens, o que não vale
    a troca aqui."""
    span = otel_trace.get_current_span()
    span.set_attribute("gen_ai.operation.name", "chat")
    span.set_attribute("gen_ai.request.model", LLM_MODEL)


def _set_gen_ai_tool_span_attribute(tool_name: str) -> None:
    """RF-09.6: `gen_ai.tool.name` no span do node que invoca uma tool
    MCP (`search_code`/`fetch_history`/`publish_comment`)."""
    otel_trace.get_current_span().set_attribute("gen_ai.tool.name", tool_name)


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
    _set_gen_ai_span_attributes()
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
    """RF-06.3 (card 18, cenário 3): duas camadas de detecção no node — a
    terceira (contenção arquitetural) já existe estruturalmente, porque
    `score_risk` (cards 02/04) é Python puro e nunca é decidido pelo LLM.

    Camada 1, `detect_by_pattern` (determinística, sem custo): roda
    primeiro. Camada 2 (LLM) só é chamada se a camada 1 não encontrar nada
    — evita gastar uma chamada de modelo em casos óbvios.

    Falha na chamada da camada 2 (Ollama fora do ar, etc.) resulta em
    `is_adversarial=False` (fail-open) — decisão consciente: a garantia
    real do sistema é a camada 3, não esta. Bloquear tudo sempre que o LLM
    de checagem estiver indisponível seria trocar disponibilidade por uma
    proteção que já existe de outra forma.
    """
    raw_requirement = state["raw_requirement"]

    pattern_check = detect_by_pattern(raw_requirement)
    if pattern_check.is_adversarial:
        logger.warning("adversarial_detected_by_pattern", extra={"reason": pattern_check.reason})
        return {"is_adversarial": True, "adversarial_reason": pattern_check.reason}

    prompt = prompts.build_guard_adversarial_prompt(raw_requirement)
    try:
        _set_gen_ai_span_attributes()
        structured_llm = build_chat_model().with_structured_output(AdversarialVerdict)
        verdict = structured_llm.invoke(prompt)
    except Exception as exc:  # noqa: BLE001 - fail-open documentado acima
        logger.warning("guard_adversarial_llm_failed", extra={"error": str(exc)})
        return {"is_adversarial": False, "adversarial_reason": None}

    if verdict.is_adversarial:
        logger.warning("adversarial_detected_by_llm", extra={"reason": verdict.reason})
        return {"is_adversarial": True, "adversarial_reason": verdict.reason}
    return {"is_adversarial": False, "adversarial_reason": None}


def block(state: AgentState) -> dict:
    """Cenário 3: nenhuma tool de escrita é chamada a partir daqui — o
    grafo desvia direto para `END` (ver `_route_after_guard`,
    `graph/build.py`). A mensagem no formato da seção 12 do PRD é gerada
    para o log estruturado; a API (card 30) reaproveita
    `render_block_message` para a resposta. RF-09.3 (card 20): registra
    `BLOCKED_ADVERSARIAL` na trilha de auditoria, com o trecho ofensor.
    """
    reason = state["adversarial_reason"] or "conteúdo bloqueado por política de segurança."
    block_message = render_block_message(reason)
    logger.warning(
        "adversarial_blocked",
        extra={"session_id": state["session_id"], "block_message": block_message},
    )
    record_audit(
        AuditRecord(
            session_id=state["session_id"],
            decision="BLOCKED_ADVERSARIAL",
            actor="system",
            reason=state["adversarial_reason"],
        )
    )
    return {}


# Latencia de I/O simulada — usada pelos testes de fan-out (card 05,
# tests/integration/test_evidence_parallelism.py) para simular a rede de
# search_codebase/fetch_history sem depender de GITHUB_TOKEN configurado.
# Os tres nodes de evidencia ja sao reais (cards 8, 9, 13); nenhum deles usa
# esta constante em producao.
STUB_IO_LATENCY_SECONDS = 0.1


def search_codebase(state: AgentState) -> dict:
    """RF-03.1: busca real via API do GitHub (`search_code`). RF-03.4: cada
    arquivo encontrado vira uma entrada em `evidence_sources`. RF-03.5/
    cenário 4: se a tool esgotar as tentativas, `tools_failed` registra o
    fallback para `score_risk` penalizar a confiança."""
    requirement = state["requirement"]
    search_terms = requirement.search_terms if requirement else []
    if not search_terms:
        return {"code_matches": [], "evidence_sources": [], "tools_failed": []}

    failures: list[str] = []
    _set_gen_ai_tool_span_attribute("search_code")
    matches = _tool_executor.execute(
        "search_code",
        state,
        lambda: search_code(
            search_terms,
            repo=os.getenv("GITHUB_REPO", ""),
            github_token=os.getenv("GITHUB_TOKEN", ""),
            failures=failures,
        ),
    )
    evidence = [EvidenceSource(type="code", ref=match.file) for match in matches]
    tools_failed = ["search_code"] if failures else []
    return {"code_matches": matches, "evidence_sources": evidence, "tools_failed": tools_failed}


def retrieve_rag(state: AgentState) -> dict:
    """RF-03.2: recuperacao semantica real via ChromaDB (`retrieve_patterns`,
    card 13). RF-03.4: cada padrao recuperado vira uma entrada em
    `evidence_sources`. Sem `search_terms`, usa o texto bruto do requisito
    como consulta — ainda ha algo para comparar semanticamente com o corpus,
    diferente de search_codebase/fetch_history, que dependem de termos
    exatos para buscar na API do GitHub.

    Não passa pelo `ToolExecutor` (card 17): `retrieve_patterns` é ChromaDB
    local, sem chamada de API externa nem ação destrutiva — não é uma tool
    registrada no servidor MCP (`mcp_server/server.py`) como search_code/
    fetch_history/publish_comment são."""
    requirement = state["requirement"]
    if requirement is None:
        return {"impact_patterns": [], "evidence_sources": []}

    query_text = " ".join(requirement.search_terms) or requirement.text
    patterns = retrieve_patterns(requirement.feature_type, query_text)
    evidence = [EvidenceSource(type="rag", ref=pattern.source) for pattern in patterns]
    return {"impact_patterns": patterns, "evidence_sources": evidence}


def fetch_history(state: AgentState) -> dict:
    """RF-03.3: commits e PRs reais via API do GitHub. RF-03.4: cada
    resultado vira uma entrada em `evidence_sources`. RF-03.5/cenário 4:
    fallback registrado em `tools_failed`."""
    requirement = state["requirement"]
    search_terms = requirement.search_terms if requirement else []
    if not search_terms:
        return {"change_history": [], "evidence_sources": [], "tools_failed": []}

    failures: list[str] = []
    _set_gen_ai_tool_span_attribute("fetch_history")
    entries = _tool_executor.execute(
        "fetch_history",
        state,
        lambda: _fetch_history(
            search_terms,
            repo=os.getenv("GITHUB_REPO", ""),
            github_token=os.getenv("GITHUB_TOKEN", ""),
            failures=failures,
        ),
    )
    evidence = [EvidenceSource(type="history", ref=entry.ref) for entry in entries]
    tools_failed = ["fetch_history"] if failures else []
    return {"change_history": entries, "evidence_sources": evidence, "tools_failed": tools_failed}


def budget_gate(state: AgentState) -> dict:
    """RF-06.5 (card 35, cenário 5): ponto de checagem entre o fan-in de
    evidência e `analyze_impact` — se o orçamento (`max_steps`/
    `MAX_WALL_TIME_SECONDS`) já estourou aqui, `_route_after_budget_gate`
    (`graph/build.py`) desvia direto para `decide_autonomy`, pulando
    `analyze_impact`/`score_risk` de propósito: "nunca deixa o requisito
    passar como se tivesse sido totalmente analisado" (cenário 5). A
    checagem de novo dentro de `decide_autonomy` cobre o caso do orçamento
    estourar só durante `analyze_impact`/`score_risk`, depois deste
    node já ter deixado passar."""
    return {}


_EMPTY_ANALYSIS = {"impacts": [], "risks": [], "dependencies": [], "recommended_tests": []}


def _known_evidence_refs(state: AgentState) -> set[str]:
    """Todos os identificadores de evidência coletada que um impacto pode
    citar em `Impact.evidence` (RF-04.5) — o arquivo/fonte/ref e também o
    basename do arquivo, porque o modelo às vezes cita só `orders.py` em
    vez do caminho inteiro."""
    refs: set[str] = set()
    for match in state["code_matches"]:
        refs.add(match.file)
        refs.add(match.file.rsplit("/", 1)[-1])
    for pattern in state["impact_patterns"]:
        refs.add(pattern.source)
    for entry in state["change_history"]:
        refs.add(entry.ref)
    for source in state["evidence_sources"]:
        refs.add(source.ref)
    if state["reviewer_context"]:
        refs.add("revisor")  # card 47: impacto pode se apoiar no contexto do revisor
    return {ref for ref in refs if ref}


def _impact_is_grounded(evidence: str, known_refs: set[str]) -> bool:
    text = (evidence or "").strip()
    if not text:
        return False
    return any(ref in text or text in ref for ref in known_refs)


def analyze_impact(state: AgentState) -> dict:
    """RF-04: o LLM classifica impactos por área (severidade + evidência),
    enumera riscos (severidade × probabilidade + mitigação), lista
    dependências externas e sugere testes prioritários, a partir da
    evidência coletada em paralelo (código, RAG, histórico).

    O LLM não decide `risk_level` nem `confidence` (RF-05.4) — só alimenta
    `score_risk`, que é Python puro.

    RF-04.5 (rastreabilidade): nenhuma afirmação sem evidência. Se nenhuma
    fonte de evidência foi coletada, a saída é vazia — não há o que
    sustentar. Caso contrário, impactos cujo campo `evidence` não referencia
    nenhuma fonte coletada são descartados (com log), nunca publicados.

    Card 47: numa reanálise pedida pelo revisor, `reviewer_context` entra
    no prompt como mais uma fonte de evidência (já registrado em
    `evidence_sources` por `human_approval`).

    Tratamento de falha (mesma filosofia de `extract_requirement`/
    `guard_adversarial`): erro de chamada ou de parse do LLM → listas
    vazias e log; o grafo continua e `score_risk` penaliza a confiança do
    resultado degradado (seção 11 do PRD).
    """
    requirement = state["requirement"]
    if requirement is None or not state["evidence_sources"]:
        return dict(_EMPTY_ANALYSIS)

    _set_gen_ai_span_attributes()
    prompt = prompts.build_analyze_impact_prompt(
        requirement,
        state["code_matches"],
        state["impact_patterns"],
        state["change_history"],
        state["reviewer_context"],
    )
    try:
        structured_llm = build_chat_model().with_structured_output(ImpactAnalysisResult)
        result = structured_llm.invoke(prompt)
    except Exception as exc:  # noqa: BLE001 - parse e erro de chamada tratados igual (RF-04, degradação)
        logger.error(
            "analyze_impact_failed",
            extra={"session_id": state["session_id"], "error": str(exc)},
        )
        return dict(_EMPTY_ANALYSIS)

    known_refs = _known_evidence_refs(state)
    grounded = [imp for imp in result.impacts if _impact_is_grounded(imp.evidence, known_refs)]
    dropped = len(result.impacts) - len(grounded)
    if dropped:
        logger.warning(
            "analyze_impact_dropped_ungrounded_impacts",
            extra={"session_id": state["session_id"], "dropped": dropped},
        )
    return {
        "impacts": grounded,
        "risks": result.risks,
        "dependencies": result.dependencies,
        "recommended_tests": result.recommended_tests,
    }


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
        tools_failed_with_fallback=len(state["tools_failed"]),
        distinct_evidence_sources=len(state["evidence_sources"]),
        risks=risk_items,
    )
    confidence = calculate_confidence(inputs)

    return {
        "risk_level": _RISK_LEVEL_NAME[risk_level],
        "confidence": confidence,
    }


_RISK_RANK = {None: -1, "LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}


def decide_autonomy(state: AgentState) -> dict:
    """RF-06: decisão determinística de autonomia (node `route_by_confidence`).

    RF-07.4 (card 16): ao escalar, já grava o prazo de expiração da
    aprovação (`APPROVAL_TTL_HOURS`, padrão 24h) no state. Isso precisa
    acontecer aqui, não dentro de `human_approval` — esse node pausa via
    `interrupt()`, que nunca chega a retornar/persistir nada na primeira
    passada; `decide_autonomy` roda normalmente antes da pausa, então é o
    lugar certo para gravar `approval_expires_at` antes do checkpointer
    congelar o state.

    RF-09.3 (card 20): a decisão `ESCALATED` é registrada aqui — é onde a
    decisão de fato acontece. `AUTO_PUBLISHED`/`APPROVED_PUBLISHED` são
    registradas em `publish_comment`, não aqui, porque só valem depois que
    a publicação de fato acontece (a autorização ainda pode ser negada).

    RF-06.5 (card 35, cenário 5): rede de segurança contra o orçamento
    estourar durante `analyze_impact`/`score_risk` (depois de
    `budget_gate` já ter deixado passar) — se estourou, força
    `risk_level` mínimo MEDIUM (nunca rebaixa um risco já mais grave) e
    `human_review_required=true`, e a decisão registrada na auditoria é
    `ESCALATED_BUDGET_EXCEEDED`, não `ESCALATED`.

    Card 46: quando o parecer escala mas `analyze_impact` não produziu
    nenhum impacto nem risco e o risco agregado é baixo — evidência
    insuficiente, não uma análise que concluiu "risco baixo" —, o mesmo
    piso MEDIUM é aplicado e `risk_assessed=False` sinaliza para a UI e o
    comentário mostrarem "não avaliado" em vez de "Baixo". A decisão de
    auditoria é `ESCALATED_NOT_ASSESSED`.
    """
    budget_exceeded = is_budget_exceeded(state)
    original_risk_level = state["risk_level"]
    risk_level = original_risk_level
    already_elevated = _RISK_RANK.get(original_risk_level, -1) >= _RISK_RANK["MEDIUM"]

    if budget_exceeded and _RISK_RANK.get(risk_level, -1) < _RISK_RANK["MEDIUM"]:
        risk_level = "MEDIUM"

    requires_review = (
        budget_exceeded
        or risk_level == "CRITICAL"
        or (state["confidence"] or 0) < CONFIDENCE_THRESHOLD
    )

    # "avaliado" = analyze_impact produziu algo, OU o risco já era >= MEDIUM
    # (houve sinal), OU nem precisou de revisão (confiança alta é um veredito
    # real). Caso contrário: escalou sem base — não avaliado.
    risk_assessed = (
        bool(state["impacts"] or state["risks"]) or already_elevated or not requires_review
    )
    not_assessed_escalation = requires_review and not budget_exceeded and not risk_assessed
    if not_assessed_escalation and _RISK_RANK.get(risk_level, -1) < _RISK_RANK["MEDIUM"]:
        risk_level = "MEDIUM"

    update: dict = {
        "human_review_required": requires_review,
        "risk_assessed": risk_assessed,
    }
    if risk_level != original_risk_level:
        update["risk_level"] = risk_level
    if requires_review:
        update["approval_expires_at"] = datetime.now(timezone.utc) + timedelta(
            hours=APPROVAL_TTL_HOURS
        )
        if budget_exceeded:
            decision = "ESCALATED_BUDGET_EXCEEDED"
        elif not_assessed_escalation:
            decision = "ESCALATED_NOT_ASSESSED"
        else:
            decision = "ESCALATED"
        record_audit(
            AuditRecord(
                session_id=state["session_id"],
                decision=decision,
                actor="system",
                risk_level=risk_level,
                confidence=state["confidence"],
                threshold=CONFIDENCE_THRESHOLD,
                steps_taken=state["steps_taken"] if budget_exceeded else None,
                max_steps=state["max_steps"] if budget_exceeded else None,
                duration_seconds=round(elapsed_seconds(state), 3) if budget_exceeded else None,
            )
        )
        if budget_exceeded:
            logger.warning(
                "budget_exceeded",
                extra={
                    "session_id": state["session_id"],
                    "steps_taken": state["steps_taken"],
                    "max_steps": state["max_steps"],
                    "duration_seconds": round(elapsed_seconds(state), 3),
                },
            )
    return update


def route_after_decision(state: AgentState) -> str:
    return "brief_escalation" if state["human_review_required"] else "publish_comment"


def _fallback_review_brief(state: AgentState, reason: str, gaps: list[str]) -> str:
    requirement = state["requirement"]
    what = (
        requirement.text.strip().splitlines()[0][:140] if requirement else state["raw_requirement"]
    )
    missing = " ".join(gaps) if gaps else "Sem lacunas específicas registradas."
    return (
        f"Mudança pedida: {what}. Escalou porque {reason} "
        f"(risco {state['risk_level'] or '—'}, confiança {state['confidence'] if state['confidence'] is not None else '—'}). "
        f"{missing}\n\n"
        "O que ajudaria numa reanálise: aponte onde já existe código ou integração "
        "relacionada, ou peça a reanálise se não houver o que acrescentar."
    )


def brief_escalation(state: AgentState) -> dict:
    """Card 49: resumo para o revisor — o que a mudança pede, por que
    escalou e o que ajudaria numa reanálise. Roda entre `decide_autonomy` e
    `human_approval`, e de novo a cada rodada de reanálise (card 47).

    O LLM só redige (`ReviewBrief`); falha da chamada → texto de fallback
    determinístico montado dos mesmos dados. Não bloqueia a escalação.
    """
    if not state["human_review_required"]:
        return {}

    last_decision = last_escalation_decision(read_audit_trail(state["session_id"]))
    reason = escalation_reason(last_decision)
    gaps = describe_gaps(state, last_decision)

    requirement = state["requirement"]
    if requirement is None:
        return {"review_brief": _fallback_review_brief(state, reason, gaps)}

    _set_gen_ai_span_attributes()
    prompt = prompts.build_review_brief_prompt(
        requirement,
        risk_level=state["risk_level"],
        risk_assessed=state["risk_assessed"],
        confidence=state["confidence"],
        threshold=CONFIDENCE_THRESHOLD,
        reason=reason,
        impacts=state["impacts"],
        risks=state["risks"],
        gaps=gaps,
    )
    try:
        brief = build_chat_model().with_structured_output(ReviewBrief).invoke(prompt)
    except Exception as exc:  # noqa: BLE001 - degradação: escala com o brief de fallback
        logger.error(
            "brief_escalation_failed",
            extra={"session_id": state["session_id"], "error": str(exc)},
        )
        return {"review_brief": _fallback_review_brief(state, reason, gaps)}

    summary = (brief.summary or "").strip() or _fallback_review_brief(state, reason, gaps)
    suggestion = (brief.suggested_context or "").strip()
    text = (
        summary if not suggestion else f"{summary}\n\nO que ajudaria numa reanálise: {suggestion}"
    )
    return {"review_brief": text}


def human_approval(state: AgentState) -> dict:
    """RF-07.1 (card 15): suspende a execução com `interrupt()` do
    LangGraph até uma decisão humana chegar (RF-07.2, `POST
    /approvals/{session_id}` — card 30). `graph.invoke()` retorna de
    imediato com a chave `"__interrupt__"`; o state fica preservado no
    checkpointer configurado em `build_graph()` (`SqliteSaver` em produção,
    `graph/checkpointer.py`) até quem aprovar retomar com
    `graph.invoke(Command(resume=decisao), config={"configurable":
    {"thread_id": session_id}})`.

    Guarda contra pausar de novo quando `approval_decision` já veio
    preenchida no state de entrada — necessário para o grafo ainda rodar
    numa única chamada sem checkpointer (testes de topologia,
    `test_graph.py`) simulando um estado já resolvido, e também é o que
    faz o *resume* funcionar de verdade: após `Command(resume=...)`, o
    LangGraph reexecuta o node do início, mas `interrupt()` devolve o valor
    do resume em vez de pausar de novo — só que a essa altura
    `approval_decision` ainda está `None` no state (a atualização abaixo
    só é aplicada quando o node retorna). Sem a guarda, todo resume pausaria
    de novo antes de conseguir gravar a decisão.

    RF-07.4 (card 16): a checagem de expiração vem *antes* de chamar
    `interrupt()`, não depois. Isso importa em duas situações: (1) uma
    retomada tardia — alguém aprova depois do prazo — cai aqui em vez de
    chegar ao `interrupt()`, então a decisão de quem aprovou fora do prazo
    é descartada e o parecer nunca publica; (2) uma varredura periódica
    (fora do escopo deste card — caberia num scheduler do card 30) pode
    retomar sessões expiradas com qualquer valor de resume, ou nenhum, para
    arquivá-las sem publicar.

    Card 47: o valor de resume pode ser um `dict`
    `{"action": "REANALYZE", "context": str|None}` além das strings
    `"APPROVED"`/`"REJECTED"`. Numa reanálise, o node não resolve a
    aprovação — injeta o contexto do revisor como evidência, incrementa
    `review_rounds`, e `route_after_approval` volta o grafo para
    `analyze_impact`. O teto de rodadas é aplicado na rota da API
    (`submit_approval`), não aqui.
    """
    if state["approval_decision"] is not None:
        return {}
    if _is_approval_expired(state):
        logger.warning(
            "human_approval_expired",
            extra={
                "session_id": state["session_id"],
                "expires_at": str(state["approval_expires_at"]),
            },
        )
        return {"approval_decision": "REJECTED"}
    resumed = interrupt(
        {
            "session_id": state["session_id"],
            "risk_level": state["risk_level"],
            "confidence": state["confidence"],
            "review_rounds": state["review_rounds"],
            "max_review_rounds": MAX_REVIEW_ROUNDS,
            "expires_at": state["approval_expires_at"].isoformat()
            if state["approval_expires_at"]
            else None,
        }
    )

    action, context = _parse_review_action(resumed)
    if action == "REANALYZE":
        return _request_reanalysis(state, context)
    return {"approval_decision": action, "reanalysis_requested": False}


def _parse_review_action(resumed) -> tuple[str, str | None]:
    """O resume pode ser a string `"APPROVED"`/`"REJECTED"` (compat, o que
    a rota manda para aprovar/rejeitar) ou o dict do card 47
    `{"action": "REANALYZE", "context": ...}`."""
    if isinstance(resumed, dict):
        return resumed.get("action", "REJECTED"), resumed.get("context")
    return resumed, None


# Passos que uma rodada de reanálise adiciona (analyze_impact + score_risk +
# decide_autonomy + human_approval, com margem). O orçamento de execução
# (card 35) é estendido por rodada para a reanálise não estourar sozinha —
# o teto real das rodadas é MAX_REVIEW_ROUNDS, aplicado na rota da API.
_STEPS_PER_REANALYSIS = 6


def _request_reanalysis(state: AgentState, context: str | None) -> dict:
    round_number = state["review_rounds"] + 1
    ctx = (context or "").strip()
    update: dict = {
        "approval_decision": None,
        "human_review_required": False,
        "reanalysis_requested": True,
        "review_rounds": round_number,
        "max_steps": state["max_steps"] + _STEPS_PER_REANALYSIS,
    }
    if ctx:
        update["reviewer_context"] = state["reviewer_context"] + [ctx]
        update["evidence_sources"] = [
            EvidenceSource(type="reviewer", ref=f"revisor#{round_number}")
        ]
    logger.info(
        "reanalysis_requested",
        extra={
            "session_id": state["session_id"],
            "review_round": round_number,
            "has_context": bool(ctx),
        },
    )
    record_audit(
        AuditRecord(
            session_id=state["session_id"],
            decision="REANALYSIS_REQUESTED",
            actor="human",
            risk_level=state["risk_level"],
            confidence=state["confidence"],
            reason=(ctx[:200] or "reanálise sem contexto adicional"),
        )
    )
    return update


def _is_approval_expired(state: AgentState) -> bool:
    expires_at = state["approval_expires_at"]
    return expires_at is not None and datetime.now(timezone.utc) >= expires_at


def route_after_approval(state: AgentState) -> str:
    if state["approval_decision"] == "APPROVED":
        return "publish_comment"
    if state["reanalysis_requested"]:
        return "analyze_impact"  # card 47: revisor pediu reanálise com contexto novo
    return "archive"


def _build_impact_analysis(state: AgentState, requirement_summary: str) -> ImpactAnalysis:
    """Monta o `ImpactAnalysis` (seção 8 do PRD) a partir do state — puro
    e determinístico. `risk_level`/`confidence` já foram decididos por
    `score_risk`/`decide_autonomy`; aqui só são copiados para o objeto de
    saída (com defaults defensivos para o caminho de orçamento estourado,
    card 35, que pula `score_risk`)."""
    return ImpactAnalysis(
        session_id=state["session_id"],
        issue_number=state["issue_number"],
        requirement_summary=requirement_summary,
        risk_level=state["risk_level"] or "LOW",
        risk_assessed=state["risk_assessed"],
        confidence=state["confidence"] if state["confidence"] is not None else 0,
        human_review_required=state["human_review_required"],
        impacts=state["impacts"],
        risks=state["risks"],
        dependencies=state["dependencies"],
        recommended_tests=state["recommended_tests"],
        evidence_sources=state["evidence_sources"],
        generated_at=datetime.now(timezone.utc),
    )


def _fallback_requirement_summary(state: AgentState) -> str:
    requirement = state["requirement"]
    text = (requirement.text if requirement else state["raw_requirement"]).strip()
    first_line = text.splitlines()[0] if text else ""
    return first_line[:140].rstrip()


def _fallback_executive_summary(analysis: ImpactAnalysis) -> str:
    review = (
        "Requer revisão humana antes de qualquer implementação."
        if analysis.human_review_required
        else "Publicado automaticamente pelo RADAR."
    )
    return (
        f"Análise concluída com nível de risco {analysis.risk_level} e confiança "
        f"{analysis.confidence}/100. {len(analysis.impacts)} impacto(s) e "
        f"{len(analysis.risks)} risco(s) identificados. {review}"
    )


def _compose_report(state: AgentState) -> tuple[ImpactAnalysis, str]:
    """RF-08 / prompt `04-compose-report` (card 45): monta o `ImpactAnalysis`
    e redige o texto do parecer.

    Só a redação passa pelo LLM — a condensação do requisito numa linha e o
    resumo executivo. Os campos estruturados (risco, confiança, impactos,
    riscos) são copiados do state, nunca reescritos pelo modelo. Falha da
    chamada → textos de fallback determinísticos e o parecer é publicado
    mesmo assim (o conteúdo que importa para a decisão já está no objeto).
    """
    base_summary = _fallback_requirement_summary(state)
    analysis = _build_impact_analysis(state, base_summary)
    exec_fallback = _fallback_executive_summary(analysis)

    try:
        _set_gen_ai_span_attributes()
        structured_llm = build_chat_model().with_structured_output(ComposedReport)
        composed = structured_llm.invoke(prompts.build_compose_report_prompt(analysis))
    except Exception as exc:  # noqa: BLE001 - degradação: publica com texto de fallback
        logger.error(
            "compose_report_failed",
            extra={"session_id": state["session_id"], "error": str(exc)},
        )
        return analysis, exec_fallback

    requirement_summary = (composed.requirement_summary or "").strip() or base_summary
    executive_summary = (composed.executive_summary or "").strip() or exec_fallback
    analysis = analysis.model_copy(update={"requirement_summary": requirement_summary})
    return analysis, executive_summary


def publish_comment(state: AgentState) -> dict:
    """RF-08: compõe o parecer (`_compose_report`, card 45) e o publica (ou
    grava em arquivo se DRY_RUN/sem Issue).

    Protegido em duas camadas (RF-08.2/RF-08.3, card 17): o `ToolExecutor`
    recusaria a chamada se `publish_comment` não estivesse registrada; a
    própria tool (`mcp_server/tools/publish_comment.py`) chama `authorize()`
    de novo internamente, então continua segura mesmo se chamada fora do
    grafo (é o que `tests/unit/test_publish_comment.py` testa direto).

    RF-09.3 (card 20): registrado só depois da publicação de fato
    acontecer — `AUTO_PUBLISHED` (`human_review_required=False`, decisão do
    sistema sozinho) ou `APPROVED_PUBLISHED` (um humano aprovou antes,
    cards 15/16). Uma negação de permissão também é uma decisão de
    autonomia auditável: `PUBLISH_DENIED` cobre o caso (não deveria
    acontecer em operação normal — indicaria um bug na checagem anterior
    de `decide_autonomy`/`human_approval` — mas se acontecer, fica
    registrado, não silencioso).
    """
    dry_run = os.getenv("DRY_RUN", "false").lower() == "true"
    analysis, prose = _compose_report(state)
    body = render_comment(state, analysis=analysis, prose=prose)
    _set_gen_ai_tool_span_attribute("publish_comment")
    try:
        url = _tool_executor.execute(
            "publish_comment",
            state,
            lambda: _publish_comment(
                state,
                repo=os.getenv("GITHUB_REPO", ""),
                github_token=os.getenv("GITHUB_TOKEN", ""),
                dry_run=dry_run,
                body=body,
            ),
        )
    except PermissionDeniedError as exc:
        logger.error("publish_comment_denied", extra={"error": str(exc)})
        record_audit(
            AuditRecord(
                session_id=state["session_id"],
                decision="PUBLISH_DENIED",
                actor="system",
                reason=str(exc),
            )
        )
        return {"analysis": analysis, "published_comment_url": None}

    record_audit(
        AuditRecord(
            session_id=state["session_id"],
            decision="APPROVED_PUBLISHED" if state["human_review_required"] else "AUTO_PUBLISHED",
            actor="human" if state["human_review_required"] else "system",
            risk_level=state["risk_level"],
            confidence=state["confidence"],
            tool_authorized="publish_comment",
        )
    )
    return {"analysis": analysis, "published_comment_url": url}


def archive(state: AgentState) -> dict:
    """RF-09.3 (card 20): registra o arquivamento. Distingue rejeição
    humana explícita de expiração de prazo (card 16) reavaliando
    `approval_expires_at` contra o relógio atual — `human_approval` nunca
    deixa uma decisão humana tardia chegar até aqui depois do prazo (a
    checagem de expiração vem antes de `interrupt()` retornar), então, se
    `approval_expires_at` já passou neste ponto, só pode ter sido o
    próprio sistema quem forçou `REJECTED` por TTL, nunca um humano.
    """
    expires_at = state["approval_expires_at"]
    expired = expires_at is not None and datetime.now(timezone.utc) >= expires_at
    record_audit(
        AuditRecord(
            session_id=state["session_id"],
            decision="EXPIRED_ARCHIVED" if expired else "REJECTED_ARCHIVED",
            actor="system" if expired else "human",
            risk_level=state["risk_level"],
            confidence=state["confidence"],
        )
    )
    return {}
