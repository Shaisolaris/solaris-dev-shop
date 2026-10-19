#!/usr/bin/env python3
"""M20 (Grok self-validation): distinguishing inputs for teeth survivors wrap_off and aria_busy_off, run on the candidate and
on each mutant in real headless Chrome. Usage: survivor_distinguish_m20.py ADAPT_TREE OUT.json"""
import json, os, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import m20_oracle as O
AT, OUT = sys.argv[1:3]
CORE = "employees/engineering/frontend-developer/async_search_core.js"; PAGE = "examples/capabilities/G20/demo/adapted.html"
MUT = {"wrap_off": (CORE, "(active + 1) % n", "Math.min(active + 1, n - 1)"),
       "aria_busy_off": (PAGE, "list.setAttribute(\"aria-busy\", next.busy ? \"true\" : \"false\");", "list.setAttribute(\"aria-busy\", \"false\");")}
res = {}
for name in ["cand"] + list(MUT):
    d = f"/tmp/m20-dist-{name}"; shutil.rmtree(d, ignore_errors=True); shutil.copytree(AT, d)
    if name != "cand":
        f, a, b = MUT[name]; p = os.path.join(d, f); s = open(p).read(); assert s.count(a) == 1; open(p, "w").write(s.replace(a, b))
    bd = os.path.join(d, "binding-adapted.json"); h = O.H(json.load(open(bd)), d, d)
    try:
        h.load(); ok, _ = h.search_ok("sol", ["One A", "Two B", "Three C"])
        for _ in range(4): h.b.key("ArrowDown")
        down4 = h.js("Array.from(document.querySelectorAll('#results [aria-selected=true]')).map(e => e.innerText)")
        h.load(); h.focus_query(); h.b.type("sol"); rs = h.wait_req("search")
        busy = h.js("document.querySelector('#results').getAttribute('aria-busy')")
        for r in rs: h.respond(r, 200, h.items(["X"]))
        res[name] = {"after_4_arrowdown_on_3": down4, "aria_busy_while_pending": busy}
    finally:
        h.close(); shutil.rmtree(d, ignore_errors=True)
    print(name, res[name], flush=True)
json.dump(res, open(OUT, "w"), indent=1)
