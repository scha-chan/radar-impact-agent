"""Fábrica do checkpointer do LangGraph (RF-07.1, card 15).

`human_approval` suspende a execução com `interrupt()`; o checkpointer é o
que preserva o `AgentState` entre essa pausa e a retomada com a decisão
humana (RF-07.2) — inclusive entre reinícios do processo, já que é
`SqliteSaver` sobre um arquivo em disco (seção 7 do PRD), não em memória.
"""

from __future__ import annotations

import os
import sqlite3

from langgraph.checkpoint.sqlite import SqliteSaver

from src import config  # noqa: F401 - carrega .env como efeito colateral do import

CHECKPOINT_DB_PATH = os.getenv("CHECKPOINT_DB_PATH", "radar_checkpoints.db")


def build_checkpointer(db_path: str | None = None) -> SqliteSaver:
    """`check_same_thread=False`: a submissão do requisito (que pausa em
    `human_approval`) e a decisão de aprovação (RF-07.2, `POST
    /approvals/{session_id}`) chegam em requisições — logo threads —
    diferentes do servidor FastAPI; a mesma conexão precisa responder por
    ambas."""
    conn = sqlite3.connect(db_path or CHECKPOINT_DB_PATH, check_same_thread=False)
    return SqliteSaver(conn)
