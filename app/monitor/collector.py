"""Real host metrics via psutil and /proc. Nothing is simulated:
anything that cannot be measured is None or a section with status='error'."""
import logging
import os
import platform
import re
import socket
import threading
import time
from collections import deque

import psutil

from .health import evaluate

log = logging.getLogger("monitor.sampler")
SKIP_NIC = ("lo", "docker", "veth", "br-", "cni", "flannel", "cali", "virbr")
SKIP_DISK = ("loop", "ram")
REAL_FS = {"ext4", "xfs", "btrfs", "zfs"}
PARTITION_RE = re.compile(r"^(.*?)(p?\d+)$")

# Series kept in the in-memory history ring buffer (columnar, one value per sample).
HISTORY_KEYS = ("cpu", "mem", "swap", "load1", "load5", "load15",
                "net_rx", "net_tx", "disk_r", "disk_w")


def rate(cur, prev, dt):
    """Per-second rate from two counter readings. None if unknowable or counter reset."""
    if cur is None or prev is None or dt <= 0:
        return None
    d = cur - prev
    return d / dt if d >= 0 else None


def read_psi(name):
    """avg10 'some' pressure from /proc/pressure/<name>, or None if unsupported."""
    try:
        with open(f"/proc/pressure/{name}") as f:
            for line in f:
                if line.startswith("some"):
                    return float(dict(kv.split("=") for kv in line.split()[1:])["avg10"])
    except (OSError, ValueError, KeyError):
        pass
    return None


def _os_pretty_name():
    try:
        with open("/etc/os-release") as f:
            for line in f:
                if line.startswith("PRETTY_NAME="):
                    return line.split("=", 1)[1].strip().strip('"')
    except OSError:
        pass
    return platform.system() or None


def _cpu_model():
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.lower().startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or None


def static_info():
    """Facts that do not change while the process runs."""
    return {
        "hostname": socket.gethostname(),
        "os": _os_pretty_name(),
        "kernel": platform.release(),
        "arch": platform.machine(),
        "cpu_model": _cpu_model(),
        "cores_logical": psutil.cpu_count(),
        "cores_physical": psutil.cpu_count(logical=False),
    }


def _round(v, nd):
    return None if v is None else round(v, nd)


def _history_point(snap):
    def g(sec, key):
        d = snap.get(sec)
        return d.get(key) if isinstance(d, dict) and d.get("status") == "ok" else None

    return {
        "t": snap["collected_at"],
        "cpu": _round(g("cpu", "percent"), 2),
        "mem": _round(g("memory", "percent"), 2),
        "swap": _round(g("memory", "swap_percent"), 2),
        "load1": _round(g("cpu", "load1"), 3),
        "load5": _round(g("cpu", "load5"), 3),
        "load15": _round(g("cpu", "load15"), 3),
        "net_rx": _round(g("network", "rx_bps"), 1),
        "net_tx": _round(g("network", "tx_bps"), 1),
        "disk_r": _round(g("disks", "read_bps"), 1),
        "disk_w": _round(g("disks", "write_bps"), 1),
    }


