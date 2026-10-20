#!/usr/bin/env python3
"""M20 r2 rendered probe (Grok self-validation, not independent review). ONE Chrome launch for the whole run, using
G20's guarded Browser class (refuses a second launch, closes in finally, watchdog kills only its own pid). In that
one session it runs (a) my own rows with labels and ids chosen for this pass and (b) the builder's own per-width rows
(browser_checks.one_width) so they are reproduced without a second launch.
Usage: PY m20r2_browser_probe.py REPO CHROME OUTDIR"""
import json, sys, tempfile, shutil, time
from pathlib import Path
REPO = Path(sys.argv[1]).resolve(); CHROME = sys.argv[2]; OUT = Path(sys.argv[3]); OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(REPO / "examples/capabilities/G20")); import browser_checks as bc
CORE = REPO / "employees/engineering/frontend-developer/async_search_core.js"
CJK = "\u6771\u4eac\u6e7e\u5cb8\u5009\u5eab" * 30
EMO = "\U0001f69a" * 80
URL = "https://example.invalid/" + "segment/" * 25
MINE = [{"id": "   ", "label": "Blank id row"}, {"id": "", "label": "Empty id row"}, {"id": "1abc", "label": "Digit first"},
        {"id": "a:b", "label": "Colon id"}, {"id": "a.b", "label": "Dot id"}, {"id": "a#b", "label": "Hash id"},
        {"id": "a b", "label": "Space id"}, {"id": "a_b", "label": "Underscore id"}, {"id": "a-b", "label": "Dash id"}, {"id": "a  b", "label": "Two spaces id"},
        {"id": "cjk", "label": CJK}, {"id": "emoji", "label": EMO}, {"id": "url", "label": URL}]
OLD = [{"id": "o1", "label": "Stale one"}]
ROWS = []
def row(rid, ok, desc, detail): ROWS.append({"id": rid, "pass": bool(ok), "desc": desc, "detail": detail}); print("%s %s %s %s" % (rid, "PASS" if ok else "FAIL", desc, json.dumps(detail, default=str)[:260]))
def mine(b, url, w):
    b.cmd("Emulation.setDeviceMetricsOverride", width=w, height=800, deviceScaleFactor=1, mobile=False)
    b.cmd("Page.navigate", url=url)
    b.wait("document.readyState === 'complete' && !!window.SolarisAsyncSearch && document.activeElement === document.body")
    b.key("Tab"); b.type("mz"); b.wait("window.__g20.pending.some(function (p) { return p.q === 'mz'; })")
    b.js("window.__g20.settle('mz', %s)" % json.dumps(MINE)); b.wait("document.querySelectorAll('#results [role=option]').length > 0")
    g = b.js(bc.GEOM); n = len(g["opts"])
    over = [o["id"] for o in g["opts"] if o["sw"] > o["cw"] + 0.5 or o["right"] > g["listRight"] + 0.5]
    row("M-L1-%d" % w, g["docSW"] <= g["docCW"] and g["listRight"] <= g["inner"] and not over,
        "CJK, emoji and URL-like unbroken labels: no page overflow, every option inside the list and viewport", {"n": n, "docSW": g["docSW"], "docCW": g["docCW"], "over": over})
    p = b.cmd("Page.captureScreenshot", format="png")["data"]; import base64; (OUT / ("m20r2-%d.png" % w)).write_bytes(base64.b64decode(p))
    ids = []; ok = True
    for i in range(n):
        b.key("ArrowDown"); s = b.js(bc.STATE); ids.append(s["ad"])
        ok = ok and s["focus"] == "q" and bool(bc.VALID_ID.match(s["ad"] or "")) and s["adResolves"] and s["adSelector"]
    row("M-K1-%d" % w, ok and len(set(ids)) == n == len(MINE), "13 rows with blank, empty, digit-first, punctuated and colliding ids: each active id valid, resolving, unique; focus stays on input", ids)
    b.key("Home"); b.key("ArrowUp"); s = b.js(bc.STATE)
    row("M-K2-%d" % w, s["selected"] == [URL], "ArrowUp from the first option wraps to the last", s["selected"][:1])
    b.key("Escape"); b.key("Escape")
    b.type("p"); b.wait("window.__g20.pending.some(function (p) { return p.q === 'p'; })")
    b.type("q"); b.wait("window.__g20.pending.some(function (p) { return p.q === 'pq'; })")
    b.js("window.__g20.settle('pq', [])"); time.sleep(0.2); s0 = b.js(bc.STATE)
    b.js("window.__g20.settle('p', %s)" % json.dumps(OLD)); time.sleep(0.25); s1 = b.js(bc.STATE)
    row("M-S1-%d" % w, s1["labels"] == s0["labels"] and "Stale" not in json.dumps(s1) and s1["status"] == s0["status"],
        "newer query answered with no rows, then the older query answers: the empty result stays", {"before": s0["status"], "after": s1["status"], "labels": s1["labels"]})
    b.key("Escape"); b.key("Escape")
    b.type("r"); b.wait("window.__g20.pending.some(function (p) { return p.q === 'r'; })")
    b.type("s"); b.wait("window.__g20.pending.some(function (p) { return p.q === 'rs'; })")
    b.js("window.__g20.settle('rs', %s)" % json.dumps(MINE[:3])); b.wait("document.querySelectorAll('#results [role=option]').length === 3"); s0 = b.js(bc.STATE)
    b.js("window.__g20.settle('r', null, 'old 500')"); time.sleep(0.25); s1 = b.js(bc.STATE)
    row("M-S2-%d" % w, not s1["err"] and s1["labels"] == s0["labels"], "an older query failing after the newer one succeeded shows no error and keeps the rows", {"err": s1["err"], "labels": len(s1["labels"])})
tmp = tempfile.mkdtemp(prefix="m20r2-page-"); b = None; version = None; builder = []
try:
    b = bc.Browser(CHROME, 200.0)
    version = b.cmd("Browser.getVersion").get("product")
    b.cmd("Page.enable"); b.cmd("Runtime.enable"); b.cmd("Network.enable"); b.cmd("Page.addScriptToEvaluateOnNewDocument", source=bc.HOOK)
    url = bc.page_copy(CORE, tmp)
    for w in (320, 360, 1280):
        try: mine(b, url, w)
        except Exception as ex:
            row("M-E-%d" % w, False, "run error (no relaunch)", "%s: %s" % (type(ex).__name__, ex))
            if b.proc.poll() is not None: raise
    for w in (320, 360, 1280):
        bc.one_width(b, url, w, builder, {}, None)
except Exception as ex:
    row("E-run", False, "run error (no relaunch)", "%s: %s" % (type(ex).__name__, ex))
finally:
    pid = b.proc.pid if b is not None else None
    if b is not None: b.close()
    shutil.rmtree(tmp, ignore_errors=True)
alive = None
if pid:
    import os
    try: os.kill(pid, 0); alive = True
    except OSError: alive = False
bp = sum(r["pass"] for r in builder)
json.dump({"chrome": version, "launches": bc.LAUNCHES, "chrome_pid_alive_after_close": alive, "rows": ROWS, "builder_rows": builder}, open(OUT / "m20r2-browser.json", "w"), indent=1, default=str)
print("builder rows reproduced in the same session: %d/%d; failing %s" % (bp, len(builder), [r["id"] for r in builder if not r["pass"]]))
print("launches %s; chrome pid alive after close: %s; version %s" % (bc.LAUNCHES, alive, version))
print("M20R2 BROWSER PROBE %d/%d" % (sum(r["pass"] for r in ROWS), len(ROWS)))
