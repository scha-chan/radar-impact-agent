"""Pequenas lacunas de cobertura em `graph/nodes.py` não exercitadas pelos
testes de cenário/integração (card 22): a conversão de `Risk` do state para
`RiskItem` do domínio, e `retrieve_rag` quando `requirement` ainda não foi
extraído."""

from src.domain.risk import Probability, RiskItem, Severity
from src.graph import nodes
from src.graph.state import Risk, create_initial_state


def test_to_risk_item_converts_risk_model_to_domain_risk_item():
    risk = Risk(
        description="usuários sem 2FA cadastrado podem ficar sem acesso",
        severity="HIGH",
        probability="LIKELY",
        mitigation="migração faseada",
    )

    item = nodes._to_risk_item(risk)

    assert item == RiskItem(
        description="usuários sem 2FA cadastrado podem ficar sem acesso",
        severity=Severity.HIGH,
        probability=Probability.LIKELY,
        mitigation="migração faseada",
    )


def test_retrieve_rag_returns_empty_when_requirement_is_not_extracted_yet():
    state = create_initial_state("x")
    assert state["requirement"] is None

    result = nodes.retrieve_rag(state)

    assert result == {"impact_patterns": [], "evidence_sources": []}
