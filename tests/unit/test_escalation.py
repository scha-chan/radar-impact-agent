"""`src/graph/escalation.py` — descrição legível de uma escalação,
compartilhada entre o node `brief_escalation` (card 49) e a API (cards 47/49).
"""

from src.graph.escalation import (
    describe_gaps,
    escalation_reason,
    last_escalation_decision,
)


def test_escalation_reason_maps_known_decisions():
    assert "threshold" in escalation_reason("ESCALATED")
    assert "orçamento" in escalation_reason("ESCALATED_BUDGET_EXCEEDED")
    assert "impactos" in escalation_reason("ESCALATED_NOT_ASSESSED")
    assert escalation_reason(None) == "escalado para revisão humana"


def test_last_escalation_decision_ignores_non_escalation_entries():
    entries = [
        {"decision": "ESCALATED"},
        {"decision": "REANALYSIS_REQUESTED"},
        {"decision": "ESCALATED_NOT_ASSESSED"},
        {"decision": "AUTO_PUBLISHED"},
    ]
    assert last_escalation_decision(entries) == "ESCALATED_NOT_ASSESSED"
    assert last_escalation_decision([{"decision": "BLOCKED_ADVERSARIAL"}]) is None


def test_describe_gaps_lists_missing_evidence_and_decision_specific_gaps():
    gaps = describe_gaps(
        {
            "code_matches": [],
            "impact_patterns": [],
            "change_history": [],
            "tools_failed": ["search_code"],
        },
        "ESCALATED_BUDGET_EXCEEDED",
    )
    assert any("search_code" in g for g in gaps)
    assert any("Orçamento" in g for g in gaps)
    assert any("código" in g for g in gaps)


def test_describe_gaps_is_empty_when_all_evidence_present():
    gaps = describe_gaps(
        {
            "code_matches": [object()],
            "impact_patterns": [object()],
            "change_history": [object()],
            "tools_failed": [],
        },
        "ESCALATED",
    )
    assert gaps == []
