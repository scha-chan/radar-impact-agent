from src.devops.baseline import escalation_rate_by_window
from src.devops.dataset import (
    NORMAL_PHASE_EXECUTIONS,
    TOTAL_EXECUTIONS,
    generate_dataset,
    read_csv,
    write_csv,
)


def test_generate_dataset_produces_exactly_50_rows():
    rows = generate_dataset()
    assert len(rows) == TOTAL_EXECUTIONS == 50


def test_generate_dataset_is_deterministic_for_the_same_seed():
    first = generate_dataset(seed=7)
    second = generate_dataset(seed=7)
    assert first == second


def test_generate_dataset_differs_across_seeds():
    assert generate_dataset(seed=1) != generate_dataset(seed=2)


def test_generate_dataset_confidence_comes_from_the_real_formula():
    # Todo confidence deve estar no intervalo valido de calculate_confidence
    # (piso 0, teto 100) - nao e um numero solto fora da formula real.
    rows = generate_dataset()
    assert all(0 <= r.confidence <= 100 for r in rows)


def test_generate_dataset_human_review_matches_confidence_threshold():
    rows = generate_dataset()
    for row in rows:
        assert row.human_review_required == (row.confidence < 70)


def test_generate_dataset_reproduces_the_documented_anomaly():
    # A metodologia (docstring de dataset.py) declara: as ultimas execucoes
    # (fase degradada) devem ter taxa de escalacao visivelmente mais alta
    # que as primeiras (fase normal) - e o proprio cenario que o baseline
    # (card 27) precisa detectar. Falha aqui significa que a simulacao
    # parou de bater com o que a documentacao afirma.
    rows = generate_dataset()
    flags = [r.human_review_required for r in rows]

    normal_phase = flags[:NORMAL_PHASE_EXECUTIONS]
    degraded_phase = flags[NORMAL_PHASE_EXECUTIONS:]
    normal_rate = sum(normal_phase) / len(normal_phase)
    degraded_rate = sum(degraded_phase) / len(degraded_phase)

    assert degraded_rate > 0.40
    assert normal_rate < degraded_rate

    windows = escalation_rate_by_window(flags, window_size=10)
    assert any(w.is_anomalous and w.escalation_rate > 0.40 for w in windows[-2:])


def test_write_csv_then_read_csv_round_trips(tmp_path):
    path = tmp_path / "dataset.csv"
    rows = generate_dataset(seed=99)

    write_csv(rows, path)
    loaded = read_csv(path)

    assert loaded == rows


def test_write_csv_creates_parent_directory(tmp_path):
    path = tmp_path / "nested" / "dir" / "dataset.csv"

    write_csv(generate_dataset(), path)

    assert path.exists()
