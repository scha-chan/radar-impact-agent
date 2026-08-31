import pytest

from src.devops.baseline import escalation_rate_by_window
from src.devops.dataset import generate_dataset
from src.devops.trend import linear_regression, project_next_window


def test_linear_regression_fits_a_perfect_line():
    slope, intercept = linear_regression([1, 2, 3, 4], [2, 4, 6, 8])
    assert slope == pytest.approx(2.0)
    assert intercept == pytest.approx(0.0)


def test_linear_regression_fits_a_flat_line():
    slope, intercept = linear_regression([1, 2, 3], [5, 5, 5])
    assert slope == pytest.approx(0.0)
    assert intercept == pytest.approx(5.0)


def test_linear_regression_requires_matching_lengths():
    with pytest.raises(ValueError, match="mesmo tamanho"):
        linear_regression([1, 2], [1])


def test_linear_regression_requires_at_least_two_points():
    with pytest.raises(ValueError, match="pelo menos 2 pontos"):
        linear_regression([1], [1])


def test_linear_regression_rejects_constant_xs():
    with pytest.raises(ValueError, match="reta indefinida"):
        linear_regression([1, 1, 1], [1, 2, 3])


def test_project_next_window_matches_manual_calculation():
    # PRD seção 16: as 5 janelas do card 27 (30%, 20%, 40%, 70%, 80%).
    rates = [0.30, 0.20, 0.40, 0.70, 0.80]

    estimate = project_next_window(rates)

    assert estimate.slope == pytest.approx(0.15)
    assert estimate.intercept == pytest.approx(0.03)
    assert estimate.next_window_index == 6
    assert estimate.projection == pytest.approx(0.93)
    assert estimate.alert is True


def test_project_next_window_does_not_alert_when_projection_is_low():
    rates = [0.20, 0.22, 0.21, 0.23, 0.20]

    estimate = project_next_window(rates)

    assert estimate.projection < 0.50
    assert estimate.alert is False


def test_project_next_window_over_the_real_committed_dataset_reproduces_the_alert():
    # Integra com o dataset real do card 27 (nao um exemplo isolado) -
    # garante que a tendencia documentada em tendencia-risco.md continua
    # batendo com o dataset committed se ele mudar.
    rows = generate_dataset()
    flags = [r.human_review_required for r in rows]
    windows = escalation_rate_by_window(flags, window_size=10)
    rates = [w.escalation_rate for w in windows]

    estimate = project_next_window(rates)

    assert estimate.alert is True
    assert estimate.projection > 0.50
