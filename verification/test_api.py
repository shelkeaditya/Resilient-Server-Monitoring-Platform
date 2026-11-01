import re
import time
from pathlib import Path

import pytest

from app import create_app

REQUIRED_SECTIONS = ("cpu", "memory", "disks", "network", "uptime", "system", "interfaces")
HTML = (Path(__file__).resolve().parent.parent / "app" / "templates" / "dashboard.html").read_text()


@pytest.fixture(scope="module")
def client():
    app = create_app()
    c = app.test_client()
    for _ in range(40):  # wait up to ~4s for first sample
        if c.get("/api/v1/snapshot").get_json().get("status") == "ok":
            break
        time.sleep(0.1)
    yield c
    app.extensions["sampler"].stop()


def test_snapshot_contract(client):
    s = client.get("/api/v1/snapshot").get_json()
    assert s["status"] == "ok"
    assert abs(time.time() - s["collected_at"]) < 10
    for sec in REQUIRED_SECTIONS:
        assert s[sec]["status"] in ("ok", "error")
        if s[sec]["status"] == "ok":
            assert "source" in s[sec]


def test_snapshot_keeps_the_original_fields(client):
    """Fields the first dashboard version relied on must still exist."""
    s = client.get("/api/v1/snapshot").get_json()
    assert {"percent", "cores", "load1", "steal_percent"} <= set(s["cpu"])
    assert {"total", "available", "swap_total", "swap_percent"} <= set(s["memory"])
    assert {"mounts", "read_bps", "write_bps"} <= set(s["disks"])
    assert {"rx_bps", "tx_bps"} <= set(s["network"])
    assert "seconds" in s["uptime"]
    assert {"age_seconds", "stale"} <= set(s)


def test_new_sections_have_real_data(client):
    s = client.get("/api/v1/snapshot").get_json()
    import socket, platform
    assert s["system"]["hostname"] == socket.gethostname()
    assert s["system"]["arch"] == platform.machine()
    assert isinstance(s["interfaces"]["interfaces"], list)
    assert isinstance(s["cpu"]["per_core"], list) and len(s["cpu"]["per_core"]) == s["cpu"]["cores"]


def test_health_block(client):
    h = client.get("/api/v1/snapshot").get_json()["health"]
    assert h["overall"] in ("ok", "warn", "crit", "unknown")
    assert sum(h["counts"].values()) == len(h["items"])
    assert {"cpu", "memory", "swap", "disk", "load", "collection"} <= {i["id"] for i in h["items"]}


def test_history_endpoint(client):
    h = client.get("/api/v1/history").get_json()
    assert h["count"] == len(h["t"]) >= 1
    assert all(len(col) == h["count"] for col in h["series"].values())


def test_healthz_ok_when_fresh(client):
    r = client.get("/healthz")
    assert r.status_code == 200 and r.get_json() == {"ok": True}


def test_security_headers(client):
    r = client.get("/")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    csp = r.headers["Content-Security-Policy"]
    assert "default-src 'self'" in csp and "frame-ancestors 'none'" in csp
    assert "unsafe-eval" not in csp and "script-src" not in csp  # scripts only from 'self'


def test_json_is_never_cached(client):
    assert client.get("/api/v1/snapshot").headers["Cache-Control"] == "no-store"
    assert client.get("/api/v1/history").headers["Cache-Control"] == "no-store"


def test_old_data_endpoint_removed(client):
    assert client.get("/data").status_code == 404


def test_dashboard_and_every_asset_are_served(client):
    page = client.get("/")
    assert page.status_code == 200
    urls = re.findall(r'(?:href|src)="(/static/[^"]+)"', page.get_data(as_text=True))
    assert len(urls) >= 8
    for u in urls:
        r = client.get(u)
        assert r.status_code == 200, u
