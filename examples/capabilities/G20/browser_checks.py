#!/usr/bin/env python3
"""G20 rendered checks: the demo page in headless Google Chrome over the DevTools protocol (standard library only).

Usage: browser_checks.py [--core PATH] [--page HTML] [--out DIR] [--chrome PATH] [--json]
Exit 0 all checks pass, 1 any check fails, 3 no browser named (nothing was run; the report says so).
It never looks for a browser by itself: Chrome starts only when --chrome PATH or G20_CHROME names the binary.

The page is the shipped examples/capabilities/G20/demo/index.html. It is copied to a temporary folder with its two
script paths made absolute (and the core swapped when --core is given); nothing else changes. A test transport is
installed before the page loads through window.G20_TEST_FETCH, so the checks decide when and in which order
responses arrive. Real key events (Input.dispatchKeyEvent) drive the combobox; layout is measured from the rendered
DOM at 320, 360 and 1280 px CSS widths, and a screenshot is written for each width."""
import argparse, base64, json, os, re, shutil, socket, struct, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CORE = ROOT / "employees" / "engineering" / "frontend-developer" / "async_search_core.js"
LONG = "Avocet-Long-Name-" + "x" * 150
ROWS = [{"id": "Heron Flats 41", "label": "Heron Flats 41"}, {"id": "kestrel\tyard 7", "label": "Kestrel Yard 7"},
        {"id": "a_b", "label": "Marlin Dock 3"}, {"id": "a b", "label": "Marlin Dock 3 annex"},
        {"id": "\u00d8resund 2", "label": "\u00d8resund 2"}, {"id": "avocet", "label": LONG}]
OTHER = [{"id": "old-1", "label": "Old answer one"}, {"id": "old-2", "label": "Old answer two"}]
VALID_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")
KEYS = {"Tab": 9, "Enter": 13, "Escape": 27, "ArrowDown": 40, "ArrowUp": 38, "Home": 36, "End": 35}
HOOK = """window.__g20 = {pending: [], log: []};
window.G20_TEST_FETCH = function (q, o) { return new Promise(function (res, rej) { window.__g20.pending.push({q: q, res: res, rej: rej}); window.__g20.log.push(q); }); };
window.__g20.settle = function (q, rows, err) { for (var i = 0; i < window.__g20.pending.length; i++) { if (window.__g20.pending[i].q === q) {
  var p = window.__g20.pending.splice(i, 1)[0]; if (err) p.rej(new Error(err)); else p.res(rows); return true; } } return false; };"""


class WS:
    def __init__(self, url):
        u = urlparse(url); self.s = socket.create_connection((u.hostname, u.port), timeout=30)
        key = base64.b64encode(os.urandom(16)).decode()
        self.s.sendall(("GET %s HTTP/1.1\r\nHost: %s:%d\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: %s\r\n"
                        "Sec-WebSocket-Version: 13\r\n\r\n" % (u.path, u.hostname, u.port, key)).encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            buf += self.s.recv(4096)
        if b" 101 " not in buf.split(b"\r\n", 1)[0]:
            raise RuntimeError("websocket upgrade failed")
        self.rest = buf.split(b"\r\n\r\n", 1)[1]

    def send(self, text):
        data = text.encode(); n = len(data); hdr = bytearray([0x81])
        hdr += bytes([0x80 | n]) if n < 126 else (bytes([0x80 | 126]) + struct.pack(">H", n) if n < 65536 else bytes([0x80 | 127]) + struct.pack(">Q", n))
        mask = os.urandom(4); self.s.sendall(bytes(hdr) + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))

    def recv(self):
        msg = b""
        while True:
            while True:
                r = self.rest
                if len(r) >= 2:
                    n, off = r[1] & 0x7F, 2
                    if n == 126 and len(r) >= 4:
                        n, off = struct.unpack(">H", r[2:4])[0], 4
                    elif n == 127 and len(r) >= 10:
                        n, off = struct.unpack(">Q", r[2:10])[0], 10
                    if n < 126 or off > 2:
                        if len(r) >= off + n:
                            b0, payload, self.rest = r[0], r[off:off + n], r[off + n:]
                            break
                self.rest += self.s.recv(1 << 16)
            if b0 & 0x0F == 9:
                continue
            msg += payload
            if b0 & 0x80:
                return msg.decode()


