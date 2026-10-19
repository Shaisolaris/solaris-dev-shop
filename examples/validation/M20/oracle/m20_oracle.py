#!/usr/bin/env python3
"""M20 prep oracle: accessible asynchronous UI behaviour (G20). Grok self-validation, not independent review.

Black-box: drives a real headless Chrome with real key events through CDP and controls every search/save
response (order, status, timing) itself, either by intercepting the page's HTTP requests (transport.mode
"network") or by injecting a fixture transport global the page calls (transport.mode "global").
Built from G20.md / M20.md and repo 02ba9c5 only, before any G20 candidate existed; a candidate is bound
through a binding JSON (see README.md). Core checks score; adversarial checks are findings only.
Interaction proof (DOM, focus, events) and screenshot evidence are reported in separate sections.

usage: m20_oracle.py BINDING.json OUT_DIR [--only ID,ID] [--perf-reps N]
"""
import base64, functools, http.server, json, os, re, statistics, sys, threading, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp import Browser

DEF_TEXT = {"loading": r"(?i)\b(loading|searching|fetching)\b", "error": r"(?i)\b(error|failed|could ?n[o']?t|try again|unavailable)\b",
            "empty": r"(?i)\bno (results|matches|items|sites|records)\b|\bnothing (found|matched)\b", "saved": r"(?i)\bsaved\b"}
LIVE_JS = """(() => Array.from(document.querySelectorAll('[aria-live],[role=status],[role=alert],[role=log]'))
  .filter(e => (e.getAttribute('aria-live') || '') !== 'off'))()"""
INIT_JS = """
window.__m20err = [];
addEventListener('error', e => window.__m20err.push('error: ' + e.message));
addEventListener('unhandledrejection', e => window.__m20err.push('unhandledrejection: ' + String(e.reason)));
addEventListener('load', () => setTimeout(() => {
  for (const e of %s) e.setAttribute('data-m20-initial', '1');
}, 0));
""" % LIVE_JS
GLOBAL_JS = """
window.__m20q = []; window.__m20p = {}; window.__m20n = 0;
window[%s] = function (req) {
  req = req || {}; const id = ++window.__m20n;
  window.__m20q.push({id, url: String(req.url || ''), method: String(req.method || 'GET').toUpperCase(),
    body: req.body == null ? null : (typeof req.body === 'string' ? req.body : JSON.stringify(req.body))});
  return new Promise((res, rej) => { window.__m20p[id] = {res, rej}; });
};
window.__m20resolve = function (id, status, text) {
  const p = window.__m20p[id]; if (!p) return false; delete window.__m20p[id];
  if (status === 0) { p.rej(new TypeError('network error (fixture)')); return true; }
  p.res({ok: status >= 200 && status < 300, status, text: () => Promise.resolve(text),
         json: () => Promise.resolve().then(() => JSON.parse(text))});
  return true;
};
"""


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


class Req:
    def __init__(self, rid, url, method, body, kind):
        self.rid, self.url, self.method, self.body, self.kind = rid, url, method, body, kind
        self.done = False


