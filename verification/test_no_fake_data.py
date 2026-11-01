"""Guard: the frontend must never contain simulated data."""
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "app"


def test_no_math_random_in_frontend():
    checked = 0
    for p in APP.rglob("*"):
        if p.suffix in {".js", ".html"} and "vendor" not in p.parts:
            checked += 1
            assert "Math.random" not in p.read_text(), f"fake data in {p}"
    assert checked >= 2  # dashboard.html and dashboard.js must have been scanned


def test_no_hardcoded_fake_constants():
    html = (APP / "templates" / "dashboard.html").read_text()
    for bad in ("LOG_POOL", "ap-south-1", "TOTAL_PODS", "of 16 GB", "4 cores"):
        assert bad not in html, f"hardcoded fake value: {bad}"
