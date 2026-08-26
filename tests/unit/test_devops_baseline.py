from src.devops.baseline import escalation_rate_by_window


def test_escalation_rate_by_window_computes_rate_per_window():
    flags = [True, True, False, False, False, False, False, False, False, False]
    windows = escalation_rate_by_window(flags, window_size=10)

    assert len(windows) == 1
    assert windows[0].escalation_rate == 0.2
    assert windows[0].is_anomalous is False


def test_escalation_rate_by_window_flags_rate_above_expected_max():
    flags = [True] * 5 + [False] * 5
    windows = escalation_rate_by_window(flags, window_size=10)

    assert windows[0].escalation_rate == 0.5
    assert windows[0].is_anomalous is True


def test_escalation_rate_by_window_flags_rate_below_expected_min():
    flags = [True] + [False] * 9
    windows = escalation_rate_by_window(flags, window_size=10)

    assert windows[0].escalation_rate == 0.1
    assert windows[0].is_anomalous is True


def test_escalation_rate_by_window_splits_into_multiple_windows():
    flags = [True, False] * 25  # 50 execucoes, taxa 50% em cada janela

    windows = escalation_rate_by_window(flags, window_size=10)

    assert len(windows) == 5
    assert windows[0].start_index == 0
    assert windows[0].end_index == 9
    assert windows[-1].start_index == 40
    assert windows[-1].end_index == 49


def test_escalation_rate_by_window_handles_final_partial_window():
    flags = [False] * 25  # nao e multiplo de 10

    windows = escalation_rate_by_window(flags, window_size=10)

    assert len(windows) == 3
    assert windows[-1].start_index == 20
    assert windows[-1].end_index == 24


def test_escalation_rate_by_window_returns_empty_for_empty_input():
    assert escalation_rate_by_window([], window_size=10) == []
