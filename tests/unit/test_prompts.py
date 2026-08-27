"""Card 44 — builder do prompt de `analyze_impact` (`build_analyze_impact_prompt`).

Garante que a evidência coletada entra no prompt com o `file`/`source`/`ref`
citável (RF-04.5) e que os três blocos têm um texto de "nada encontrado"
quando a lista correspondente vem vazia.
"""

from datetime import datetime, timezone

from src.graph import prompts
from src.graph.state import (
    CodeMatch,
    EvidenceSource,
    HistoryEntry,
    Impact,
    ImpactAnalysis,
    PatternChunk,
    Requirement,
    Risk,
)

REQUIREMENT = Requirement(text="Adicionar 2FA no login", feature_type="login", search_terms=["2fa"])


def test_prompt_includes_every_piece_of_evidence():
    text = prompts.build_analyze_impact_prompt(
        REQUIREMENT,
        [CodeMatch(file="src/auth/login.py", snippet="def login():", line=10)],
        [
            PatternChunk(
                content="2FA quebra recuperação", source="knowledge/login.md#2fa", similarity=0.8
            )
        ],
        [HistoryEntry(type="pr", ref="PR #7", description="mexeu no login")],
    )

    assert "src/auth/login.py:10" in text
    assert "knowledge/login.md#2fa" in text
    assert "PR #7" in text
    assert "login" in text  # feature_type
    assert REQUIREMENT.text in text


def test_prompt_marks_missing_evidence_blocks():
    text = prompts.build_analyze_impact_prompt(REQUIREMENT, [], [], [])

    assert "(nenhum trecho de código encontrado)" in text
    assert "(nenhum padrão de impacto recuperado)" in text
    assert "(nenhum commit ou PR relacionado)" in text


def test_prompt_handles_code_match_without_line_number():
    text = prompts.build_analyze_impact_prompt(
        REQUIREMENT,
        [CodeMatch(file="src/auth/login.py", snippet="x")],
        [],
        [],
    )

    assert "src/auth/login.py —" in text
    assert "src/auth/login.py:" not in text


# --- card 45: build_compose_report_prompt -------------------------------------


def _analysis(**overrides) -> ImpactAnalysis:
    base = dict(
        session_id="s1",
        issue_number=1,
        requirement_summary="Adicionar 2FA no login",
        risk_level="HIGH",
        confidence=65,
        human_review_required=True,
        impacts=[
            Impact(area="auth", description="login muda", severity="HIGH", evidence="src/auth.py")
        ],
        risks=[Risk(description="usuários travados", severity="HIGH", probability="LIKELY")],
        dependencies=["Provedor de SMS"],
        recommended_tests=["login com 2FA"],
        evidence_sources=[EvidenceSource(type="code", ref="src/auth.py")],
        generated_at=datetime.now(timezone.utc),
    )
    base.update(overrides)
    return ImpactAnalysis(**base)


def test_compose_prompt_carries_the_structured_analysis():
    text = prompts.build_compose_report_prompt(_analysis())

    assert "Nível de risco: HIGH" in text
    assert "Confiança: 65/100" in text
    assert "Revisão humana necessária: sim" in text
    assert "auth: login muda" in text
    assert "usuários travados" in text
    assert "Provedor de SMS" in text
    assert "login com 2FA" in text
    # instrução de não contradizer a decisão
    assert "não os altera" in text or "nunca decidir" in text


def test_compose_prompt_handles_empty_analysis():
    text = prompts.build_compose_report_prompt(
        _analysis(impacts=[], risks=[], dependencies=[], recommended_tests=[])
    )

    assert "Impactos:\n  (nenhum)" in text
    assert "Riscos:\n  (nenhum)" in text
    assert "Dependências externas: (nenhuma)" in text
    assert "Testes recomendados:\n  (nenhum)" in text
