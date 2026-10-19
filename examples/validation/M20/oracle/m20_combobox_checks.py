#!/usr/bin/env python3
"""M20 combobox keyboard and focus checks (Grok self-validation, written after seeing G20, disclosed as such).
The prep oracle (m20_oracle.py) assumed a per-result save control; G20 is a combobox with focus kept on the input and
aria-activedescendant. These checks drive the same real headless Chrome with real key events (CDP) and take their
expectations from async-search-ui.md / the demo hint text: arrows move through results with wrap, Enter chooses,
Escape closes then clears, Tab does not select, focus is never dropped by a re-render, Retry is keyboard reachable.
Usage: m20_combobox_checks.py BINDING_ADAPTED BINDING_ASIS OUT_DIR"""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import m20_oracle as O
BA, BS, OUT = sys.argv[1:4]; os.makedirs(OUT, exist_ok=True)
res = []
def rec(i, ok, det, graded=True):
    res.append({"id": i, "result": ("PASS" if ok else "FAIL") if graded else "OBS", "detail": det})
    print(f"{i} {res[-1]['result']:4} {json.dumps(det)[:260]}", flush=True)
def st(h):
    return h.js("""(() => { const q = document.querySelector('#q'), ad = q.getAttribute('aria-activedescendant');
      const sel = Array.from(document.querySelectorAll('#results [aria-selected=true]')).map(e => e.innerText);
      return {focus: document.activeElement ? (document.activeElement.id || document.activeElement.tagName) : null, value: q.value,
              expanded: q.getAttribute('aria-expanded'), ad, ad_exists: ad ? !!document.getElementById(ad) : null, selected: sel,
              listHidden: document.querySelector('#results').hidden, chosen: document.querySelector('#chosen').innerText,
              fv: q.matches(':focus-visible'), outline: getComputedStyle(q).outlineStyle + ' ' + getComputedStyle(q).outlineWidth}; })()""")
