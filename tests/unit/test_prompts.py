"""Card 44 — builder do prompt de `analyze_impact` (`build_analyze_impact_prompt`).

Garante que a evidência coletada entra no prompt com o `file`/`source`/`ref`
citável (RF-04.5) e que os três blocos têm um texto de "nada encontrado"
quando a lista correspondente vem vazia.
"""

from src.graph import prompts
from src.graph.state import CodeMatch, HistoryEntry, PatternChunk, Requirement

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
