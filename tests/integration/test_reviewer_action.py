"""Card 47 — ação do revisor na escalação: reanálise com contexto.

Em vez de só aprovar/rejeitar, o revisor manda `Command(resume={"action":
"REANALYZE", "context": ...})`. O grafo injeta o contexto como evidência,
incrementa `review_rounds`, reexecuta `analyze_impact` e volta a pausar
(ou publica, se a reanálise deu confiança suficiente).
"""

from langgraph.types import Command

from src.graph import nodes
from src.graph.build import build_graph
from src.graph.state import Risk, create_initial_state
from src.observability.audit import read_audit_trail
from tests.helpers import mock_llm, sqlite_checkpointer

REQUIREMENT = "Adicionar autenticação por 2FA no login dos usuários existentes."
CONTEXT = (
    "A integração de SMS já existe em src/notif/sms.py e o fluxo de recuperação "
    "de conta em src/auth/recovery.py usa o mesmo provedor."
)


def _graph(tmp_path):
    return build_graph(checkpointer=sqlite_checkpointer(tmp_path / "cp.db"))


def _no_evidence(monkeypatch):
    """Isola a coleta: sem isso os testes dependem de `GITHUB_TOKEN` do
    `.env` e de o `chroma/` local estar vazio."""
    monkeypatch.setattr(nodes, "search_code", lambda *_a, **_k: [])
    monkeypatch.setattr(nodes, "_fetch_history", lambda *_a, **_k: [])
    monkeypatch.setattr(nodes, "retrieve_patterns", lambda *_a, **_k: [])


def test_reanalyze_with_context_reruns_analysis_and_repauses(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _no_evidence(monkeypatch)
    # Na reanálise o LLM classifica um risco a partir do contexto do revisor.
    mock_llm(
        monkeypatch,
        feature_type="login",
        search_terms=["2fa"],
        requirement_text=REQUIREMENT,
        risks=[
            Risk(
                description="usuários sem 2FA podem ficar bloqueados",
                severity="HIGH",
                probability="LIKELY",
                mitigation="migração faseada",
            )
        ],
    )
    graph = _graph(tmp_path)
    state = create_initial_state(REQUIREMENT)
    cfg = {"configurable": {"thread_id": state["session_id"]}}

    first = graph.invoke(state, cfg)
    assert "__interrupt__" in first  # escalou sem evidência (card 46)

    resumed = graph.invoke(Command(resume={"action": "REANALYZE", "context": CONTEXT}), cfg)

    assert resumed["review_rounds"] == 1
    assert CONTEXT in resumed["reviewer_context"]
    assert any(e.type == "reviewer" for e in resumed["evidence_sources"])
    # a reanálise produziu um risco -> risco avaliado, HIGH
    assert resumed["risk_level"] == "HIGH"
    assert resumed["risk_assessed"] is True
    assert "__interrupt__" in resumed  # confiança ainda baixa -> repausa

    decisions = [e["decision"] for e in read_audit_trail(resumed["session_id"])]
    assert decisions == ["ESCALATED_NOT_ASSESSED", "REANALYSIS_REQUESTED", "ESCALATED"]

    final = graph.invoke(Command(resume="APPROVED"), cfg)
    assert final["published_comment_url"].startswith("file://")
    assert read_audit_trail(final["session_id"])[-1]["decision"] == "APPROVED_PUBLISHED"


def test_reanalyze_without_context_still_counts_the_round(tmp_path, monkeypatch):
    _no_evidence(monkeypatch)
    mock_llm(monkeypatch, feature_type="outro", search_terms=[])
    graph = _graph(tmp_path)
    state = create_initial_state(REQUIREMENT)
    cfg = {"configurable": {"thread_id": state["session_id"]}}
    graph.invoke(state, cfg)

    resumed = graph.invoke(Command(resume={"action": "REANALYZE", "context": None}), cfg)

    assert resumed["review_rounds"] == 1
    assert resumed["reviewer_context"] == []
    # sem contexto, nenhuma fonte nova -> segue não avaliado
    assert resumed["risk_assessed"] is False
    assert "__interrupt__" in resumed
    entries = read_audit_trail(resumed["session_id"])
    assert [e["decision"] for e in entries][:2] == [
        "ESCALATED_NOT_ASSESSED",
        "REANALYSIS_REQUESTED",
    ]
    assert entries[1]["reason"] == "reanálise sem contexto adicional"


def test_reviewer_context_reaches_the_analyze_impact_prompt(tmp_path, monkeypatch):
    seen: dict[str, str] = {}
    real_build = nodes.prompts.build_analyze_impact_prompt

    def _spy(*args, **kwargs):
        prompt = real_build(*args, **kwargs)
        seen["prompt"] = prompt
        return prompt

    monkeypatch.setattr(nodes.prompts, "build_analyze_impact_prompt", _spy)
    _no_evidence(monkeypatch)
    mock_llm(monkeypatch, feature_type="login", search_terms=["2fa"], requirement_text=REQUIREMENT)
    graph = _graph(tmp_path)
    state = create_initial_state(REQUIREMENT)
    cfg = {"configurable": {"thread_id": state["session_id"]}}
    graph.invoke(state, cfg)

    graph.invoke(Command(resume={"action": "REANALYZE", "context": CONTEXT}), cfg)

    assert "contexto adicional do revisor" in seen["prompt"].lower()
    assert CONTEXT in seen["prompt"]