class Browser:
    def __init__(self, chrome, width):
        self.prof = tempfile.mkdtemp(prefix="g20-chrome-")
        self.proc = subprocess.Popen([chrome, "--headless=new", "--remote-debugging-port=0", "--user-data-dir=" + self.prof,
                                      "--no-first-run", "--no-default-browser-check", "--disable-background-networking",
                                      "--disable-extensions", "--disable-sync", "--allow-file-access-from-files",
                                      "--window-size=%d,800" % max(width, 500), "about:blank"],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        port_file = Path(self.prof) / "DevToolsActivePort"
        for _ in range(200):
            if port_file.exists() and port_file.read_text().strip():
                break
            time.sleep(0.05)
        port = int(port_file.read_text().split()[0])
        for _ in range(100):
            try:
                tabs = json.loads(urllib.request.urlopen("http://127.0.0.1:%d/json/list" % port, timeout=5).read())
                ws = [t["webSocketDebuggerUrl"] for t in tabs if t.get("type") == "page"]
                if ws:
                    break
            except OSError:
                pass
            time.sleep(0.05)
        self.ws, self.n, self.events = WS(ws[0]), 0, []

    def cmd(self, method, **params):
        self.n += 1; mid = self.n
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params}))
        while True:
            m = json.loads(self.ws.recv())
            if m.get("id") == mid:
                if "error" in m:
                    raise RuntimeError("%s: %s" % (method, m["error"]))
                return m.get("result", {})
            self.events.append(m)

    def js(self, expr):
        r = self.cmd("Runtime.evaluate", expression=expr, returnByValue=True, awaitPromise=True)
        if "exceptionDetails" in r:
            raise RuntimeError("js error: %s" % r["exceptionDetails"].get("text"))
        return r["result"].get("value")

    def key(self, k):
        code = KEYS[k]; extra = {"text": "\r"} if k == "Enter" else {}
        self.cmd("Input.dispatchKeyEvent", type="keyDown" if not extra else "keyDown", key=k, code=k, windowsVirtualKeyCode=code, nativeVirtualKeyCode=code, **extra)
        self.cmd("Input.dispatchKeyEvent", type="keyUp", key=k, code=k, windowsVirtualKeyCode=code, nativeVirtualKeyCode=code)
        time.sleep(0.03)

    def type(self, text):
        for ch in text:
            self.cmd("Input.dispatchKeyEvent", type="keyDown", key=ch, text=ch, unmodifiedText=ch)
            self.cmd("Input.dispatchKeyEvent", type="keyUp", key=ch)
        time.sleep(0.03)

    def wait(self, expr, timeout=3.0):
        end = time.time() + timeout
        while time.time() < end:
            if self.js(expr):
                return True
            time.sleep(0.03)
        return False

    def close(self):
        try:
            self.proc.terminate(); self.proc.wait(5)
        except Exception:
            self.proc.kill()
        shutil.rmtree(self.prof, ignore_errors=True)


def page_copy(core, tmp, page=None):
    demo = HERE / "demo"
    html = Path(page or demo / "index.html").read_text()
    a = '<script src="fixture-data.js"></script>'
    b = '<script src="../../../../employees/engineering/frontend-developer/async_search_core.js"></script>'
    if a not in html or b not in html:
        raise SystemExit("demo page script tags not found")
    html = html.replace(a, '<script src="%s"></script>' % (demo / "fixture-data.js").as_uri()).replace(b, '<script src="%s"></script>' % Path(core).resolve().as_uri())
    out = Path(tmp) / "index.html"; out.write_text(html)
    return out.as_uri()


GEOM = """(function () { var d = document.documentElement, b = document.body, L = document.getElementById('results');
  var lr = L.getBoundingClientRect(), opts = Array.prototype.slice.call(L.querySelectorAll('[role=option]'));
  var c = document.getElementById('chosen').getBoundingClientRect();
  return {docSW: d.scrollWidth, docCW: d.clientWidth, bodySW: b.scrollWidth, inner: window.innerWidth, listRight: lr.right, listHidden: L.hidden,
    chosenRight: c.right, chosenSW: document.getElementById('chosen').scrollWidth, chosenCW: document.getElementById('chosen').clientWidth,
    opts: opts.map(function (o) { var r = o.getBoundingClientRect(); return {id: o.id, sw: o.scrollWidth, cw: o.clientWidth, left: Math.round(r.left), right: r.right, h: r.height}; })}; })()"""
STATE = """(function () { var q = document.getElementById('q'), L = document.getElementById('results'), ad = q.getAttribute('aria-activedescendant');
  var el = ad ? document.getElementById(ad) : null, sel = null; try { sel = ad ? document.querySelector('#' + ad) : null; } catch (e) { sel = 'throws'; }
  return {focus: document.activeElement && document.activeElement.id, value: q.value, expanded: q.getAttribute('aria-expanded'), hidden: L.hidden,
    ad: ad, adResolves: !!el && el.parentNode === L && el.getAttribute('role') === 'option', adSelector: sel === el && !!el,
    selected: Array.prototype.map.call(L.querySelectorAll('[aria-selected=true]'), function (o) { return o.textContent; }),
    labels: Array.prototype.map.call(L.children, function (o) { return o.textContent; }), status: document.getElementById('status').textContent,
    chosen: document.getElementById('chosen').textContent, err: !document.getElementById('error').hidden,
    outline: getComputedStyle(document.activeElement).outlineStyle + ' ' + getComputedStyle(document.activeElement).outlineWidth}; })()"""


