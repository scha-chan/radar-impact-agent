"""Permissões de tool — RF-08.2, seção 13 do PRD.

Escopo deste card: só o necessário para proteger `publish_comment`, a
primeira ação irreversível do RADAR. O card 17 generaliza isto para
todas as tools (recusar chamada sem permissão declarada, trilha de
auditoria completa via `src/observability`, card 20).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from src.graph.state import AgentState


@dataclass(frozen=True)
class ToolPermission:
    name: str
    permission: str
    destructive: bool
    requires_approval_when: Callable[[AgentState], bool] | None = None


class PermissionDeniedError(Exception):
    """Levantada quando uma tool destrutiva é chamada sem autorização (RF-08.2/RF-08.3)."""


def authorize(tool: ToolPermission, state: AgentState) -> None:
    """RF-08.3: uma tool destrutiva cujo `requires_approval_when(state)` é
    verdadeiro só pode ser chamada com `approval_decision == "APPROVED"`.
    Levanta `PermissionDeniedError` caso contrário — a tool nunca executa
    a ação sem essa checagem passar.
    """
    if not tool.destructive or tool.requires_approval_when is None:
        return
    if not tool.requires_approval_when(state):
        return
    if state.get("approval_decision") != "APPROVED":
        raise PermissionDeniedError(
            f"{tool.name}: ação destrutiva requer aprovação humana explícita "
            f"(human_review_required=True, approval_decision={state.get('approval_decision')!r})"
        )
