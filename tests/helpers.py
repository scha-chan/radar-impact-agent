"""Utilitários compartilhados entre testes de integração do grafo."""

from __future__ import annotations

from unittest.mock import MagicMock

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
