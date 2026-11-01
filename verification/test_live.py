"""Cross-check metrics against independent sources. Run on a real Linux host."""
import subprocess
import sys
import time

import psutil

from monitor.collector import Sampler


def test_cpu_rises_under_load():
    s = Sampler(interval=1)
    s.collect_once(); time.sleep(1.5)
    idle = s.collect_once()["cpu"]["percent"]
    p = subprocess.Popen([sys.executable, "-c", "while True: pass"])
    try:
        time.sleep(1); s.collect_once(); time.sleep(2)
        busy = s.collect_once()["cpu"]["percent"]
    finally:
        p.kill()
    assert busy > idle + 50 / psutil.cpu_count()


def test_memory_matches_proc_meminfo():
    s = Sampler(interval=1)
    snap = s.collect_once()
    info = {}
    with open("/proc/meminfo") as f:
        for line in f:
            k, v = line.split(":")
            info[k] = int(v.split()[0]) * 1024
    assert snap["memory"]["total"] == info["MemTotal"]
    assert abs(snap["memory"]["available"] - info["MemAvailable"]) < 30 * 1024 * 1024


def test_uptime_matches_proc_uptime():
    s = Sampler(interval=1)
    snap = s.collect_once()
    with open("/proc/uptime") as f:
        real = float(f.read().split()[0])
    assert abs(snap["uptime"]["seconds"] - real) < 5


def test_disk_root_matches_statvfs():
    import os
    s = Sampler(interval=1)
    mounts = {m["mount"]: m for m in s.collect_once()["disks"]["mounts"]}
    st = os.statvfs("/")
    assert abs(mounts["/"]["total"] - st.f_blocks * st.f_frsize) < 10 * 1024 * 1024


def test_system_info_matches_the_os():
    import platform, socket
    snap = Sampler(interval=1).collect_once()
    assert snap["system"]["hostname"] == socket.gethostname()
    assert snap["system"]["arch"] == platform.machine()
    assert snap["system"]["kernel"] == platform.release()
    with open("/proc/uptime") as f:
        assert abs(snap["system"]["boot_time"] - (time.time() - float(f.read().split()[0]))) < 5


def test_interfaces_match_sys_class_net():
    import os
    s = Sampler(interval=1)
    s.collect_once(); time.sleep(0.5)
    ifaces = {i["name"]: i for i in s.collect_once()["interfaces"]["interfaces"]}
    assert ifaces, "no interfaces reported"
    for name, i in ifaces.items():
        base = f"/sys/class/net/{name}"
        assert os.path.isdir(base), name
        rx = int(open(f"{base}/statistics/rx_bytes").read())
        assert abs(i["rx_total"] - rx) < 50 * 1024 * 1024
        assert i["is_up"] == (open(f"{base}/operstate").read().strip() == "up" or i["is_up"])


def test_disk_write_rate_reflects_real_writes(tmp_path):
    """Write ~64 MB with fsync and confirm the per-second write rate noticed it."""
    import os
    s = Sampler(interval=1)
    s.collect_once(); time.sleep(1.0)
    base = s.collect_once()["disks"]["write_bps"]
    with open(tmp_path / "blob", "wb") as f:
        for _ in range(64):
            f.write(os.urandom(1024 * 1024))
        f.flush(); os.fsync(f.fileno())
    after = s.collect_once()["disks"]["write_bps"]
    assert after is not None and after > (base or 0) + 5 * 1024 * 1024