class H:
    """Harness around one Browser. Each scenario calls load() for a fresh page."""

    def __init__(self, binding, bdir, raw_dir):
        self.B, self.bdir, self.raw = binding, bdir, raw_dir
        self.sel = binding["selectors"]
        self.txt = {k: re.compile(binding.get("text", {}).get(k, v)) for k, v in DEF_TEXT.items()}
        self.tr = binding["transport"]
        self.search_re = re.compile(self.tr["search_url_regex"])
        self.save_re = re.compile(self.tr["save_url_regex"])
        self.external = []
        self.server = None
        page = binding["page"]
        if "serve_dir" in page:
            root = os.path.join(bdir, page["serve_dir"])
            self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=root))
            threading.Thread(target=self.server.serve_forever, daemon=True).start()
            self.origin = f"http://127.0.0.1:{self.server.server_address[1]}"
            self.url = self.origin + "/" + page["path"]
        else:
            self.origin = "file://"
            self.url = "file://" + os.path.abspath(os.path.join(bdir, page["file"]))
        self.b = Browser()
        self.b.hook = self._hook
        self.b.call("Page.enable")
        self.b.call("Runtime.enable")
        self.b.call("Page.addScriptToEvaluateOnNewDocument", source=INIT_JS)
        if self.tr["mode"] == "global":
            self.b.call("Page.addScriptToEvaluateOnNewDocument", source=GLOBAL_JS % json.dumps(self.tr["name"]))
        self.b.call("Fetch.enable", patterns=[{"urlPattern": "*", "requestStage": "Request"}])
        self.width = None

    # ---------- transport ----------
    def _hook(self, m):
        meth = m.get("method")
        if meth == "Fetch.requestPaused":
            p = m["params"]
            url, method = p["request"]["url"], p["request"]["method"]
            kind = self._kind(url, method)
            if kind and self.tr["mode"] == "network":
                self.reqs.append(Req(p["requestId"], url, method, p["request"].get("postData"), kind))
            elif url.startswith(self.origin) or url.startswith(("file:", "data:", "blob:")):
                self.b.call("Fetch.continueRequest", requestId=p["requestId"])
            else:
                self.external.append(url)
                self.b.call("Fetch.failRequest", requestId=p["requestId"], errorReason="BlockedByClient")
        elif meth == "Runtime.exceptionThrown":
            d = m["params"]["exceptionDetails"]
            self.exc.append((d.get("exception", {}).get("description") or d.get("text", ""))[:200])
        elif meth == "Runtime.consoleAPICalled" and m["params"].get("type") == "error":
            self.console_err.append(" ".join(str(a.get("value", a.get("description", ""))) for a in m["params"]["args"])[:200])

    def _kind(self, url, method):
        if self.save_re.search(url) and method in ("POST", "PUT", "PATCH"):
            return "save"
        if self.search_re.search(url):
            return "search"
        return None

    def poll(self, seconds=0.0):
        self.b.pump(seconds)
        if self.tr["mode"] == "global":
            for r in self.b.eval("window.__m20q ? window.__m20q.splice(0) : []") or []:
                k = self._kind(r["url"], r["method"])
                if k:
                    self.reqs.append(Req(r["id"], r["url"], r["method"], r["body"], k))

    def pending(self, kind):
        return [r for r in self.reqs if r.kind == kind and not r.done]

    def wait_req(self, kind, n=1, timeout=3.0, since=0):
        end = time.time() + timeout
        while True:
            got = [r for r in self.reqs[since:] if r.kind == kind]
            if len(got) >= n or time.time() > end:
                return got
            self.poll(0.03)

    def query_of(self, r):
        src = self.tr.get("query_from", "param:q")
        how, key = src.split(":", 1)
        if how == "param":
            from urllib.parse import urlparse, parse_qs
            return (parse_qs(urlparse(r.url).query).get(key) or [""])[0]
        return json.loads(r.body or "{}").get(key, "")

    def respond(self, r, status=200, obj=None, raw=None):
        text = raw if raw is not None else json.dumps(obj if obj is not None else {})
        r.done = True
        try:
            if self.tr["mode"] == "network":
                if status == 0:
                    self.b.call("Fetch.failRequest", requestId=r.rid, errorReason="Failed")
                else:
                    self.b.call("Fetch.fulfillRequest", requestId=r.rid, responseCode=status,
                                responseHeaders=[{"name": "Content-Type", "value": "application/json"}],
                                body=base64.b64encode(text.encode()).decode())
            else:
                self.b.eval(f"window.__m20resolve({json.dumps(r.rid)}, {status}, {json.dumps(text)})")
        except RuntimeError as e:  # request already aborted by the page: fine
            return str(e)[:120]

    def items(self, labels):
        sr = self.B["search_response"]
        tmpl = sr["item_template"]
        out = []
        for i, lab in enumerate(labels):
            out.append({k: (v.replace("{id}", f"id-{lab}").replace("{label}", lab) if isinstance(v, str) else v) for k, v in tmpl.items()})
        return {sr["items_key"]: out}

    def ok_save(self):
        return self.B.get("save_response", {"ok": True})

    # ---------- page ----------
    def load(self, width=1280, height=800):
        self.reqs, self.exc, self.console_err = [], [], []
        if width != self.width:
            self.b.call("Emulation.setDeviceMetricsOverride", width=width, height=height, deviceScaleFactor=1, mobile=width < 600)
            self.width = width
        self.b.call("Page.navigate", url=self.url)
        end = time.time() + 10
        while time.time() < end:
            self.poll(0.05)
            try:
                if self.b.eval("document.readyState") == "complete" and self.b.eval(f"!!document.querySelector({json.dumps(self.sel['query'])})"):
                    break
            except RuntimeError:
                pass
        self.poll(0.15)

    def js(self, expr):
        return self.b.eval(expr)

    def q(self, name):
        return json.dumps(self.sel[name])

    def shown(self):
        return self.js(f"Array.from(document.querySelectorAll({self.q('item')})).map(e => e.innerText).join('\\n')") or ""

    def page_text(self):
        return self.js("document.body ? document.body.innerText : ''") or ""

    def live(self):
        return self.js(f"{LIVE_JS}.map(e => ({{initial: e.hasAttribute('data-m20-initial'), role: e.getAttribute('role') || '', "
                       f"live: e.getAttribute('aria-live') || '', text: e.innerText || e.textContent || ''}}))") or []

    def announced(self, which):
        """Text matching `which` inside a live region that existed at load (or role=alert)."""
        rx = self.txt[which]
        return any(rx.search(r["text"]) and (r["initial"] or r["role"] == "alert") for r in self.live())

    def busy(self):
        return bool(self.js("!!document.querySelector('[aria-busy=true]')"))

    def active(self):
        return self.js("""(() => { const a = document.activeElement;
          if (!a || a === document.body || a === document.documentElement) return {lost: true, desc: a ? a.tagName : 'null'};
          return {lost: !a.isConnected, desc: a.tagName.toLowerCase() + (a.id ? '#' + a.id : '') + ' "' + (a.innerText || a.value || a.getAttribute('aria-label') || '').slice(0, 30) + '"'}; })()""")

    def focus_query(self):
        self.js(f"document.querySelector({self.q('query')}).focus()")

    def clear_and_type(self, s):
        self.focus_query()
        n = len(self.js(f"document.querySelector({self.q('query')}).value") or "")
        for _ in range(n):
            self.b.key("Backspace")
        self.b.type(s)

    def until(self, fn, timeout=1.5):
        end = time.time() + timeout
        while True:
            self.poll(0.02)
            v = fn()
            if v or time.time() > end:
                return v

    def tab_to(self, selector_name, max_tabs=40, start_body=False):
        """Press real Tab until the focused element matches the selector. Returns the number of presses or None."""
        if start_body:
            self.js("document.activeElement && document.activeElement.blur()")
        sel = self.q(selector_name)
        for i in range(1, max_tabs + 1):
            self.b.key("Tab")
            if self.js(f"!!(document.activeElement && document.activeElement.matches({sel}))"):
                return i
        return None

    def search_ok(self, q, labels):
        """Type q, answer its request with labels, wait until shown. Returns (ok, req)."""
        since = len(self.reqs)
        self.clear_and_type(q)
        rs = self.wait_req("search", since=since)
        if not rs:
            return False, None
        for r in rs[:-1]:
            if not r.done:
                self.respond(r, 200, self.items([]))
        self.respond(rs[-1], 200, self.items(labels))
        return bool(self.until(lambda: all(l in self.shown() for l in labels))), rs[-1]

    def errors(self):
        try:
            return self.exc + (self.js("window.__m20err || []") or [])
        except RuntimeError:
            return self.exc

    def close(self):
        self.b.close()
        if self.server:
            self.server.shutdown()


