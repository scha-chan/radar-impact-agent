"""RF-11.5 (card 39): detecção de mudança de versão e diff contra o
baseline salvo — o mecanismo, não a chamada real ao juiz (que exige
Ollama, indisponível em CI)."""

from src.eval.regression import (
    EvalVersionFingerprint,
    diff_against_baseline,
    load_baseline,
    needs_rerun,
    save_baseline,
)


def test_load_baseline_returns_none_when_file_does_not_exist(tmp_path):
    assert load_baseline(tmp_path / "does-not-exist.json") is None


def test_save_and_load_baseline_roundtrip(tmp_path):
    path = tmp_path / "eval-baseline.json"
    fingerprint = EvalVersionFingerprint(
        prompt_version="1", policy_version="1", llm_model="mistral"
    )
    save_baseline(path, fingerprint, {"resumo_fiel_kappa": 0.8})

    loaded = load_baseline(path)

    assert loaded["fingerprint"] == {
        "prompt_version": "1",
        "policy_version": "1",
        "llm_model": "mistral",
    }
    assert loaded["result_by_layer"] == {"resumo_fiel_kappa": 0.8}


def test_needs_rerun_is_true_without_a_baseline():
    fingerprint = EvalVersionFingerprint(
        prompt_version="1", policy_version="1", llm_model="mistral"
    )
    assert needs_rerun(None, fingerprint) is True


def test_needs_rerun_is_false_when_fingerprint_is_unchanged(tmp_path):
    path = tmp_path / "eval-baseline.json"
    fingerprint = EvalVersionFingerprint(
        prompt_version="1", policy_version="1", llm_model="mistral"
    )
    save_baseline(path, fingerprint, {})

    assert needs_rerun(load_baseline(path), fingerprint) is False


def test_needs_rerun_is_true_when_llm_model_changed(tmp_path):
    path = tmp_path / "eval-baseline.json"
    save_baseline(
        path,
        EvalVersionFingerprint(prompt_version="1", policy_version="1", llm_model="mistral"),
        {},
    )

    new_fingerprint = EvalVersionFingerprint(
        prompt_version="1", policy_version="1", llm_model="gemma4:12b"
    )
    assert needs_rerun(load_baseline(path), new_fingerprint) is True


def test_diff_against_baseline_reports_new_baseline_when_none_exists():
    assert diff_against_baseline(None, {"x": 1}) == {"new_baseline": True}


def test_diff_against_baseline_is_empty_when_nothing_changed():
    baseline = {"result_by_layer": {"resumo_fiel_kappa": 0.8}}
    assert diff_against_baseline(baseline, {"resumo_fiel_kappa": 0.8}) == {}


def test_diff_against_baseline_reports_only_changed_layers():
    baseline = {"result_by_layer": {"resumo_fiel_kappa": 0.8, "testes_sustentados_kappa": 0.6}}
    current = {"resumo_fiel_kappa": 0.5, "testes_sustentados_kappa": 0.6}

    diff = diff_against_baseline(baseline, current)

    assert diff == {"resumo_fiel_kappa": {"previous": 0.8, "current": 0.5}}


def test_eval_version_fingerprint_current_reads_from_config():
    fingerprint = EvalVersionFingerprint.current()
    assert fingerprint.prompt_version
    assert fingerprint.policy_version
    assert fingerprint.llm_model
