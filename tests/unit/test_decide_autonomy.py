"""RF-07.4 (card 16): `decide_autonomy` é onde `approval_expires_at` é
gravado — antes da pausa em `human_approval` (`interrupt()` nunca retorna
nada na primeira passada, então não pode ser ele a persistir o prazo).
"""

from datetime import datetime, timedelta, timezone

from src.graph import nodes
from src.graph.state import Impact, Risk, create_initial_state


def _state_with(risk_level: str, confidence: int) -> dict:
    state = create_initial_state("x")
    state["risk_level"] = risk_level
    state["confidence"] = confidence
    return state


def test_decide_autonomy_sets_expiry_when_escalating_by_low_confidence():
    before = datetime.now(timezone.utc)
    result = nodes.decide_autonomy(_state_with("LOW", nodes.CONFIDENCE_THRESHOLD - 1))
    after = datetime.now(timezone.utc)

    assert result["human_review_required"] is True
    expires_at = result["approval_expires_at"]
    assert expires_at is not None
    expected_min = before + timedelta(hours=nodes.APPROVAL_TTL_HOURS)
    expected_max = after + timedelta(hours=nodes.APPROVAL_TTL_HOURS)
    assert expected_min <= expires_at <= expected_max


def test_decide_autonomy_sets_expiry_when_escalating_by_critical_risk():
    result = nodes.decide_autonomy(_state_with("CRITICAL", 100))

    assert result["human_review_required"] is True
    assert result["approval_expires_at"] is not None


def test_decide_autonomy_does_not_set_expiry_when_auto_publishing():
    result = nodes.decide_autonomy(_state_with("LOW", nodes.CONFIDENCE_THRESHOLD))

    assert result["human_review_required"] is False
    assert "approval_expires_at" not in result


def test_decide_autonomy_respects_ttl_env_override(monkeypatch):
    monkeypatch.setattr(nodes, "APPROVAL_TTL_HOURS", 1)

    result = nodes.decide_autonomy(_state_with("LOW", 0))

    delta = result["approval_expires_at"] - datetime.now(timezone.utc)
    assert timedelta(minutes=55) < delta <= timedelta(hours=1)


# --- card 46: risco avaliado vs. não avaliado -------------------------------


def test_not_assessed_when_escalates_without_impacts_or_risks():
    result = nodes.decide_autonomy(_state_with("LOW", 10))

    assert result["risk_assessed"] is False
    assert result["risk_level"] == "MEDIUM"  # piso aplicado


def test_assessed_when_a_risk_was_identified():
    state = _state_with("LOW", 10)
    state["risks"] = [Risk(description="r", severity="LOW", probability="RARE")]

    result = nodes.decide_autonomy(state)

    assert result["risk_assessed"] is True
    assert "risk_level" not in result  # LOW real, não é piso


def test_assessed_when_only_impacts_were_identified():
    state = _state_with("LOW", 10)
    state["impacts"] = [Impact(area="a", description="d", severity="LOW", evidence="x")]

    result = nodes.decide_autonomy(state)

    assert result["risk_assessed"] is True


def test_assessed_when_auto_publishing_with_high_confidence():
    # confiança alta, sem riscos: é um veredito real de "risco baixo",
    # não uma análise que faltou — a tela mostra "Baixo", não "não avaliado".
    result = nodes.decide_autonomy(_state_with("LOW", nodes.CONFIDENCE_THRESHOLD))

    assert result["human_review_required"] is False
    assert result["risk_assessed"] is True


def test_not_assessed_never_downgrades_a_risk_already_elevated():
    result = nodes.decide_autonomy(_state_with("HIGH", 10))

    assert result["risk_assessed"] is True
    assert "risk_level" not in result