# ---------------- scenarios ----------------
SC = []


def sc(sid, kind, title):
    def deco(f):
        SC.append((sid, kind, title, f))
        return f
    return deco


@sc("C01", "core", "initial state: input, results container, pre-existing live region, Solaris branding, no errors")
def c01(h):
    h.load()
    d = h.js(f"""({{q: !!document.querySelector({h.q('query')}), res: !!document.querySelector({h.q('results')}),
      items: document.querySelectorAll({h.q('item')}).length, title: document.title}})""")
    live = [r for r in h.live() if r["initial"]]
    brand = bool(re.search(r"(?i)solaris", d["title"] + " " + h.page_text()))
    errtxt = bool(h.txt["error"].search(h.page_text()))
    ok = d["q"] and d["res"] and d["items"] == 0 and live and brand and not errtxt and not h.errors()
    return ok, dict(d, live_regions=len(live), solaris_brand=brand, error_text_at_load=errtxt, js_errors=h.errors())


@sc("C02", "core", "typing issues a request and shows a loading state while it is pending")
def c02(h):
    h.load()
    h.focus_query(); h.b.type("sol")
    rs = h.wait_req("search")
    if not rs:
        return False, {"request": None}
    loading = h.until(lambda: h.txt["loading"].search(h.page_text()) or h.busy(), 0.6)
    return bool(loading), {"query": h.query_of(rs[-1]), "loading_text_or_busy": bool(loading), "announced": h.announced("loading")}


