"""Card 44 — `analyze_impact` real (RF-04).

O node chama o LLM com saída estruturada (`ImpactAnalysisResult`) a partir
da evidência coletada, aplica a rastreabilidade da RF-04.5 (impacto sem
evidência que aponte uma fonte coletada é descartado) e degrada para
listas vazias se a chamada falhar. A chamada ao modelo é sempre dublada.
"""

from unittest.mock import MagicMock

from src.graph import nodes
from src.graph.state import (
    CodeMatch,
    EvidenceSource,
    Impact,
    ImpactAnalysisResult,
    PatternChunk,
    Requirement,
    Risk,
    create_initial_state,
)


def _fake_structured_llm(*, invoke_side_effect):
    chat_model = MagicMock()
    structured = MagicMock()
    structured.invoke.side_effect = invoke_side_effect
    chat_model.with_structured_output.return_value = structured
    return chat_model


def _state_with_evidence(**overrides):
    state = create_initial_state("Adicionar autenticação por 2FA no login dos usuários existentes")
    state["requirement"] = Requirement(
        text=state["raw_requirement"], feature_type="login", search_terms=["2fa", "login"]
    )
    state["code_matches"] = [
        CodeMatch(file="src/auth/login_service.py", snippet="def login(...):", line=41)
    ]
    state["impact_patterns"] = [
        PatternChunk(
            content="2FA quebra recuperação de senha",
            source="knowledge/login.md#2fa",
            similarity=0.9,
        )
    ]
    state["change_history"] = []
    state["evidence_sources"] = [
        EvidenceSource(type="code", ref="src/auth/login_service.py"),
        EvidenceSource(type="rag", ref="knowledge/login.md#2fa"),
    ]
    state.update(overrides)
    return state


def test_analyze_impact_maps_llm_output_to_state(monkeypatch):
    analysis = ImpactAnalysisResult(
        impacts=[
            Impact(
                area="autenticacao",
                description="Login ganha uma etapa",
                severity="HIGH",
                evidence="src/auth/login_service.py:41",
            )
        ],
        risks=[
            Risk(description="Usuários sem 2FA travados", severity="HIGH", probability="LIKELY")
        ],
        dependencies=["Provedor de SMS"],
        recommended_tests=["login com 2FA habilitado"],
    )
    chat_model = _fake_structured_llm(invoke_side_effect=[analysis])
    monkeypatch.setattr(nodes, "build_chat_model", lambda **_: chat_model)

    result = nodes.analyze_impact(_state_with_evidence())

    assert [i.area for i in result["impacts"]] == ["autenticacao"]
    assert [r.severity for r in result["risks"]] == ["HIGH"]
    assert result["dependencies"] == ["Provedor de SMS"]
    assert result["recommended_tests"] == ["login com 2FA habilitado"]


def test_analyze_impact_passes_collected_evidence_into_prompt(monkeypatch):
    chat_model = _fake_structured_llm(invoke_side_effect=[ImpactAnalysisResult()])
    monkeypatch.setattr(nodes, "build_chat_model", lambda **_: chat_model)

    nodes.analyze_impact(_state_with_evidence())

    prompt = chat_model.with_structured_output.return_value.invoke.call_args[0][0]
    assert "src/auth/login_service.py:41" in prompt
    assert "knowledge/login.md#2fa" in prompt
    assert "login" in prompt  # feature_type


def test_analyze_impact_drops_impacts_without_grounded_evidence(monkeypatch):
    analysis = ImpactAnalysisResult(
        impacts=[
            Impact(
                area="a",
                description="tem evidência",
                severity="MEDIUM",
                evidence="src/auth/login_service.py",
            ),
            Impact(area="b", description="inventado", severity="CRITICAL", evidence=""),
            Impact(
                area="c",
                description="fonte inexistente",
                severity="HIGH",
                evidence="src/outro/coisa.py",
            ),
        ]
    )
    chat_model = _fake_structured_llm(invoke_side_effect=[analysis])
    monkeypatch.setattr(nodes, "build_chat_model", lambda **_: chat_model)

    result = nodes.analyze_impact(_state_with_evidence())

    assert [i.area for i in result["impacts"]] == ["a"]


def test_analyze_impact_returns_empty_when_no_evidence_was_collected(monkeypatch):
    chat_model = _fake_structured_llm(invoke_side_effect=[ImpactAnalysisResult(impacts=[])])
    monkeypatch.setattr(nodes, "build_chat_model", lambda **_: chat_model)

    state = _state_with_evidence(evidence_sources=[])
    result = nodes.analyze_impact(state)

    assert result == {"impacts": [], "risks": [], "dependencies": [], "recommended_tests": []}
    # sem evidência não há o que analisar — o modelo nem é chamado.
    chat_model.with_structured_output.return_value.invoke.assert_not_called()


def test_analyze_impact_degrades_to_empty_on_llm_failure(monkeypatch):
    chat_model = _fake_structured_llm(invoke_side_effect=RuntimeError("ollama fora do ar"))
    monkeypatch.setattr(nodes, "build_chat_model", lambda **_: chat_model)

    result = nodes.analyze_impact(_state_with_evidence())

    assert result == {"impacts": [], "risks": [], "dependencies": [], "recommended_tests": []}


def test_analyze_impact_returns_empty_when_requirement_missing(monkeypatch):
    called = MagicMock()
    monkeypatch.setattr(nodes, "build_chat_model", called)

    state = _state_with_evidence(requirement=None)
    result = nodes.analyze_impact(state)

    assert result == {"impacts": [], "risks": [], "dependencies": [], "recommended_tests": []}
    called.assert_not_called()
