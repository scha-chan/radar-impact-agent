"""`ToolExecutor` — RF-08.2 generalizado a todas as tools do RADAR (seção 13
do PRD, card 17).

`authorize()` (cards 10/11) só protegia `publish_comment`, chamada
diretamente dentro da própria tool. O `ToolExecutor` centraliza a mesma
garantia para qualquer tool, a partir de um único ponto no grafo (os nodes
em `graph/nodes.py`): nenhuma chamada acontece sem uma `ToolPermission`
registrada — "chamada não autorizada é recusada" deixa de depender de cada
tool se lembrar de chamar `authorize()` sozinha.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TypeVar

from src.governance.permissions import PermissionDeniedError, ToolPermission, authorize
from src.graph.state import AgentState

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ToolExecutor:
    """Registro de `ToolPermission` por nome de tool + ponto único de
    validação antes de qualquer chamada."""

    def __init__(self) -> None:
        self._registry: dict[str, ToolPermission] = {}

    def register(self, permission: ToolPermission) -> None:
        self._registry[permission.name] = permission

    def execute(self, tool_name: str, state: AgentState, call: Callable[[], T]) -> T:
        """Recusa a chamada (`PermissionDeniedError`, `call` nunca é
        invocado) se `tool_name` não tiver `ToolPermission` registrada.
        Caso tenha, valida `authorize()` (RF-08.3) antes de executar.
        """
        permission = self._registry.get(tool_name)
        if permission is None:
            logger.error(
                "tool_call_refused_unregistered",
                extra={"tool": tool_name, "session_id": state["session_id"]},
            )
            raise PermissionDeniedError(f"{tool_name}: nenhuma permissão declarada — chamada recusada")

        authorize(permission, state)
        logger.info(
            "tool_authorized",
            extra={
                "tool": tool_name,
                "permission": permission.permission,
                "session_id": state["session_id"],
            },
        )
        return call()