@sc("C03", "core", "success renders the returned items and clears loading")
def c03(h):
    h.load()
    ok, r = h.search_ok("sol", ["Heron Flats 41", "Kestrel Yard 7", "Marlin Dock 3"])
    cleared = h.until(lambda: not h.txt["loading"].search(h.page_text()) and not h.busy(), 1.0)
    return bool(ok and cleared), {"shown": h.shown().split("\n")[:5], "loading_cleared": bool(cleared)}


@sc("C04", "core", "empty response shows and announces an empty state")
def c04(h):
    h.load()
    h.focus_query(); h.b.type("zzq")
    rs = h.wait_req("search")
    if not rs:
        return False, {"request": None}
    for r in rs:
        h.respond(r, 200, h.items([]))
    vis = h.until(lambda: h.txt["empty"].search(h.page_text()))
    ann = h.until(lambda: h.announced("empty"), 0.5)
    return bool(vis and ann and not h.shown().strip()), {"empty_visible": bool(vis), "announced": bool(ann), "js_errors": h.errors()}


@sc("C05", "core", "server error: announced, loading cleared, recoverable, error cleared on later success")
def c05(h):
    h.load()
    h.focus_query(); h.b.type("sol")
    rs = h.wait_req("search")
    if not rs:
        return False, {"request": None}
    for r in rs:
        h.respond(r, 500, {"error": "fixture 500"})
    ann = h.until(lambda: h.announced("error"))
    cleared = not h.txt["loading"].search(h.page_text()) and not h.busy()
    # recovery: a retry control activated by keyboard, else typing again
    since = len(h.reqs)
    retry = h.js("""(() => { const b = Array.from(document.querySelectorAll('button,[role=button],a[href]'))
        .find(e => /retry|try again/i.test(e.innerText || e.getAttribute('aria-label') || '')); if (!b) return false;
        b.setAttribute('data-m20-retry', '1'); return true; })()""")
    route = None
    if retry:
        h.sel["_retry"] = "[data-m20-retry]"
        if h.tab_to("_retry", start_body=True):
            h.b.key("Enter"); route = "retry control via keyboard"
    if route is None:
        h.focus_query(); h.b.type("a"); route = "typing again"
    rs2 = h.wait_req("search", since=since)
    recovered = False
    if rs2:
        h.respond(rs2[-1], 200, h.items(["Osprey Quay 9"]))
        recovered = bool(h.until(lambda: "Osprey Quay 9" in h.shown() and not h.txt["error"].search(h.page_text())))
    return bool(ann and cleared and recovered), {"announced": bool(ann), "loading_cleared": cleared, "recovery_route": route,
                                                 "recovered_and_error_cleared": recovered, "js_errors": h.errors()}


def two_requests(h):
    """Type 'so' then 'l', leaving both requests pending. Returns (reqA, reqB) or None."""
    h.load()
    h.focus_query(); h.b.type("so")
    a = h.wait_req("search")
    h.b.type("l")
    b = h.wait_req("search", since=len(a)) if a else []
    if not a or not b:
        return None
    return a[-1], b[-1]


@sc("C06", "core", "out-of-order success: the late response for the older query never replaces the newer one")
def c06(h):
    rr = two_requests(h)
    if not rr:
        return False, {"requests": "fewer than 2 (cannot exercise; debounce or no requests)"}
    a, b = rr
    h.respond(b, 200, h.items(["Newer Result Bravo"]))
    first = h.until(lambda: "Newer Result Bravo" in h.shown())
    note = h.respond(a, 200, h.items(["Stale Result Alpha"]))
    h.poll(0.7)
    s = h.shown()
    return bool(first and "Stale Result Alpha" not in s and "Newer Result Bravo" in s), {
        "queries": [h.query_of(a), h.query_of(b)], "newer_shown": bool(first), "final_shown": s.split("\n")[:4], "late_fulfil": note}


