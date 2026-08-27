"""Descrição legível de uma escalação — compartilhada entre o node
`brief_escalation` (card 49, gera o resumo para o revisor) e a API
(`GET /approvals` / `GET /approvals/{id}`, cards 47/49).

Sem dependência de FastAPI nem do grafo: recebe o `AgentState` (ou o dict
`snapshot.values` do checkpointer) e a última decisão de auditoria.
"""

from __future__ import annotations

from collections.abc import Mapping

ESCALATION_REASONS: dict[str, str] = {
    "ESCALATED": "confiança abaixo do threshold ou risco crítico",
    "ESCALATED_BUDGET_EXCEEDED": "orçamento de execução estourado",
    "ESCALATED_NOT_ASSESSED": "análise não produziu impactos nem riscos (evidência insuficiente)",
}


def escalation_reason(last_decision: str | None) -> str:
    """Frase curta para o motivo da escala, a partir da última decisão
    `ESCALATED*` da trilha de auditoria."""
    return ESCALATION_REASONS.get(last_decision or "", "escalado para revisão humana")


def last_escalation_decision(audit_entries: list[dict]) -> str | None:
    """A decisão da última entrada `ESCALATED*` da trilha (ou `None`)."""
    escalations = [e for e in audit_entries if e.get("decision") in ESCALATION_REASONS]
    return escalations[-1]["decision"] if escalations else None


def describe_gaps(state_like: Mapping[str, object], last_decision: str | None) -> list[str]:
    """O que faltou para a análise fechar — derivado do state congelado."""
    gaps: list[str] = []
    if not state_like.get("code_matches"):
        gaps.append("Nenhuma evidência de código (busca no repositório vazia).")
    if not state_like.get("impact_patterns"):
        gaps.append("Nenhum padrão de impacto recuperado do RAG.")
    if not state_like.get("change_history"):
        gaps.append("Nenhum histórico de mudanças relacionado.")
    tools_failed = state_like.get("tools_failed")
    if tools_failed:
        gaps.append(f"Ferramentas com falha: {', '.join(tools_failed)}.")  # type: ignore[arg-type]
    if last_decision == "ESCALATED_BUDGET_EXCEEDED":
        gaps.append("Orçamento de execução estourado antes de a análise concluir.")
    if last_decision == "ESCALATED_NOT_ASSESSED":
        gaps.append("A análise não classificou nenhum impacto ou risco.")
    return gaps
