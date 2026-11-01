"""Health evaluation is a pure function of real measurements: no data -> 'unknown', never 'ok'."""
from monitor.health import evaluate

OK = {"status": "ok"}


def snap(**over):
    base = {
        "cpu": {**OK, "percent": 10.0, "cores": 2, "load1": 0.2, "steal_percent": 0.0, "psi_some_avg10": 0.0},
        "memory": {**OK, "percent": 30.0, "swap_total": 6 * 2**30, "swap_percent": 0.0, "psi_some_avg10": 0.0},
        "disks": {**OK, "io_psi_some_avg10": 0.0,
                  "mounts": [{"mount": "/", "percent": 20.0, "inode_percent": 1.0}]},
        "network": OK, "uptime": OK, "system": OK, "interfaces": OK,
    }
    base.update(over)
    return base


def item(h, item_id):
    return next(i for i in h["items"] if i["id"] == item_id)


def test_all_ok():
    h = evaluate(snap())
    assert h["overall"] == "ok"
    assert h["counts"]["crit"] == 0 and h["counts"]["warn"] == 0


def test_cpu_thresholds():
    assert item(evaluate(snap(cpu={**snap()["cpu"], "percent": 80})), "cpu")["level"] == "warn"
    h = evaluate(snap(cpu={**snap()["cpu"], "percent": 95}))
    assert item(h, "cpu")["level"] == "crit" and h["overall"] == "crit"


def test_load_is_normalised_per_core():
    c = {**snap()["cpu"], "load1": 1.9, "cores": 2}      # 0.95 per core -> ok
    assert item(evaluate(snap(cpu=c)), "load")["level"] == "ok"
    c = {**snap()["cpu"], "load1": 4.5, "cores": 2}      # 2.25 per core -> crit
    assert item(evaluate(snap(cpu=c)), "load")["level"] == "crit"


def test_worst_mount_is_reported():
    d = {**snap()["disks"], "mounts": [{"mount": "/", "percent": 20.0, "inode_percent": 1.0},
                                       {"mount": "/data", "percent": 93.0, "inode_percent": 2.0}]}
    it = item(evaluate(snap(disks=d)), "disk")
    assert it["level"] == "crit" and "/data" in it["message"]


def test_missing_metric_is_unknown_not_ok():
    h = evaluate(snap(cpu={"status": "error"}))
    assert item(h, "cpu")["level"] == "unknown"
    assert item(h, "load")["level"] == "unknown"
    assert item(h, "collection")["level"] == "warn"


def test_everything_missing_is_unknown_overall():
    h = evaluate({})
    non_collection = [i for i in h["items"] if i["id"] != "collection"]
    assert all(i["level"] == "unknown" for i in non_collection)


def test_no_swap_is_not_a_problem():
    m = {**snap()["memory"], "swap_total": 0, "swap_percent": 0.0}
    it = item(evaluate(snap(memory=m)), "swap")
    assert it["level"] == "ok" and "No swap" in it["message"]


def test_unsupported_pressure_is_unknown():
    c = {**snap()["cpu"], "psi_some_avg10": None}
    assert item(evaluate(snap(cpu=c)), "psi_cpu")["level"] == "unknown"


def test_stale_data_is_critical():
    h = evaluate(snap(), age_seconds=42, stale=True)
    assert item(h, "collection")["level"] == "crit" and h["overall"] == "crit"


def test_threshold_override():
    h = evaluate(snap(cpu={**snap()["cpu"], "percent": 50}), thresholds={"cpu": (40, 60)})
    assert item(h, "cpu")["level"] == "warn"