@sc("C07", "core", "out-of-order failure: a late error for the older query does not show an error over fresh results")
def c07(h):
    rr = two_requests(h)
    if not rr:
        return False, {"requests": "fewer than 2"}
    a, b = rr
    h.respond(b, 200, h.items(["Newer Result Bravo"]))
    first = h.until(lambda: "Newer Result Bravo" in h.shown())
    h.respond(a, 500, {"error": "late"})
    h.poll(0.7)
    err = bool(h.txt["error"].search(h.page_text())) or h.announced("error")
    return bool(first and not err and "Newer Result Bravo" in h.shown()), {"newer_shown": bool(first), "error_shown_after_late_failure": err}


@sc("C08", "core", "keyboard: Tab reaches the input and a save control, no trap, visible focus indicator")
def c08(h):
    h.load()
    ok, _ = h.search_ok("sol", ["Heron Flats 41", "Kestrel Yard 7"])
    if not ok:
        return False, {"results": "not shown"}
    h.js("document.activeElement && document.activeElement.blur()")
    seq, vis = [], []
    for _ in range(30):
        h.b.key("Tab")
        info = h.js(f"""(() => {{ const a = document.activeElement; if (!a || a === document.body) return null;
          const cs = getComputedStyle(a); const ind = (cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth) > 0) || cs.boxShadow !== 'none';
          return {{q: a.matches({h.q('query')}), save: a.matches({h.q('save')}), fv: a.matches(':focus-visible'), ind,
                   d: a.tagName + (a.id ? '#' + a.id : '') + ':' + (a.innerText || a.value || '').slice(0, 20)}}; }})()""")
        seq.append(info["d"] if info else "body/none")
        if info:
            vis.append(info["fv"] and info["ind"])
    distinct = len(set(seq))
    stuck = any(len(set(seq[i:i + 6])) == 1 and seq[i] != "body/none" for i in range(len(seq) - 5)) and distinct <= 2
    # re-derive q/save reach from the sequence descriptors via selector checks
    hit_q = h.tab_to("query", start_body=True) is not None
    hit_save = h.tab_to("save", start_body=True) is not None
    all_vis = bool(vis) and all(vis)
    return bool(hit_q and hit_save and not stuck and all_vis), {"reached_query": hit_q, "reached_save": hit_save, "trap": stuck,
                                                                "visible_focus_all": all_vis, "tab_sequence": seq[:12]}


def to_first_save(h):
    ok, _ = h.search_ok("sol", ["Heron Flats 41", "Kestrel Yard 7"])
    if not ok:
        return None
    return h.tab_to("save", start_body=True)


@sc("C09", "core", "failed save via keyboard: error announced, focus kept, item not marked saved, control usable again")
def c09(h):
    h.load()
    if not to_first_save(h):
        return False, {"save_control": "not reachable by Tab"}
    item_js = f"(() => {{ const a = document.activeElement; const it = a && a.closest({h.q('item')}); return it ? it.innerText : ''; }})()"
    since = len(h.reqs)
    h.b.key("Enter")
    rs = h.wait_req("save", since=since, timeout=1.5)
    if not rs:
        return False, {"save_request": "none after Enter"}
    h.respond(rs[0], 500, {"error": "fixture save failure"})
    ann = h.until(lambda: h.announced("error"))
    act = h.active()
    item_txt = h.js(item_js) or ""
    marked = bool(h.txt["saved"].search(item_txt)) and not h.txt["error"].search(item_txt)
    usable = h.js("(() => { const a = document.activeElement; return !!a && !a.disabled && a.getAttribute('aria-disabled') !== 'true'; })()")
    h.state_c09 = dict(after_fail_focus=act)
    return bool(ann and not act["lost"] and not marked and usable), {"announced": bool(ann), "focus_after_failure": act,
                                                                     "item_marked_saved": marked, "control_usable": bool(usable), "js_errors": h.errors()}


