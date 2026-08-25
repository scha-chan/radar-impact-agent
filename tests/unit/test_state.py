from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.graph.state import (
    EvidenceSource,
    Impact,
    ImpactAnalysis,
    Requirement,
    Risk,
    create_initial_state,
)


def test_requirement_accepts_a_known_feature_type():
    req = Requirement(text="Adicionar filtro por data", feature_type="listagem")
    assert req.search_terms == []


def test_requirement_rejects_unknown_feature_type():
    with pytest.raises(ValidationError):
        Requirement(text="x", feature_type="nao-existe")


def test_impact_analysis_rejects_confidence_out_of_range():
    with pytest.raises(ValidationError):
        ImpactAnalysis(
            session_id="abc123",
            issue_number=1,
            requirement_summary="x",
            risk_level="LOW",
            confidence=150,
            human_review_required=False,
            generated_at=datetime.now(timezone.utc),
        )


def test_impact_analysis_accepts_valid_payload():
    analysis = ImpactAnalysis(
        session_id="a3f9c2e1",
        issue_number=42,
        requirement_summary="Adicionar autenticação por 2FA no login",
        risk_level="HIGH",
        confidence=63,
        human_review_required=True,
        impacts=[
            Impact(
                area="authentication",
                description="Fluxo de login ganha uma etapa adicional",
                severity="HIGH",
                evidence="src/auth/login_service.py:41",
            )
        ],
        risks=[
            Risk(
                description="Usuários existentes sem segundo fator podem ficar sem acesso",
                severity="HIGH",
                probability="LIKELY",
                mitigation="Migração faseada com período de tolerância",
            )
        ],
        dependencies=["Provedor de SMS"],
        recommended_tests=["login com 2FA habilitado"],
        evidence_sources=[EvidenceSource(type="code", ref="src/auth/login_service.py")],
        generated_at=datetime.now(timezone.utc),
    )
    assert analysis.risk_level == "HIGH"
    assert analysis.impacts[0].severity == "HIGH"


def test_create_initial_state_defaults():
    state = create_initial_state("Adicionar filtro por data", issue_number=41)

    assert state["session_id"] == state["correlation_id"]
    assert state["issue_number"] == 41
    assert state["raw_requirement"] == "Adicionar filtro por data"
    assert state["requirement"] is None
    assert state["is_adversarial"] is False
    assert state["retries_left"] == 2
    assert state["code_matches"] == []
    assert state["risks"] == []
    assert state["risk_level"] is None
    assert state["human_review_required"] is False
    assert state["analysis"] is None


def test_create_initial_state_generates_distinct_session_ids():
    a = create_initial_state("req a")
    b = create_initial_state("req b")
    assert a["session_id"] != b["session_id"]


def test_create_initial_state_respects_max_retries():
    state = create_initial_state("req", max_retries=5)
    assert state["retries_left"] == 5
