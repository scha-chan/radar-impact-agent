"""Cenário 2 do PRD (seção 12) — Risco alto com escalação.

Entrada: "Adicionar autenticação por 2FA no login." Igual ao cenário 1
(`test_scenario_1_happy_path.py`), roda o grafo real de ponta a ponta com
as tools de evidência mockadas — a diferença aqui é que `analyze_impact`
(o LLM que classifica impactos/riscos, ainda stub no código, card 14 do
LLM) também é mockado, fixado no exemplo do PRD: um risco HIGH/LIKELY (com
mitigação) que empurra `risk_level` para HIGH. Isso não é possível apenas
com as tools de evidência, porque `analyze_impact` real ainda não existe.

A confiança calculada aqui (65) não é o `63` do exemplo narrativo do PRD —
esse número na seção 12 é ilustrativo, não uma saída travada da fórmula
(seção 11). O que a fórmula real produz a partir da evidência mockada é
determinístico e documentado dedução por dedução abaixo; o que importa
para o cenário é ficar abaixo do threshold (70), o que acontece.
"""

from langgraph.types import Command

from src.graph import nodes
from src.graph.build import build_graph
from src.graph.state import PatternChunk, Requirement, Risk, create_initial_state
from src.observability.audit import read_audit_trail
from tests.helpers import mock_llm, sqlite_checkpointer

REQUIREMENT_TEXT = (
    "Adicionar autenticação por 2FA (segundo fator) no login para aumentar "
    "a segurança de acesso dos usuários existentes."
)


def _mock_evidence_and_analysis(monkeypatch):
    mock_llm(
        monkeypatch,
        feature_type="login",
        search_terms=["2FA", "login", "autenticacao"],
        requirement_text=REQUIREMENT_TEXT,
    )

    # Nenhum código encontrado (a integração com o provedor de SMS ainda
    # não existe no repositório hipotético) — RF-03.1, dedução de -25.
    monkeypatch.setattr(nodes, "search_code", lambda *_a, **_k: [])

    # RAG encontra o padrão real de 2FA do corpus (knowledge/login.md,
    # card 12) — RF-03.2, sem dedução.
    monkeypatch.setattr(
        nodes,
        "retrieve_patterns",
        lambda *_a, **_k: [
            PatternChunk(
                content="Segundo fator de autenticação (2FA/MFA): usuários existentes sem "
                "segundo fator cadastrado podem ficar bloqueados.",
                source="knowledge/login.md#segundo-fator-de-autenticacao-2famfa",
                similarity=0.9,
            )
        ],
    )

    # Nenhum histórico relevante encontrado — RF-03.3.
    monkeypatch.setattr(nodes, "_fetch_history", lambda *_a, **_k: [])

    # analyze_impact real (LLM, card 14 do LLM) ainda é stub — fixado aqui
    # no exemplo do cenário 2 (seção 12 do PRD): um risco HIGH/LIKELY, com
    # mitigação proposta.
    monkeypatch.setattr(
        nodes,
        "analyze_impact",
        lambda _state: {
            "impacts": [],
            "risks": [
                Risk(
                    description=(
                        "Usuários existentes sem segundo fator cadastrado podem ficar sem acesso"
                    ),
                    severity="HIGH",
                    probability="LIKELY",
                    mitigation="Migração faseada com período de tolerância",
                )
            ],
            "dependencies": ["Provedor de SMS", "Serviço de sessão"],
            "recommended_tests": [
                "login com 2FA habilitado",
                "recuperação de conta com 2FA perdido",
                "migração de usuário existente",
            ],
        },
    )


def test_scenario_2_high_risk_escalates_and_pauses(tmp_path, monkeypatch):
    _mock_evidence_and_analysis(monkeypatch)
    graph = build_graph(checkpointer=sqlite_checkpointer(tmp_path / "checkpoints.db"))
    state = create_initial_state(REQUIREMENT_TEXT)
    config = {"configurable": {"thread_id": state["session_id"]}}

    result = graph.invoke(state, config=config)

    assert result["requirement"] == Requirement(
        text=REQUIREMENT_TEXT, feature_type="login", search_terms=["2FA", "login", "autenticacao"]
    )
    assert result["risk_level"] == "HIGH"
    # Dedução real: -25 (nenhum código encontrado) -10 (só uma fonte de
    # evidência distinta, o padrão RAG) = 100 - 35 = 65. Abaixo do
    # threshold padrão (70) -> escala (RF-06.2).
    assert result["confidence"] == 65
    assert result["human_review_required"] is True
    assert "__interrupt__" in result
    assert result["published_comment_url"] is None

    entries = read_audit_trail(result["session_id"])
    assert [e["decision"] for e in entries] == ["ESCALATED"]
    assert entries[0]["risk_level"] == "HIGH"
    assert entries[0]["confidence"] == 65
    assert entries[0]["threshold"] == 70


def test_scenario_2_approval_resumes_and_publishes_with_human_review_stamp(tmp_path, monkeypatch):
    _mock_evidence_and_analysis(monkeypatch)
    monkeypatch.chdir(tmp_path)
    graph = build_graph(checkpointer=sqlite_checkpointer(tmp_path / "checkpoints.db"))
    state = create_initial_state(REQUIREMENT_TEXT)
    config = {"configurable": {"thread_id": state["session_id"]}}
    graph.invoke(state, config=config)

    result = graph.invoke(Command(resume="APPROVED"), config=config)

    assert result["approval_decision"] == "APPROVED"
    assert result["published_comment_url"] is not None
    assert result["published_comment_url"].startswith("file://")

    published_path = result["published_comment_url"].removeprefix("file://")
    with open(published_path, encoding="utf-8") as f:
        body = f.read()
    # "Carimbo de revisão humana" (seção 12 do PRD): a composição definitiva
    # do comentário a partir de `ImpactAnalysis` é o card 14 do LLM
    # (pendente); render_comment (card 10) já marca a revisão humana.
    assert "Revisão humana necessária:** sim" in body
    assert "HIGH" in body

    entries = read_audit_trail(result["session_id"])
    assert [e["decision"] for e in entries] == ["ESCALATED", "APPROVED_PUBLISHED"]
    assert entries[-1]["actor"] == "human"
    assert entries[-1]["tool_authorized"] == "publish_comment"


def test_scenario_2_rejection_resumes_and_archives_without_publishing(tmp_path, monkeypatch):
    _mock_evidence_and_analysis(monkeypatch)
    graph = build_graph(checkpointer=sqlite_checkpointer(tmp_path / "checkpoints.db"))
    state = create_initial_state(REQUIREMENT_TEXT)
    config = {"configurable": {"thread_id": state["session_id"]}}
    graph.invoke(state, config=config)

    result = graph.invoke(Command(resume="REJECTED"), config=config)

    assert result["approval_decision"] == "REJECTED"
    assert result["published_comment_url"] is None

    entries = read_audit_trail(result["session_id"])
    assert [e["decision"] for e in entries] == ["ESCALATED", "REJECTED_ARCHIVED"]