@sc("C10", "core", "retry save via keyboard after a failure succeeds and is announced")
def c10(h):
    h.load()
    if not to_first_save(h):
        return False, {"save_control": "not reachable by Tab"}
    since = len(h.reqs)
    h.b.key("Enter")
    rs = h.wait_req("save", since=since, timeout=1.5)
    if not rs:
        return False, {"save_request": "none"}
    h.respond(rs[0], 500, {"error": "x"})
    h.until(lambda: h.announced("error"))
    if h.active()["lost"]:
        h.tab_to("save", start_body=True)
    since = len(h.reqs)
    h.b.key("Enter")
    rs2 = h.wait_req("save", since=since, timeout=1.5)
    if not rs2:
        return False, {"retry_request": "none"}
    h.respond(rs2[0], 200, h.ok_save())
    ann = h.until(lambda: h.announced("saved"))
    return bool(ann and not h.active()["lost"]), {"saved_announced": bool(ann), "focus": h.active()}


@sc("C11", "core", "focus recovery: results re-render while focus is on a result control; focus is not dropped")
def c11(h):
    h.load()
    ok, _ = h.search_ok("so", ["Heron Flats 41", "Kestrel Yard 7"])
    if not ok:
        return False, {"results": "not shown"}
    h.focus_query()
    since = len(h.reqs)
    h.b.type("l")
    rs = h.wait_req("search", since=since)
    if not rs:
        return False, {"request": None}
    n = h.tab_to("save")
    if not n:
        return False, {"save_control": "not reachable by Tab while request pending"}
    before = h.active()
    h.respond(rs[-1], 200, h.items(["Plover Steps 2", "Tern Row 5"]))
    h.until(lambda: "Plover Steps 2" in h.shown())
    h.poll(0.3)
    after = h.active()
    return (not after["lost"]), {"focus_before": before, "focus_after_rerender": after}


def layout(h, width):
    h.load(width=width)
    ok, _ = h.search_ok("sol", ["Heron Flats 41", "Kestrel Yard 7", "Avocet-Long-Name-" + "x" * 48])
    m = h.js(f"""(() => {{ const W = innerWidth; const els = Array.from(document.querySelectorAll({h.q('query')} + ',' + {h.q('save')}));
      const bad = els.filter(e => {{ const r = e.getBoundingClientRect(); return r.width <= 0 || r.height <= 0 || r.left < -1 || r.right > W + 1; }})
        .map(e => e.tagName + ':' + (e.innerText || '').slice(0, 15));
      return {{W, scrollW: document.documentElement.scrollWidth, controls: els.length, outside: bad}}; }})()""")
    shot = h.b.call("Page.captureScreenshot", format="png")["data"]
    p = os.path.join(h.raw, f"screenshot-{width}.png")
    open(p, "wb").write(base64.b64decode(shot))
    h.shots.append(p)
    good = bool(ok) and m["scrollW"] <= m["W"] + 1 and m["controls"] >= 2 and not m["outside"]
    return good, dict(m, results_shown=bool(ok))


@sc("C12", "core", "narrow 360px: no horizontal overflow, input and save controls inside the viewport")
def c12(h):
    return layout(h, 360)


@sc("C13", "core", "wide 1280px: no horizontal overflow, input and save controls inside the viewport")
def c13(h):
    return layout(h, 1280)


@sc("A01", "adversarial", "three overlapping requests resolved 3,1,2: only the newest is ever shown after it lands")
def a01(h):
    h.load()
    h.focus_query()
    reqs = []
    for ch in "sol":
        since = len(h.reqs)
        h.b.type(ch)
        r = h.wait_req("search", since=since)
        if r:
            reqs.append(r[-1])
    if len(reqs) < 3:
        return None, {"requests": len(reqs), "note": "cannot exercise: page coalesced requests"}
    r1, r2, r3 = reqs
    h.respond(r3, 200, h.items(["Third Gamma"]))
    h.until(lambda: "Third Gamma" in h.shown())
    snaps = []
    for r, lab in ((r1, "First Alpha"), (r2, "Second Beta")):
        h.respond(r, 200, h.items([lab]))
        h.poll(0.4)
        snaps.append(h.shown())
    bad = any("First Alpha" in s or "Second Beta" in s for s in snaps)
    return (not bad and "Third Gamma" in snaps[-1]), {"snapshots": [s.split("\n")[:2] for s in snaps]}


