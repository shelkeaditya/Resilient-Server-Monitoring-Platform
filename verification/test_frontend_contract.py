"""Static checks that the HTML, CSS and JavaScript agree with each other."""
import re
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "app"
HTML = (APP / "templates" / "dashboard.html").read_text()
JS_DIR = APP / "static" / "js"
JS = {p.name: p.read_text() for p in JS_DIR.glob("*.js")}

# Element-id families the JS builds as name + suffix.
CARDS = ("cpu", "memory", "swap", "disk", "load")
DYNAMIC_IDS = (
    [f"card-{c}" for c in CARDS] + [f"{c}-{s}" for c in CARDS for s in ("val", "cap", "foot", "ring", "chip")]
    + [f"psi-{n}{s}" for n in ("cpu", "memory", "io") for s in ("", "-val", "-bar")]
    + [f"cnt-{k}" for k in ("ok", "warn", "crit", "unknown")]
)


def html_ids():
    return set(re.findall(r'\bid="([^"]+)"', HTML))


def test_every_id_used_by_js_exists_in_html():
    used = set()
    for src in JS.values():
        used |= set(re.findall(r"""(?:\btext|\bel)\(\s*'([\w-]+)'(?!\s*\+)""", src))
        used |= set(re.findall(r"""getElementById\(\s*'([\w-]+)'(?!\s*\+)""", src))
    used |= set(DYNAMIC_IDS)
    missing = sorted(used - html_ids())
    assert not missing, f"ids used by JS but missing from dashboard.html: {missing}"


def test_every_chart_has_a_canvas_and_a_legend_slot():
    ids = re.findall(r"id:\s*'(chart-[\w-]+)'", JS["charts.js"])
    assert len(ids) == 5
    for cid in ids:
        assert f'id="{cid}"' in HTML, cid
        assert f'data-legend-for="{cid}"' in HTML, cid


def test_every_asset_referenced_by_the_template_exists():
    files = re.findall(r"filename='([^']+)'", HTML)
    assert len(files) >= 8
    for f in files:
        assert (APP / "static" / f).is_file(), f


def test_every_icon_used_in_html_is_defined():
    defined = set(re.findall(r'<symbol id="(i-[\w-]+)"', HTML))
    used = set(re.findall(r'href="#(i-[\w-]+)"', HTML)) | set(re.findall(r"'#(i-[\w-]+)'", JS["ui.js"]))
    assert not (used - defined), sorted(used - defined)


def test_frontend_never_writes_markup():
    for name, src in JS.items():
        assert "innerHTML" not in src, f"{name} uses innerHTML"
        assert "insertAdjacentHTML" not in src, f"{name} uses insertAdjacentHTML"
        assert "document.write" not in src, name


def test_no_inline_event_handlers_or_scripts():
    assert not re.search(r"\son[a-z]+\s*=", HTML), "inline event handler found"
    assert "<script>" not in HTML, "inline script found"
