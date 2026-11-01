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


def test_bind_mounts_of_one_device_are_reported_once(monkeypatch):
    """/tmp and /var/tmp are usually bind mounts of / - they must not appear as duplicate rows."""
    from collections import namedtuple
    import psutil
    Part = namedtuple("Part", "device mountpoint fstype opts")
    fake = [Part("/dev/vda1", "/", "ext4", ""), Part("/dev/vda1", "/tmp", "ext4", ""),
            Part("/dev/vda1", "/usr", "ext4", ""), Part("/dev/vdb1", "/home", "ext4", "")]
    monkeypatch.setattr(psutil, "disk_partitions", lambda all=False: fake)
    snap = Sampler(interval=1).collect_once()
    mounts = {m["mount"]: m for m in snap["disks"]["mounts"]}
    assert set(mounts) == {"/", "/home"}
    assert mounts["/"]["aliases"] == ["/tmp", "/usr"]
    assert mounts["/home"]["aliases"] == []