@sc("A02", "adversarial", "same query text twice (so, sol, so): the older 'so' response arriving last is still stale")
def a02(h):
    h.load()
    h.focus_query(); h.b.type("so")
    a1 = h.wait_req("search")
    h.b.type("l")
    b = h.wait_req("search", since=len(a1))
    since = len(h.reqs)
    h.b.key("Backspace")
    a2 = h.wait_req("search", since=since)
    if not (a1 and b and a2):
        return None, {"requests": [len(a1), len(b), len(a2)], "note": "cannot exercise (cache or coalescing); inspect manually"}
    h.respond(a2[-1], 200, h.items(["Current So Result"]))
    h.until(lambda: "Current So Result" in h.shown())
    h.respond(b[-1], 200, h.items(["Stale Sol Result"]))
    h.poll(0.4)
    h.respond(a1[-1], 200, h.items(["Stale So Result"]))
    h.poll(0.6)
    s = h.shown()
    return ("Current So Result" in s and "Stale" not in s), {"final_shown": s.split("\n")[:3]}


@sc("A03", "adversarial", "input cleared while requests are pending: late responses do not repopulate results")
def a03(h):
    h.load()
    h.focus_query(); h.b.type("sol")
    h.wait_req("search")
    for _ in range(3):
        h.b.key("Backspace")
    h.poll(0.6)
    for r in h.pending("search"):
        h.respond(r, 200, h.items(["Ghost Result " + h.query_of(r)]))
    h.poll(0.7)
    s = h.shown()
    stuck = bool(h.txt["loading"].search(h.page_text())) or h.busy()
    return ("Ghost Result" not in s and not stuck), {"shown": s.split("\n")[:3], "loading_stuck": stuck,
                                                    "value": h.js(f"document.querySelector({h.q('query')}).value")}


@sc("A04", "adversarial", "malformed JSON on 200: error state, no uncaught exception, not an empty state")
def a04(h):
    h.load()
    h.focus_query(); h.b.type("sol")
    rs = h.wait_req("search")
    if not rs:
        return False, {"request": None}
    for r in rs:
        h.respond(r, 200, raw="{not json")
    err = h.until(lambda: h.txt["error"].search(h.page_text()))
    empty = bool(h.txt["empty"].search(h.page_text()))
    return bool(err and not empty and not h.errors()), {"error_shown": bool(err), "claims_empty": empty, "js_errors": h.errors()}


@sc("A05", "adversarial", "markup in a returned label is rendered as text (no injected element or handler)")
def a05(h):
    h.load()
    lab = '<img src=x onerror="window.__m20xss=1">Injected Tern'
    h.focus_query(); h.b.type("sol")
    rs = h.wait_req("search")
    if not rs:
        return False, {"request": None}
    h.respond(rs[-1], 200, h.items([lab]))
    h.poll(0.8)
    d = h.js(f"({{xss: !!window.__m20xss, img: document.querySelectorAll({h.q('results')} + ' img').length}})")
    return (not d["xss"] and d["img"] == 0), d


@sc("A06", "adversarial", "slow response (4 s): loading stays indicated, no premature empty or error state")
def a06(h):
    h.load()
    h.focus_query(); h.b.type("sol")
    rs = h.wait_req("search")
    if not rs:
        return False, {"request": None}
    h.poll(4.0)
    t = h.page_text()
    loading = bool(h.txt["loading"].search(t)) or h.busy()
    premature = bool(h.txt["empty"].search(t) or h.txt["error"].search(t))
    for r in rs:
        h.respond(r, 200, h.items(["Late But Fine"]))
    return (loading and not premature), {"loading_at_4s": loading, "premature_empty_or_error": premature}


@sc("A07", "adversarial", "320px reflow (WCAG 1.4.10 width): no horizontal overflow")
def a07(h):
    return layout(h, 320)


@sc("A08", "adversarial", "double Enter on a pending save sends one request (or the control is disabled while pending)")
def a08(h):
    h.load()
    if not to_first_save(h):
        return False, {"save_control": "not reachable"}
    since = len(h.reqs)
    h.b.key("Enter")
    h.poll(0.1)
    busy = h.js("(() => { const a = document.activeElement; return !!a && (a.disabled || a.getAttribute('aria-disabled') === 'true' || a.getAttribute('aria-busy') === 'true'); })()")
    h.b.key("Enter")
    h.poll(0.5)
    n = len([r for r in h.reqs[since:] if r.kind == "save"])
    for r in h.pending("save"):
        h.respond(r, 200, h.ok_save())
    return n == 1, {"save_requests": n, "control_marked_busy_or_disabled_while_pending": bool(busy)}


