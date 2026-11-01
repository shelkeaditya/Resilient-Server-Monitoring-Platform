"""Health evaluation for the monitoring dashboard.

A pure function: it takes a collector snapshot and returns ok/warn/crit levels
per indicator plus an overall level. It never invents data. An indicator whose
underlying metric is unavailable is reported as "unknown" and is ignored when
the overall level is computed.

Thresholds are (warn, crit) pairs and apply as ">= value".
"""

DEFAULT_THRESHOLDS = {
    "cpu": (75.0, 90.0),            # % CPU busy
    "memory": (80.0, 90.0),         # % of RAM in use (excludes reclaimable cache)
    "swap": (30.0, 60.0),           # % of swap in use
    "disk": (80.0, 90.0),           # % of the fullest filesystem
    "inode": (80.0, 90.0),          # % of inodes on the fullest filesystem
    "load_per_core": (1.0, 2.0),    # 1-minute load average divided by vCPUs
    "psi": (10.0, 25.0),            # % of time tasks stalled (10 s average)
    "steal": (10.0, 25.0),          # % of CPU time stolen by the hypervisor
}

# Sections the collector is expected to deliver on every sample.
EXPECTED_SECTIONS = ("cpu", "memory", "disks", "network", "uptime", "system", "interfaces")

_RANK = {"unknown": -1, "ok": 0, "warn": 1, "crit": 2}


def _level(value, warn, crit):
    if value is None:
        return "unknown"
    if value >= crit:
        return "crit"
    if value >= warn:
        return "warn"
    return "ok"


def _section(snap, name):
    sec = snap.get(name)
    return sec if isinstance(sec, dict) and sec.get("status") == "ok" else None


def _item(item_id, label, level, value=None, unit=None, message="", threshold=None):
    return {"id": item_id, "label": label, "level": level, "value": value,
            "unit": unit, "message": message, "threshold": list(threshold) if threshold else None}


def _pct_item(item_id, label, value, th, message):
    level = _level(value, *th)
    return _item(item_id, label, level, value, "%", message if value is not None else "Unavailable", th)


def evaluate(snap, thresholds=None, age_seconds=None, stale=False):
    """Return {"overall", "counts", "items"} for a collector snapshot."""
    th = dict(DEFAULT_THRESHOLDS)
    if thresholds:
        th.update(thresholds)
    items = []

    cpu = _section(snap, "cpu")
    mem = _section(snap, "memory")
    disks = _section(snap, "disks")

    # --- CPU -----------------------------------------------------------------
    v = cpu["percent"] if cpu else None
    items.append(_pct_item("cpu", "CPU usage", v, th["cpu"],
                           "%.0f%% of capacity" % v if v is not None else ""))

    steal = cpu.get("steal_percent") if cpu else None
    items.append(_pct_item("steal", "CPU steal", steal, th["steal"],
                           "%.1f%% taken by the hypervisor" % steal if steal is not None else ""))

    cores = cpu.get("cores") if cpu else None
    if cpu and cores:
        per_core = cpu["load1"] / cores
        items.append(_item("load", "System load", _level(per_core, *th["load_per_core"]),
                           round(per_core, 3), "per core",
                           "%.2f per core (1 min, %d vCPU)" % (per_core, cores), th["load_per_core"]))
    else:
        items.append(_item("load", "System load", "unknown", message="Unavailable"))

    # --- Memory and swap -----------------------------------------------------
    v = mem["percent"] if mem else None
    items.append(_pct_item("memory", "Memory usage", v, th["memory"],
                           "%.0f%% of RAM in use" % v if v is not None else ""))

    if mem and mem.get("swap_total", 0) == 0:
        items.append(_item("swap", "Swap usage", "ok", None, "%", "No swap configured", th["swap"]))
    else:
        v = mem["swap_percent"] if mem else None
        items.append(_pct_item("swap", "Swap usage", v, th["swap"],
                               "%.1f%% of swap in use" % v if v is not None else ""))

    # --- Disk ----------------------------------------------------------------
    mounts = disks.get("mounts", []) if disks else []
    if mounts:
        worst = max(mounts, key=lambda m: m["percent"])
        items.append(_pct_item("disk", "Disk usage", worst["percent"], th["disk"],
                               "%s is %.0f%% full" % (worst["mount"], worst["percent"])))
        with_inodes = [m for m in mounts if m.get("inode_percent") is not None]
        if with_inodes:
            wi = max(with_inodes, key=lambda m: m["inode_percent"])
            items.append(_pct_item("inode", "Inode usage", wi["inode_percent"], th["inode"],
                                   "%s uses %.1f%% of inodes" % (wi["mount"], wi["inode_percent"])))
        else:
            items.append(_item("inode", "Inode usage", "unknown", message="Unavailable"))
    else:
        items.append(_item("disk", "Disk usage", "unknown", message="No filesystems reported"))
        items.append(_item("inode", "Inode usage", "unknown", message="Unavailable"))

    # --- Resource pressure (kernel PSI, not available on every kernel) -------
    pressure = (
        ("psi_cpu", "CPU pressure", cpu.get("psi_some_avg10") if cpu else None),
        ("psi_memory", "Memory pressure", mem.get("psi_some_avg10") if mem else None),
        ("psi_io", "I/O pressure", disks.get("io_psi_some_avg10") if disks else None),
    )
    for item_id, label, v in pressure:
        items.append(_pct_item(item_id, label, v, th["psi"],
                               "Tasks stalled %.1f%% of the time (10 s)" % v if v is not None
                               else "Not supported by this kernel"))

    # --- Collection status ---------------------------------------------------
    failed = [n for n in EXPECTED_SECTIONS if n in snap and not _section(snap, n)]
    ok_count = len([n for n in EXPECTED_SECTIONS if _section(snap, n)])
    if stale:
        level, msg = "crit", "No new sample for %.0f s" % (age_seconds or 0)
    elif failed:
        level, msg = "warn", "Collector failed: " + ", ".join(failed)
    else:
        level, msg = "ok", "%d of %d collectors reporting" % (ok_count, len(EXPECTED_SECTIONS))
    items.append(_item("collection", "Collection", level, ok_count, "collectors", msg))

    known = [i["level"] for i in items if i["level"] != "unknown"]
    overall = max(known, key=lambda lv: _RANK[lv]) if known else "unknown"
    counts = {lv: sum(1 for i in items if i["level"] == lv) for lv in ("ok", "warn", "crit", "unknown")}
    return {"overall": overall, "counts": counts, "items": items}