def run(chrome, core, out, widths=(320, 360, 1280), page=None):
    rows, shots = [], {}
    def row(rid, ok, desc, detail):
        rows.append({"id": rid, "pass": bool(ok), "desc": desc, "detail": detail})
    tmp = tempfile.mkdtemp(prefix="g20-page-")
    url = page_copy(core, tmp, page)
    for w in widths:
        b = Browser(chrome, w)
        try:
            b.cmd("Page.enable"); b.cmd("Runtime.enable"); b.cmd("Network.enable")
            b.cmd("Page.addScriptToEvaluateOnNewDocument", source=HOOK)
            b.cmd("Emulation.setDeviceMetricsOverride", width=w, height=800, deviceScaleFactor=1, mobile=False)
            b.cmd("Page.navigate", url=url)
            b.wait("document.readyState === 'complete' && !!window.SolarisAsyncSearch")
            # keyboard reaches the input with a visible focus indicator
            b.key("Tab"); s = b.js(STATE)
            row("K01-%d" % w, s["focus"] == "q" and s["outline"] == "solid 3px", "Tab reaches the input and shows a 3px focus outline", s["outline"])
            # search with long labels and ids holding whitespace, underscore and non-ASCII characters
            b.type("sol"); b.wait("window.__g20.pending.some(function (p) { return p.q === 'sol'; })")
            b.js("window.__g20.settle('sol', %s)" % json.dumps(ROWS)); b.wait("document.querySelectorAll('#results [role=option]').length === %d" % len(ROWS))
            g = b.js(GEOM)
            over = [o["id"] for o in g["opts"] if o["sw"] > o["cw"] or o["right"] > g["listRight"] + 0.5]
            row("L01-%d" % w, g["docSW"] <= g["docCW"] and g["bodySW"] <= g["docCW"] and g["listRight"] <= g["inner"] and not over and not g["listHidden"],
                "no horizontal overflow with a 167-character unbroken label: page scrollWidth <= clientWidth, every option inside the list and the viewport",
                {"docSW": g["docSW"], "docCW": g["docCW"], "listRight": g["listRight"], "inner": g["inner"], "overflowing": over})
            cols = len({o["left"] for o in g["opts"]}); want = 1 if w < 640 else 2; minh = min(o["h"] for o in g["opts"])
            row("L02-%d" % w, cols == want and minh >= (44 if w < 640 else 32), "%d column(s) and targets at least %d px" % (want, 44 if w < 640 else 32), {"columns": cols, "min_height": minh})
            png = b.cmd("Page.captureScreenshot", format="png", captureBeyondViewport=False)["data"]
            if out:
                p = Path(out) / ("screenshot-%d.png" % w); p.write_bytes(base64.b64decode(png)); shots[w] = str(p.name)
            # every option id is a valid IDREF token that resolves, is unique and maps one to one
            ids, ok_ids = [], True
            for i in range(len(ROWS)):
                b.key("ArrowDown"); s = b.js(STATE); ids.append(s["ad"])
                ok_ids = ok_ids and s["focus"] == "q" and bool(s["ad"]) and bool(VALID_ID.match(s["ad"] or "")) and s["adResolves"] and s["adSelector"]
            row("K02-%d" % w, ok_ids and len(set(ids)) == len(ROWS), "ArrowDown through all options: aria-activedescendant is a whitespace-free id that resolves (also as a CSS selector), unique per row; focus stays on the input", ids)
            # the long label is active and stays inside the viewport
            g2 = b.js(GEOM); act = [o for o in g2["opts"] if o["id"] == ids[-1]][0]
            row("K03-%d" % w, s["selected"] == [LONG] and act["right"] <= g2["inner"] and g2["docSW"] <= g2["docCW"], "the active long label is inside the viewport", {"right": act["right"], "inner": g2["inner"]})
            b.key("ArrowDown"); s1 = b.js(STATE); b.key("End"); s2 = b.js(STATE); b.key("Home"); s3 = b.js(STATE)
            row("K04-%d" % w, s1["selected"] == [ROWS[0]["label"]] and s2["selected"] == [LONG] and s3["selected"] == [ROWS[0]["label"]], "ArrowDown wraps to the first option; End and Home", [s1["selected"], s2["selected"], s3["selected"]])
            b.key("End"); b.key("Enter"); s = b.js(STATE); g3 = b.js(GEOM)
            row("K05-%d" % w, s["value"] == LONG and s["hidden"] and s["expanded"] == "false" and s["focus"] == "q" and s["chosen"] == "Chosen: " + LONG
                and g3["docSW"] <= g3["docCW"] and g3["chosenSW"] <= g3["chosenCW"], "Enter chooses the long label, closes the list, keeps focus; the chosen line wraps without overflow",
                {"focus": s["focus"], "docSW": g3["docSW"], "docCW": g3["docCW"]})
            b.key("ArrowDown"); s1 = b.js(STATE); b.key("Escape"); s2 = b.js(STATE); b.key("Escape"); s3 = b.js(STATE)
            row("K06-%d" % w, s1["expanded"] == "true" and s2["hidden"] and s2["value"] == LONG and s3["value"] == "" and s3["focus"] == "q", "Escape closes, a second Escape clears; focus stays", [s1["expanded"], s2["hidden"], s3["value"]])
            # stale responses: an older answer arriving last never replaces the newer list, even with an option active
            b.type("a"); b.wait("window.__g20.pending.some(function (p) { return p.q === 'a'; })")
            b.type("b"); b.wait("window.__g20.pending.some(function (p) { return p.q === 'ab'; })")
            b.js("window.__g20.settle('ab', %s)" % json.dumps(ROWS)); b.wait("document.querySelectorAll('#results [role=option]').length === %d" % len(ROWS))
            b.key("ArrowDown"); before = b.js(STATE)
            b.js("window.__g20.settle('a', %s)" % json.dumps(OTHER)); time.sleep(0.25); after = b.js(STATE)
            row("S01-%d" % w, after["labels"] == [r["label"] for r in ROWS] and after["selected"] == before["selected"] and after["ad"] == before["ad"] and after["adResolves"]
                and "Old answer" not in after["status"] and after["status"] == before["status"], "an older response arriving after the newer one changes nothing: same rows, active option, status",
                {"labels": len(after["labels"]), "status": after["status"]})
            # error, Retry by keyboard, focus back to the input
            b.key("Escape"); b.key("Escape"); b.type("zz"); b.wait("window.__g20.pending.some(function (p) { return p.q === 'zz'; })")
            b.js("window.__g20.settle('zz', null, 'fixture 503')"); b.wait("!document.getElementById('error').hidden")
            n0 = b.js("window.__g20.log.length"); b.key("Tab"); f = b.js("document.activeElement.id"); b.key("Enter")
            again = b.wait("window.__g20.log.length > %d && window.__g20.log[window.__g20.log.length - 1] === 'zz'" % n0); s = b.js(STATE)
            row("K07-%d" % w, f == "retry" and again and s["focus"] == "q", "error shown; Tab reaches Retry, Enter re-runs the failed query, focus returns to the input", {"tab_to": f, "rerun": again})
            exc = [e for e in b.events if e.get("method") == "Runtime.exceptionThrown"]
            ext = [e["params"]["request"]["url"] for e in b.events if e.get("method") == "Network.requestWillBeSent" and not e["params"]["request"]["url"].startswith(("file:", "data:", "about:"))]
            row("X01-%d" % w, not exc and not ext, "no JavaScript exceptions and no network requests", {"exceptions": len(exc), "external": ext[:3]})
        except Exception as ex:
            row("E-%d" % w, False, "run error", "%s: %s" % (type(ex).__name__, ex))
        finally:
            b.close()
    shutil.rmtree(tmp, ignore_errors=True)
    return rows, shots


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--core", default=str(CORE)); ap.add_argument("--page"); ap.add_argument("--out"); ap.add_argument("--chrome"); ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    chrome = a.chrome or os.environ.get("G20_CHROME")  # explicit only: no browser is ever discovered or started by default
    if not chrome or not os.path.isfile(chrome):
        print("UNRUN: no browser named (pass --chrome PATH or set G20_CHROME); no rendered check was run"); return 3
    if a.out:
        Path(a.out).mkdir(parents=True, exist_ok=True)
    rows, shots = run(chrome, a.core, a.out, page=a.page)
    n = sum(r["pass"] for r in rows)
    rep = {"chrome": subprocess.run([chrome, "--version"], capture_output=True, text=True).stdout.strip(), "rows": rows, "screenshots": shots,
           "not_run": "screen readers, other browsers, touch, zoom, forced colours"}
    if a.out:
        (Path(a.out) / "report.json").write_text(json.dumps(rep, indent=1))
    if a.json:
        print(json.dumps(rep, indent=1))
    else:
        for r in rows:
            print("%s %s %s%s" % ("PASS" if r["pass"] else "FAIL", r["id"], r["desc"], "" if r["pass"] else " :: " + json.dumps(r["detail"])[:300]))
    print("BROWSER CHECKS %d/%d %s" % (n, len(rows), "PASS" if n == len(rows) and rows else "FAIL"))
    return 0 if n == len(rows) and rows else 1


if __name__ == "__main__":
    sys.exit(main())
