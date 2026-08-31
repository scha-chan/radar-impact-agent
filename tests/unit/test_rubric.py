"""RF-11.3 (card 39): contrato do juiz LLM por critério."""

from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from src.eval.rubric import Veredito, build_judge_prompt, judge


def test_veredito_accepts_a_valid_payload():
    v = Veredito(
        criterio="resumo_fiel", evidencia="o resumo bate com o texto", nota=3, confianca=90
    )
    assert v.nota == 3
    assert v.abstencao is False


def test_veredito_rejects_a_note_outside_1_to_3():
    with pytest.raises(ValidationError):
        Veredito(criterio="resumo_fiel", evidencia="x", nota=4, confianca=50)


def test_veredito_field_order_puts_evidencia_before_nota():
    # RF-11.3: "evidência é campo obrigatório e precede a nota" — trava a
    # ordem dos campos no schema, não só que ambos existem.
    fields = list(Veredito.model_fields)
    assert fields.index("evidencia") < fields.index("nota")


def test_build_judge_prompt_includes_requirement_summary_and_tests():
    prompt = build_judge_prompt(
        "resumo_fiel",
        raw_requirement="Adicionar filtro de data",
        requirement_summary="Filtro de data na listagem",
        recommended_tests=["filtrar por data válida", "filtrar por data inválida"],
    )
    assert "Adicionar filtro de data" in prompt
    assert "Filtro de data na listagem" in prompt
    assert "filtrar por data válida" in prompt


def test_build_judge_prompt_handles_no_recommended_tests():
    prompt = build_judge_prompt(
        "testes_sustentados",
        raw_requirement="x",
        requirement_summary="y",
        recommended_tests=[],
    )
    assert "nenhum teste recomendado" in prompt


def test_build_judge_prompt_marks_content_as_data_not_instruction():
    prompt = build_judge_prompt(
        "resumo_fiel", raw_requirement="x", requirement_summary="y", recommended_tests=[]
    )
    assert "DADO a ser avaliado" in prompt


def test_judge_invokes_the_llm_with_structured_output(monkeypatch):
    fake_veredito = Veredito(
        criterio="resumo_fiel", evidencia="bate com o original", nota=3, confianca=80
    )
    chat_model = MagicMock()
    chat_model.with_structured_output.return_value.invoke.return_value = fake_veredito
    monkeypatch.setattr("src.graph.llm.build_chat_model", lambda **_: chat_model)

    result = judge(
        "resumo_fiel",
        raw_requirement="x",
        requirement_summary="y",
        recommended_tests=["t1"],
    )

    assert result == fake_veredito
    chat_model.with_structured_output.assert_called_once_with(Veredito)
