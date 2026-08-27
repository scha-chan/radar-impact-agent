"""Utilitários compartilhados entre testes de integração do grafo."""

from __future__ import annotations

import sqlite3
from unittest.mock import MagicMock

from langgraph.checkpoint.sqlite import SqliteSaver

from src.governance.adversarial import AdversarialVerdict
from src.graph import nodes
from src.graph.state import (
    ComposedReport,
    Impact,
    ImpactAnalysisResult,
    Requirement,
    Risk,
)


def mock_llm(
    monkeypatch,
    *,
    feature_type: str = "outro",
    search_terms: list[str] | None = None,
    requirement_text: str = "x",
    is_adversarial: bool = False,
    adversarial_reason: str = "",
    impacts: list[Impact] | None = None,
    risks: list[Risk] | None = None,
    dependencies: list[str] | None = None,
    recommended_tests: list[str] | None = None,
    requirement_summary: str | None = None,
    executive_summary: str = "Resumo executivo de teste.",
) -> None:
    """Substitui `nodes.build_chat_model` por um duplo que responde de
    forma diferente conforme o schema pedido a `with_structured_output` —
    `extract_requirement` pede `Requirement`, `guard_adversarial` (card 18)
    pede `AdversarialVerdict`, `analyze_impact` (card 44) pede
    `ImpactAnalysisResult`, `compose_report` (card 45) pede `ComposedReport`.
    Um `MagicMock` ingênuo único devolveria o mesmo valor para todos,
    quebrando quem chamasse depois com um objeto do tipo errado.

    `impacts`/`risks`/`dependencies`/`recommended_tests` fixam a saída de
    `analyze_impact` (default: listas vazias — o node real roda, só não
    produz nada, preservando o comportamento que os testes anteriores
    esperavam do stub). `requirement_summary`/`executive_summary` fixam a
    saída de `compose_report`.
    """
    fake_requirement = Requirement(
        text=requirement_text, feature_type=feature_type, search_terms=search_terms or []
    )
    fake_verdict = AdversarialVerdict(is_adversarial=is_adversarial, reason=adversarial_reason)
    fake_analysis = ImpactAnalysisResult(
        impacts=impacts or [],
        risks=risks or [],
        dependencies=dependencies or [],
        recommended_tests=recommended_tests or [],
    )
    fake_report = ComposedReport(
        requirement_summary=requirement_summary
        if requirement_summary is not None
        else requirement_text,
        executive_summary=executive_summary,
    )

    def _with_structured_output(schema, *_args, **_kwargs):
        result = MagicMock()
        if schema is Requirement:
            result.invoke.return_value = fake_requirement
        elif schema is AdversarialVerdict:
            result.invoke.return_value = fake_verdict
        elif schema is ImpactAnalysisResult:
            result.invoke.return_value = fake_analysis
        elif schema is ComposedReport:
            result.invoke.return_value = fake_report
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
