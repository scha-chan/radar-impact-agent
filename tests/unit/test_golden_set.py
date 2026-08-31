"""RF-11.1 (card 39): sanidade do golden set em si — não testa o juiz,
só garante que o dado que alimenta o resto do pipeline de avaliação está
bem formado."""

from src.eval.golden_set import load_golden_set

EXPECTED_SCENARIOS = {"feliz", "risco_alto", "adversarial", "resiliencia"}


def test_golden_set_has_at_least_20_entries():
    assert len(load_golden_set()) >= 20


def test_golden_set_covers_the_four_prd_scenarios():
    scenarios = {entry.scenario for entry in load_golden_set()}
    assert EXPECTED_SCENARIOS <= scenarios


def test_golden_set_entry_ids_are_unique():
    ids = [entry.id for entry in load_golden_set()]
    assert len(ids) == len(set(ids))


def test_golden_set_every_entry_has_both_human_notes():
    for entry in load_golden_set():
        assert set(entry.human_notes) == {"resumo_fiel", "testes_sustentados"}
        assert all(note in (1, 2, 3) for note in entry.human_notes.values())


def test_golden_set_has_quality_variation_not_just_perfect_scores():
    # RF-11.4: um golden set onde tudo é nota 3 não dá sinal real ao
    # Kappa — precisa ter pelo menos uma nota 1 e uma nota 2 em cada
    # critério, não só o caso feliz.
    for criterion in ("resumo_fiel", "testes_sustentados"):
        notes = {entry.human_notes[criterion] for entry in load_golden_set()}
        assert notes == {1, 2, 3}, f"{criterion} não tem variação suficiente: {notes}"
