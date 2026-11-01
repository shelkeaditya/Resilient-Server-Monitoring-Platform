from monitor.collector import rate


def test_basic_rate():
    assert rate(2000, 1000, 2.0) == 500


def test_counter_reset_returns_none():
    assert rate(10, 1000, 1.0) is None


def test_first_sample_returns_none():
    assert rate(10, None, 1.0) is None


def test_zero_elapsed_returns_none():
    assert rate(10, 5, 0) is None


def test_missing_current_returns_none():
    assert rate(None, 5, 1.0) is None