@sc("A09", "adversarial", "network failure (fetch rejects) on search: error announced, no uncaught rejection")
def a09(h):
    h.load()
    h.focus_query(); h.b.type("sol")
    rs = h.wait_req("search")
    if not rs:
        return False, {"request": None}
    for r in rs:
        h.respond(r, 0)
    ann = h.until(lambda: h.announced("error"))
    return bool(ann and not h.errors()), {"announced": bool(ann), "js_errors": h.errors()}


def perf(h, reps, width):
    h.load(width=width)
    lat = []
    for i in range(reps):
        since = len(h.reqs)
        h.clear_and_type(f"p{i}x")
        rs = h.wait_req("search", since=since)
        if not rs:
            return None
        for r in rs[:-1]:
            h.respond(r, 200, h.items([]))
        lab = f"Perf Item {i} Q"
        t0 = time.perf_counter()
        h.respond(rs[-1], 200, h.items([lab] + [f"Filler {i}-{k}" for k in range(19)]))
        if not h.until(lambda: lab in h.shown(), 2.0):
            return None
        lat.append((time.perf_counter() - t0) * 1000)
    lat.sort()
    return {"width": width, "reps": reps, "median_ms": round(statistics.median(lat), 1), "p90_ms": round(lat[int(0.9 * (len(lat) - 1))], 1),
            "method": "oracle wall clock from response release to item text visible in DOM (20 items), polled over CDP; includes CDP overhead; same method for every subject"}


def main():
    a = sys.argv[1:]
    bpath, out = a[0], a[1]
    only = a[a.index("--only") + 1].split(",") if "--only" in a else None
    reps = int(a[a.index("--perf-reps") + 1]) if "--perf-reps" in a else 10
    binding = json.load(open(bpath))
    os.makedirs(out, exist_ok=True)
    h = H(binding, os.path.dirname(os.path.abspath(bpath)), out)
    h.shots = []
    res = []
    t_all = time.time()
    try:
        for sid, kind, title, f in SC:
            if only and sid not in only:
                continue
            t = time.time()
            try:
                ok, det = f(h)
            except Exception as e:
                ok, det = False, {"harness_or_page_exception": repr(e)[:300]}
            res.append({"id": sid, "kind": kind, "title": title, "result": {True: "PASS", False: "FAIL", None: "INCONCLUSIVE"}[ok if ok in (True, False, None) else bool(ok)],
                        "secs": round(time.time() - t, 2), "detail": det})
            print(f"{sid} {kind:11s} {res[-1]['result']:12s} {title}", flush=True)
        pm = [] if only else [perf(h, reps, w) for w in (360, 1280)]
    finally:
        ext = list(h.external)
        version = h.b.version
        h.close()
    core = [r for r in res if r["kind"] == "core"]
    rep = {"label": "Grok self-validation (M20 prep oracle); not independent review",
           "subject": binding.get("name"), "browser": version, "transport_mode": binding["transport"]["mode"],
           "interaction_proof": res,
           "core_pass": sum(r["result"] == "PASS" for r in core), "core_total": len(core),
           "adversarial_findings": [r["id"] for r in res if r["kind"] == "adversarial" and r["result"] == "FAIL"],
           "inconclusive": [r["id"] for r in res if r["result"] == "INCONCLUSIVE"],
           "external_requests_blocked": ext,
           "performance": pm,
           "screenshot_evidence": {"files": [os.path.basename(p) for p in h.shots],
                                   "note": "screenshots are visual evidence only; they prove nothing about interaction and no visual QA claim is made from them"},
           "secs": round(time.time() - t_all, 1)}
    rep["verdict_core"] = "PASS" if rep["core_pass"] == rep["core_total"] and not ext else "FAIL"
    json.dump(rep, open(os.path.join(out, "report.json"), "w"), indent=1)
    print(f"core {rep['core_pass']}/{rep['core_total']}  adversarial findings {rep['adversarial_findings']}  inconclusive {rep['inconclusive']}  external {len(ext)}  verdict_core {rep['verdict_core']}")
    for p in pm:
        print("perf", p)


if __name__ == "__main__":
    main()
