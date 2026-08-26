"""Utilitários compartilhados entre testes de integração do grafo."""

from __future__ import annotations

import sqlite3
from unittest.mock import MagicMock

from langgraph.checkpoint.sqlite import SqliteSaver

from src.governance.adversarial import AdversarialVerdict
from src.graph import nodes
from src.graph.state import Requirement


def mock_llm(
    monkeypatch,
    *,
    feature_type: str = "outro",
    search_terms: list[str] | None = None,
    requirement_text: str = "x",
    is_adversarial: bool = False,
    adversarial_reason: str = "",
) -> None:
    """Substitui `nodes.build_chat_model` por um duplo que responde de
    forma diferente conforme o schema pedido a `with_structured_output` —
    `extract_requirement` pede `Requirement`, `guard_adversarial` (card 18)
    pede `AdversarialVerdict`. Um `MagicMock` ingênuo único devolveria o
    mesmo valor para os dois nodes, quebrando quem chamasse depois com um
    objeto do tipo errado.
    """
    fake_requirement = Requirement(
        text=requirement_text, feature_type=feature_type, search_terms=search_terms or []
    )
    fake_verdict = AdversarialVerdict(is_adversarial=is_adversarial, reason=adversarial_reason)

    def _with_structured_output(schema, *_args, **_kwargs):
        result = MagicMock()
        if schema is Requirement:
            result.invoke.return_value = fake_requirement
        elif schema is AdversarialVerdict:
            result.invoke.return_value = fake_verdict
        else:
            raise AssertionError(f"schema inesperado em with_structured_output: {schema}")
        return result

    chat_model = MagicMock()
    chat_model.with_structured_output.side_effect = _with_structured_output
    monkeypatch.setattr(nodes, "build_chat_model", lambda **_: chat_model)


# Registro de conexões sqlite abertas por `sqlite_checkpointer` — fechadas no
# teardown por um fixture autouse em `tests/conftest.py`. Achado do card 26
# (análise do log do job "test" da CI): sem isso, cada execução real do
# grafo com checkpointer real deixava um `ResourceWarning: unclosed
# database` nos 46 warnings do relatório do pytest.
_open_sqlite_connections: list[sqlite3.Connection] = []


def sqlite_checkpointer(db_path) -> SqliteSaver:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    _open_sqlite_connections.append(conn)
    return SqliteSaver(conn)


def close_all_sqlite_connections() -> None:
    while _open_sqlite_connections:
        conn = _open_sqlite_connections.pop()
        try:
            conn.close()
        except sqlite3.Error:
            pass
