#!/usr/bin/env python3
"""M20 (Grok self-validation): bind the M20 prep oracle to the G20 demo without editing the candidate.
The demo has no HTTP backend: it calls an inline fakeFetch(query, o) with random latency. The oracle must control every
response (order, status, timing), so this writes a scratch copy (OUT) of exactly the two files the page loads plus the
page, and replaces ONLY the body of fakeFetch with a call to the oracle's fixture-transport global. Everything else on
the page (render, keyboard handler, live region, Retry, CSS) and the core file are byte-identical to the candidate.
It also writes binding-asis.json for the page exactly as shipped (its own fakeFetch). Usage: make_adapter_m20.py TREE OUT"""
import hashlib, json, os, shutil, sys
T, OUT = sys.argv[1:3]
CORE = "employees/engineering/frontend-developer/async_search_core.js"
DEMO = "examples/capabilities/G20/demo"
for rel in (CORE, DEMO + "/index.html", DEMO + "/fixture-data.js"):
    os.makedirs(os.path.dirname(os.path.join(OUT, rel)), exist_ok=True); shutil.copy2(os.path.join(T, rel), os.path.join(OUT, rel))
src = open(os.path.join(T, DEMO, "index.html")).read()
a = src.index("  function fakeFetch(query, o) {"); b = src.index("  function render(next) {")
new = ("  function fakeFetch(query, o) {  // M20 ADAPTER (Grok, not the candidate): the oracle answers every request\n"
       "    return window.__M20_FETCH({ url: '/api/search?q=' + encodeURIComponent(query) }).then(function (r) {\n"
       "      if (!r.ok) throw new Error('the fixture backend returned ' + r.status);\n"
       "      return r.json();\n"
       "    }).then(function (d) { return d.results; });\n"
       "  }\n")
adapted = src[:a] + new + src[b:]
open(os.path.join(OUT, DEMO, "adapted.html"), "w").write(adapted)
sel = {"query": "#q", "results": "#results", "item": "#results [role=option]", "save": "#results [role=option]", "status": "#status"}
base = {"page": {"serve_dir": ".", "path": DEMO + "/adapted.html"},
        "transport": {"mode": "global", "name": "__M20_FETCH", "search_url_regex": "/api/search\\?", "save_url_regex": "/api/save-not-in-g20", "query_from": "param:q"},
        "search_response": {"items_key": "results", "item_template": {"id": "{id}", "label": "{label}"}}, "selectors": sel}
json.dump(dict(base, name="G20 8d45038 demo, fakeFetch body swapped for the oracle transport (Grok adapter)"), open(os.path.join(OUT, "binding-adapted.json"), "w"), indent=1)
json.dump(dict(base, name="G20 8d45038 demo as shipped (own random-latency fakeFetch)", page={"serve_dir": ".", "path": DEMO + "/index.html"}),
          open(os.path.join(OUT, "binding-asis.json"), "w"), indent=1)
removed = src[a:b]
print("adapter: replaced %d chars (fakeFetch only); rest of page identical: %s" % (len(removed), src[:a] + src[b:] == adapted[:a] + adapted[a + len(new):]))
print("removed block sha256 %s" % hashlib.sha256(removed.encode()).hexdigest()[:16])
