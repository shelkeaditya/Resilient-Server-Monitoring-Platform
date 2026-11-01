"""The history buffer backs the charts: it must be bounded, aligned and built from real samples."""
import time

from monitor.collector import HISTORY_KEYS, Sampler


def test_history_matches_collected_samples():
    s = Sampler(interval=1, history_points=50)
    for _ in range(3):
        s.collect_once(); time.sleep(0.2)
    h = s.history()
    assert h["count"] == 3 and len(h["t"]) == 3
    assert set(h["series"]) == set(HISTORY_KEYS)
    assert all(len(col) == 3 for col in h["series"].values())
    assert h["t"] == sorted(h["t"])


def test_history_is_bounded():
    s = Sampler(interval=1, history_points=10)    # 10 is the enforced minimum
    for _ in range(25):
        s.collect_once()
    h = s.history()
    assert h["count"] == 10 and h["max_points"] == 10


def test_history_values_come_from_snapshot():
    s = Sampler(interval=1)
    s.collect_once(); time.sleep(0.3)
    snap = s.collect_once()
    h = s.history()
    assert h["series"]["mem"][-1] == round(snap["memory"]["percent"], 2)
    assert h["series"]["load1"][-1] == round(snap["cpu"]["load1"], 3)
    assert h["t"][-1] == snap["collected_at"]
    assert h["cores"] == snap["cpu"]["cores"]


def test_empty_history_is_valid():
    h = Sampler(interval=1).history()
    assert h["count"] == 0 and all(col == [] for col in h["series"].values())