class Sampler:
    def __init__(self, interval=3.0, history_points=300):
        self.interval = interval
        self.static = static_info()
        self._lock = threading.Lock()
        self._snap = None
        self._hist = deque(maxlen=max(10, int(history_points)))
        self._prev = None  # (monotonic_time, counters)
        self._stop = threading.Event()
        self._thread = None
        psutil.cpu_percent(None)                  # prime: first call returns a meaningless 0.0
        psutil.cpu_percent(None, percpu=True)
        psutil.cpu_times_percent(None)

    # ---- counters used for rate calculations ----
    def _counters(self):
        c = {}
        try:
            nics = psutil.net_io_counters(pernic=True)
            sel = {k: v for k, v in nics.items() if not k.startswith(SKIP_NIC)}
            c["net_rx"] = sum(v.bytes_recv for v in sel.values())
            c["net_tx"] = sum(v.bytes_sent for v in sel.values())
            for name, v in sel.items():
                c[f"nic:{name}:rx"] = v.bytes_recv
                c[f"nic:{name}:tx"] = v.bytes_sent
        except Exception:
            log.exception("net counters")
        try:
            d = psutil.disk_io_counters()
            if d:
                c["disk_r"], c["disk_w"] = d.read_bytes, d.write_bytes
            for name, v in (psutil.disk_io_counters(perdisk=True) or {}).items():
                c[f"dev:{name}:rb"] = v.read_bytes
                c[f"dev:{name}:wb"] = v.write_bytes
                c[f"dev:{name}:rc"] = v.read_count
                c[f"dev:{name}:wc"] = v.write_count
                busy = getattr(v, "busy_time", None)
                if busy is not None:
                    c[f"dev:{name}:busy"] = busy
        except Exception:
            log.exception("disk counters")
        try:
            sw = psutil.swap_memory()
            c["swap_in"], c["swap_out"] = sw.sin, sw.sout
        except Exception:
            log.exception("swap counters")
        return c

    @staticmethod
    def _section(fn):
        try:
            d = fn()
            d["status"] = "ok"
            return d
        except Exception as e:
            log.exception("collector section failed")
            return {"status": "error", "error": type(e).__name__}

    def collect_once(self):
        now = time.monotonic()
        cur = self._counters()
        prev_t, prev = self._prev if self._prev else (now, {})
        dt = now - prev_t
        r = lambda k: rate(cur.get(k), prev.get(k), dt)

        def cpu():
            t = psutil.cpu_times_percent(None)
            l1, l5, l15 = os.getloadavg()
            return {"percent": psutil.cpu_percent(None), "cores": psutil.cpu_count(),
                    "per_core": psutil.cpu_percent(None, percpu=True),
                    "load1": l1, "load5": l5, "load15": l15,
                    "user_percent": getattr(t, "user", None),
                    "system_percent": getattr(t, "system", None),
                    "iowait_percent": getattr(t, "iowait", None),
                    "steal_percent": getattr(t, "steal", None),
                    "psi_some_avg10": read_psi("cpu"), "source": "psutil"}

        def memory():
            vm, sw = psutil.virtual_memory(), psutil.swap_memory()
            return {"total": vm.total, "available": vm.available,
                    "used": vm.total - vm.available,
                    "percent": (vm.total - vm.available) / vm.total * 100,
                    "cached": getattr(vm, "cached", None),
                    "buffers": getattr(vm, "buffers", None),
                    "swap_total": sw.total, "swap_used": sw.used, "swap_percent": sw.percent,
                    "swap_in_bps": r("swap_in"), "swap_out_bps": r("swap_out"),
                    "psi_some_avg10": read_psi("memory"), "source": "psutil"}

        def disks():
            mounts, seen = [], set()
            for p in psutil.disk_partitions(all=False):
                if p.fstype not in REAL_FS or p.mountpoint in seen:
                    continue
                seen.add(p.mountpoint)
                u, st = psutil.disk_usage(p.mountpoint), os.statvfs(p.mountpoint)
                inode_pct = ((st.f_files - st.f_ffree) / st.f_files * 100) if st.f_files else None
                mounts.append({"mount": p.mountpoint, "device": p.device, "fstype": p.fstype,
                               "total": u.total, "used": u.used, "free": u.free,
                               "percent": u.percent, "inode_percent": inode_pct})

            # /tmp and /var/tmp are often bind mounts of the root filesystem: report each device
            # once (shortest mount point) and list the others as aliases instead of duplicate rows.
            by_dev = {}
            for m in mounts:
                cur = by_dev.get(m["device"])
                if cur is None:
                    m["aliases"] = []
                    by_dev[m["device"]] = m
                    continue
                keep, other = (m, cur) if len(m["mount"]) < len(cur["mount"]) else (cur, m)
                keep["aliases"] = sorted(set(keep.get("aliases", [])) | set(other.get("aliases", [])) | {other["mount"]})
                by_dev[m["device"]] = keep
            mounts = sorted(by_dev.values(), key=lambda m: m["mount"])

            counters = psutil.disk_io_counters(perdisk=True) or {}
            names = set(counters)
            devices = []
            for name in sorted(names):
                if name.startswith(SKIP_DISK):
                    continue
                m = PARTITION_RE.match(name)
                if m and m.group(1) in names:  # sda1 / nvme0n1p1: counted under the parent disk
                    continue
                busy_ms = r(f"dev:{name}:busy")
                devices.append({"name": name,
                                "read_bps": r(f"dev:{name}:rb"), "write_bps": r(f"dev:{name}:wb"),
                                "read_iops": r(f"dev:{name}:rc"), "write_iops": r(f"dev:{name}:wc"),
                                "busy_percent": None if busy_ms is None else min(100.0, busy_ms / 10.0)})
            return {"mounts": mounts, "devices": devices,
                    "read_bps": r("disk_r"), "write_bps": r("disk_w"),
                    "io_psi_some_avg10": read_psi("io"), "source": "psutil"}

        def network():
            return {"rx_bps": r("net_rx"), "tx_bps": r("net_tx"),
                    "rx_total": cur.get("net_rx"), "tx_total": cur.get("net_tx"),
                    "source": "psutil"}

        def interfaces():
            stats, addrs = psutil.net_if_stats(), psutil.net_if_addrs()
            io = psutil.net_io_counters(pernic=True)
            out = []
            for name in sorted(stats):
                if name.startswith(SKIP_NIC):
                    continue
                st, c = stats[name], io.get(name)
                out.append({
                    "name": name, "is_up": st.isup, "mtu": st.mtu or None,
                    "speed_mbps": st.speed or None,
                    "ipv4": [a.address for a in addrs.get(name, []) if a.family == socket.AF_INET],
                    "rx_bps": r(f"nic:{name}:rx"), "tx_bps": r(f"nic:{name}:tx"),
                    "rx_total": c.bytes_recv if c else None, "tx_total": c.bytes_sent if c else None,
                    "rx_errors": c.errin if c else None, "tx_errors": c.errout if c else None,
                    "rx_drops": c.dropin if c else None, "tx_drops": c.dropout if c else None})
            return {"interfaces": out, "source": "psutil"}

        def uptime():
            return {"seconds": time.time() - psutil.boot_time(), "source": "psutil.boot_time"}

        def system():
            return {**self.static, "boot_time": psutil.boot_time(), "source": "platform/psutil"}

        snap = {"status": "ok", "collected_at": time.time(), "interval": self.interval,
                "cpu": self._section(cpu), "memory": self._section(memory),
                "disks": self._section(disks), "network": self._section(network),
                "interfaces": self._section(interfaces),
                "uptime": self._section(uptime), "system": self._section(system)}
        self._prev = (now, cur)
        with self._lock:
            self._snap = snap
            self._hist.append(_history_point(snap))
        return snap

    def snapshot(self):
        with self._lock:
            s = self._snap
        if s is None:
            return {"status": "starting"}
        age = time.time() - s["collected_at"]
        stale = age > self.interval * 3
        return {**s, "age_seconds": round(age, 1), "stale": stale,
                "health": evaluate(s, age_seconds=age, stale=stale)}

    def history(self):
        """Columnar history for the dashboard charts (so a page reload keeps its graphs)."""
        with self._lock:
            pts = list(self._hist)
        return {"interval": self.interval, "max_points": self._hist.maxlen, "count": len(pts),
                "cores": self.static.get("cores_logical"),
                "t": [p["t"] for p in pts],
                "series": {k: [p[k] for p in pts] for k in HISTORY_KEYS}}

    def _run(self):
        nxt = time.monotonic()
        while not self._stop.is_set():
            try:
                self.collect_once()
            except Exception:
                log.exception("collect_once failed")
            nxt += self.interval
            now = time.monotonic()
            if nxt < now:  # fell behind (suspended VM, long pause): resync instead of bursting
                nxt = now + self.interval
            self._stop.wait(max(0.0, nxt - now))

    def start(self):
        self._thread = threading.Thread(target=self._run, name="sampler", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
