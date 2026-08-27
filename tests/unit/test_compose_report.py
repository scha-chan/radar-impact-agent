"""Card 45 — composição do parecer final (`_compose_report`, `render_comment`).

O `ImpactAnalysis` é montado deterministicamente a partir do state; só o
texto (resumo do requisito + resumo executivo) passa pelo LLM, e uma
falha da chamada cai em texto de fallback sem impedir a publicação.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock

from src.graph import nodes
from src.graph.state import (
    ComposedReport,
    EvidenceSource,
    Impact,
    ImpactAnalysis,
    Requirement,
    Risk,
    create_initial_state,
)
from src.mcp_server.tools.publish_comment import render_comment


def _fake_structured_llm(*, invoke_side_effect):
    chat_model = MagicMock()
    structured = MagicMock()
    structured.invoke.side_effect = invoke_side_effect
    chat_model.with_structured_output.return_value = structured
    return chat_model


def _analysed_state(**overrides):
    state = create_initial_state("Adicionar filtro por intervalo de data na listagem de pedidos")
    state["requirement"] = Requirement(
        text=state["raw_requirement"], feature_type="listagem", search_terms=["pedidos"]
    )
    state["risk_level"] = "MEDIUM"
    state["confidence"] = 72
    state["human_review_required"] = False
    state["impacts"] = [
        Impact(
            area="listagem",
            description="query ganha um filtro",
            severity="MEDIUM",
            evidence="src/orders/repo.py",
        )
    ]
    state["risks"] = [
        Risk(
            description="filtro sem índice degrada a query",
            severity="MEDIUM",
            probability="POSSIBLE",
            mitigation="criar índice composto",
        )
    ]
    state["dependencies"] = ["Índice de banco"]
    state["recommended_tests"] = ["listagem com intervalo amplo"]
    state["evidence_sources"] = [EvidenceSource(type="code", ref="src/orders/repo.py")]
    state.update(overrides)
    return state


def test_compose_report_uses_llm_text_and_keeps_structured_fields(monkeypatch):
    composed = ComposedReport(
        requirement_summary="Filtrar a listagem de pedidos por intervalo de data",
        executive_summary="Mudança de risco médio. Recomenda-se criar índice antes de liberar.",
    )
    monkeypatch.setattr(
        nodes, "build_chat_model", lambda **_: _fake_structured_llm(invoke_side_effect=[composed])
    )

    analysis, prose = nodes._compose_report(_analysed_state())

    assert analysis.requirement_summary == "Filtrar a listagem de pedidos por intervalo de data"
    assert prose.startswith("Mudança de risco médio")
    # campos estruturados vêm do state, não do LLM
    assert analysis.risk_level == "MEDIUM"
    assert analysis.confidence == 72
    assert [i.area for i in analysis.impacts] == ["listagem"]
    assert analysis.session_id == _analysed_state()["session_id"] or analysis.session_id


def test_compose_report_falls_back_to_deterministic_text_on_llm_failure(monkeypatch):
    monkeypatch.setattr(
        nodes,
        "build_chat_model",
        lambda **_: _fake_structured_llm(invoke_side_effect=RuntimeError("ollama down")),
    )

    analysis, prose = nodes._compose_report(_analysed_state())

    assert analysis.requirement_summary.startswith("Adicionar filtro por intervalo de data")
    assert "risco MEDIUM" in prose and "72/100" in prose
    assert "1 impacto(s)" in prose and "1 risco(s)" in prose


def test_compose_report_defensive_defaults_when_scoring_was_skipped(monkeypatch):
    monkeypatch.setattr(
        nodes,
        "build_chat_model",
        lambda **_: _fake_structured_llm(invoke_side_effect=RuntimeError("x")),
    )
    state = _analysed_state(risk_level=None, confidence=None, impacts=[], risks=[])

    analysis, _ = nodes._compose_report(state)

    assert analysis.risk_level == "LOW"
    assert analysis.confidence == 0


def test_compose_report_blank_llm_strings_fall_back(monkeypatch):
    composed = ComposedReport(requirement_summary="   ", executive_summary="")
    monkeypatch.setattr(
        nodes, "build_chat_model", lambda **_: _fake_structured_llm(invoke_side_effect=[composed])
    )

    analysis, prose = nodes._compose_report(_analysed_state())

    assert analysis.requirement_summary.startswith("Adicionar filtro")
    assert "risco MEDIUM" in prose


def _analysis(**overrides) -> ImpactAnalysis:
    base = dict(
        session_id="sess1234",
        issue_number=7,
        requirement_summary="Resumo do requisito",
        risk_level="HIGH",
        confidence=65,
        human_review_required=True,
        impacts=[
            Impact(
                area="auth", description="login muda", severity="HIGH", evidence="src/auth.py:10"
            )
        ],
        risks=[
            Risk(
                description="usuários travados",
                severity="HIGH",
                probability="LIKELY",
                mitigation="migração faseada",
            )
        ],
        dependencies=["Provedor de SMS"],
        recommended_tests=["login com 2FA"],
        evidence_sources=[EvidenceSource(type="rag", ref="knowledge/login.md#2fa")],
        generated_at=datetime.now(timezone.utc),
    )
    base.update(overrides)
    return ImpactAnalysis(**base)


def test_render_comment_full_report_has_every_section():
    state = create_initial_state("x")
    body = render_comment(state, analysis=_analysis(), prose="Resumo executivo.")

    assert "Resumo executivo." in body
    assert "**Requisito:** Resumo do requisito" in body
    assert "**Nível de risco:** HIGH" in body
    assert "**Revisão humana necessária:** sim" in body
    assert "- **auth** (HIGH): login muda — _evidência: src/auth.py:10_" in body
    assert "- (HIGH/LIKELY) usuários travados" in body
    assert "Mitigação: migração faseada" in body
    assert "- Provedor de SMS" in body
    assert "- login com 2FA" in body
    assert "- [rag] knowledge/login.md#2fa" in body
    assert "_session_id: sess1234_" in body


def test_render_comment_full_report_marks_empty_sections():
    state = create_initial_state("x")
    body = render_comment(
        state,
        analysis=_analysis(
            impacts=[], risks=[], dependencies=[], recommended_tests=[], evidence_sources=[]
        ),
        prose=None,
    )

    assert "_Nenhum impacto identificado._" in body
    assert "_Nenhum risco identificado._" in body
    assert "_Nenhuma dependência externa identificada._" in body
    assert "_Nenhum teste recomendado._" in body
    assert "_Sem evidência coletada._" in body


def test_render_comment_without_analysis_keeps_minimal_body():
    state = _analysed_state()
    body = render_comment(state)

    assert "### Impactos" not in body
    assert "**Nível de risco:** MEDIUM" in body
    assert state["session_id"] in body


def test_render_comment_marks_risk_as_not_assessed():
    # card 46: parecer escalou sem avaliação -> o comentário não afirma
    # "risco MEDIUM", diz que não foi avaliado (piso aplicado).
    state = create_initial_state("x")
    body = render_comment(
        state,
        analysis=_analysis(risk_level="MEDIUM", risk_assessed=False),
        prose=None,
    )

    assert "não avaliado — evidência insuficiente (piso MEDIUM aplicado)" in body
    assert "**Nível de risco:** MEDIUM\n" not in body