b = json.load(open(BA)); h = O.H(b, os.path.dirname(os.path.abspath(BA)), OUT)
L = ["Heron Flats 41", "Kestrel Yard 7", "Marlin Dock 3"]
try:
    h.load(); h.js("document.activeElement && document.activeElement.blur()")
    n = h.tab_to("query", start_body=True); s = st(h)
    rec("K01", n is not None and s["focus"] == "q" and s["fv"] and s["outline"].split()[0] != "none", {"tabs": n, **{k: s[k] for k in ("focus", "fv", "outline")}})
    h.load(); ok, _ = h.search_ok("sol", L); h.b.key("ArrowDown"); s1 = st(h)
    rec("K02", ok and s1["focus"] == "q" and s1["expanded"] == "true" and s1["ad_exists"] and s1["selected"] == [L[0]], s1)
    h.b.key("ArrowUp"); s2 = st(h); h.b.key("ArrowUp"); s3 = st(h); h.b.key("Home"); s4 = st(h); h.b.key("End"); s5 = st(h)
    rec("K03", s2["selected"] == [L[2]] and s3["selected"] == [L[1]] and s4["selected"] == [L[0]] and s5["selected"] == [L[2]],
        {"up_from_first": s2["selected"], "up_again": s3["selected"], "home": s4["selected"], "end": s5["selected"]})
    h.b.key("Enter"); s6 = st(h)
    rec("K04", s6["value"] == L[2] and L[2] in s6["chosen"] and s6["expanded"] == "false" and s6["focus"] == "q" and not s6["ad"], s6)
    h.load(); ok, _ = h.search_ok("sol", L); h.b.key("Escape"); e1 = st(h); h.b.key("Escape"); h.poll(0.3); e2 = st(h)
    rec("K05", ok and e1["expanded"] == "false" and e1["value"] == "sol" and e2["value"] == "" and e2["focus"] == "q", {"first_escape": e1, "second_escape": e2})
    h.load(); ok, _ = h.search_ok("sol", L); h.b.key("ArrowDown"); h.b.key("Tab"); h.poll(0.2); t = st(h)
    rec("K06", ok and t["value"] == "sol" and t["chosen"] == "" and t["expanded"] == "false", t)
    # focus recovery: active option, more typing, results re-render
    h.load(); ok, _ = h.search_ok("so", L); h.b.key("ArrowDown"); before = st(h)
    since = len(h.reqs); h.b.type("l"); rs = h.wait_req("search", since=since); mid = st(h)
    if rs: h.respond(rs[-1], 200, h.items(["Plover Steps 2", "Tern Row 5"]))
    h.until(lambda: "Plover Steps 2" in h.shown()); h.poll(0.3); after = st(h)
    rec("K07", ok and bool(rs) and after["focus"] == "q" and (after["ad"] is None or after["ad_exists"]) and after["selected"] == [],
        {"before": before, "while_pending": mid, "after_rerender": after})
    # stale response while an option is active: the late older answer must not change rows or leave a dangling activedescendant
    rr = O.two_requests(h)
    if rr:
        a, bq = rr; h.respond(bq, 200, h.items(L)); h.until(lambda: L[0] in h.shown()); h.b.key("ArrowDown"); h.b.key("ArrowDown")
        x = st(h); h.respond(a, 200, h.items(["Stale One", "Stale Two", "Stale Three", "Stale Four"])); h.poll(0.6); y = st(h)
        rec("K08", "Stale" not in h.shown() and y["selected"] == x["selected"] == [L[1]] and y["ad_exists"], {"before_late": x, "after_late": y})
    else:
        rec("K08", False, {"requests": "fewer than 2"})
    # Retry by keyboard after an error: Retry reachable by Tab, Enter re-runs, focus goes back to the input
    h.load(); h.focus_query(); h.b.type("sol"); rs = h.wait_req("search")
    for r in rs: h.respond(r, 500, {"error": "x"})
    h.until(lambda: h.announced("error")); h.sel["_retry"] = "#retry"; n = h.tab_to("_retry", start_body=True)
    since = len(h.reqs)
    if n: h.b.key("Enter")
    rs2 = h.wait_req("search", since=since); f = st(h)
    if rs2: h.respond(rs2[-1], 200, h.items(L))
    ok2 = h.until(lambda: L[0] in h.shown() and h.js("document.querySelector('#error').hidden"))
    rec("K09", bool(n) and bool(rs2) and f["focus"] == "q" and bool(ok2), {"tabs_to_retry": n, "retry_request": bool(rs2), "focus_after_retry": f["focus"], "recovered": bool(ok2)})
    # keys with no results do nothing and throw nothing
    h.load(); h.focus_query()
    for k in ("ArrowDown", "ArrowUp", "Enter", "Home", "End", "PageDown"): h.b.key(k)
    z = st(h); rec("K10", z["value"] == "" and not z["ad"] and not h.errors(), dict(z, js_errors=h.errors()))
    h.close()
    # the page exactly as shipped: its own random-latency backend and fail switch
    b2 = json.load(open(BS)); h = O.H(b2, os.path.dirname(os.path.abspath(BS)), OUT)
    h.load(); h.focus_query(); h.b.type("invoice")
    got = h.until(lambda: "nvoice" in h.shown(), 3.0); opts = (h.shown() or "").split("\n")
    rec("S01", bool(got) and all("invoice" in o.lower() for o in opts if o), {"options": len([o for o in opts if o]), "first": opts[:3]})
    h.b.key("ArrowDown"); h.b.key("Enter"); c = st(h)
    rec("S02", c["value"] == opts[0] and opts[0] in c["chosen"] and c["focus"] == "q", c)
    # fail switch via keyboard (Space on the checkbox), then a search: alert with Retry, Retry recovers
    h.load(); h.sel["_fail"] = "#fail"; nf = h.tab_to("_fail", start_body=True); h.b.key(" "); h.poll(0.1)
    checked = h.js("document.querySelector('#fail').checked"); h.focus_query(); h.b.type("billing")
    alert = h.until(lambda: not h.js("document.querySelector('#error').hidden"), 3.0)
    h.sel["_retry"] = "#retry"; nr = h.tab_to("_retry", start_body=True)
    if nr: h.b.key("Enter")
    rec_ok = h.until(lambda: "illing" in h.shown() and h.js("document.querySelector('#error').hidden"), 3.0)
    rec("S03", bool(nf) and checked and bool(alert) and bool(nr) and bool(rec_ok), {"fail_switch_tabs": nf, "checked_by_space": checked,
        "alert_shown": bool(alert), "retry_tabs": nr, "recovered": bool(rec_ok), "status": h.js("document.querySelector('#status').innerText")})
    # random latency: type quickly, then let all answers land; the final rows match the final text
    h.load(); h.focus_query()
    for ch in "card": h.b.type(ch); h.poll(0.2)
    h.poll(1.6); fin = [o for o in (h.shown() or "").split("\n") if o]
    rec("S04", bool(fin) and all("card" in o.lower() for o in fin), {"final_rows": len(fin), "sample": fin[:3], "note": "random latency; one run, not a proof"})
    rec("S05", not h.errors() and not h.external, {"js_errors": h.errors(), "external_requests": h.external}, graded=True)
finally:
    try: h.close()
    except Exception: pass
g = [r for r in res if r["result"] != "OBS"]
json.dump({"label": "Grok self-validation; not independent review", "checks": res}, open(os.path.join(OUT, "combobox.json"), "w"), indent=1)
print("COMBOBOX %d/%d FAILS %s" % (sum(r["result"] == "PASS" for r in g), len(g), [r["id"] for r in g if r["result"] == "FAIL"]))
