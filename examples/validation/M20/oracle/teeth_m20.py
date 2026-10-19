#!/usr/bin/env python3
"""M20 browser teeth (Grok self-validation). Mutants of the G20 core and demo page, applied to a copy of the adapter tree,
scored by the prep oracle (m20_oracle.py) and the combobox checks in real headless Chrome. A kill is any check whose
result differs from the unmutated candidate. Usage: teeth_m20.py ADAPT_TREE BASE_ORACLE_JSON BASE_COMBO_JSON OUT i/n"""
import json, os, shutil, subprocess, sys
here = os.path.dirname(os.path.abspath(__file__))
AT, BO, BC, OUT, SH = sys.argv[1:6]; os.makedirs(OUT, exist_ok=True)
CORE = "employees/engineering/frontend-developer/async_search_core.js"; PAGE = "examples/capabilities/G20/demo/adapted.html"
SHIP = "examples/capabilities/G20/demo/index.html"
M = [
 ("stale_guard_off", CORE, "if (id !== seq || id !== pending) { s.staleDropped++; return; }", "if (false) { s.staleDropped++; return; }"),
 ("supersede_no_bump_EQUIV?", CORE, "if (pending) { stopInFlight(); seq++; }", "if (pending) { stopInFlight(); }"),
 ("wrap_off", CORE, "(active + 1) % n", "Math.min(active + 1, n - 1)"),
 ("escape_clear_off", CORE, "} else { r.clearInput = true; }", "} else { }"),
 ("onresults_keeps_active", CORE, "return { open: !!(st && st.open) && n > 0, active: -1 };", "return { open: !!(st && st.open) && n > 0, active: st && st.active >= 0 ? st.active : -1 };"),
 ("timeout_off", CORE, "deadline = opts.schedule(function () { deadline = null;", "deadline = null && opts.schedule(function () { deadline = null;"),
 ("retry_focus_off", "PAGE", "retry.addEventListener(\"click\", function () { c.retry(); q.focus(); });", "retry.addEventListener(\"click\", function () { c.retry(); });"),
 ("live_region_off", "PAGE", "if (said) status.textContent = said;", "if (false) status.textContent = said;"),
 ("activedescendant_off", "PAGE", "q.setAttribute(\"aria-activedescendant\", opts[ui.active].id);", ""),
 ("label_innerhtml", "PAGE", "li.textContent = r.label;", "li.innerHTML = r.label;"),
 ("aria_busy_off", "PAGE", "list.setAttribute(\"aria-busy\", next.busy ? \"true\" : \"false\");", "list.setAttribute(\"aria-busy\", \"false\");"),
 ("focus_outline_off", "PAGE", "#q:focus-visible, button:focus-visible { outline: 3px solid var(--sol-ink-2); outline-offset: 2px; }", "#q:focus-visible, button:focus-visible { outline: none; }"),
]
i, n = map(int, SH.split("/"))
bo = {r["id"]: r["result"] for r in json.load(open(BO))["interaction_proof"]}
bc = {r["id"]: r["result"] for r in json.load(open(BC))["checks"]}
rows = []
for name, f, old, new in M[i::n]:
    d = f"/tmp/m20-mut-{name.replace('?', '')}"; shutil.rmtree(d, ignore_errors=True); shutil.copytree(AT, d)
    files = [CORE] if f == CORE else [PAGE, SHIP]
    cnt = []
    for rel in files:
        p = os.path.join(d, rel); s = open(p).read(); cnt.append(s.count(old))
        if s.count(old) == 1: open(p, "w").write(s.replace(old, new))
    if cnt[0] != 1:
        rows.append({"mutant": name, "error": f"anchor count {cnt}"}); continue
    od, cd = os.path.join(OUT, name.replace('?', '') + "-oracle"), os.path.join(OUT, name.replace('?', '') + "-combo")
    subprocess.run([sys.executable, os.path.join(here, "m20_oracle.py"), os.path.join(d, "binding-adapted.json"), od, "--perf-reps", "1"], capture_output=True, text=True, timeout=400)
    subprocess.run([sys.executable, os.path.join(here, "m20_combobox_checks.py"), os.path.join(d, "binding-adapted.json"), os.path.join(d, "binding-asis.json"), cd], capture_output=True, text=True, timeout=400)
    try:
        mo = {r["id"]: r["result"] for r in json.load(open(os.path.join(od, "report.json")))["interaction_proof"]}
    except Exception as e:
        mo = {"ERR": repr(e)[:60]}
    try:
        mc = {r["id"]: r["result"] for r in json.load(open(os.path.join(cd, "combobox.json")))["checks"]}
    except Exception as e:
        mc = {"ERR": repr(e)[:60]}
    ko = sorted(k for k in set(bo) | set(mo) if bo.get(k) != mo.get(k)); kc = sorted(k for k in set(bc) | set(mc) if bc.get(k) != mc.get(k))
    rows.append({"mutant": name, "file": "core" if f == CORE else "page", "anchors": cnt, "oracle_kills": ko, "combobox_kills": kc})
    for sub in (od, cd):
        for fn in os.listdir(sub):
            if fn.endswith(".png"): os.remove(os.path.join(sub, fn))  # screenshots of mutants are not kept
    print(json.dumps(rows[-1]), flush=True); shutil.rmtree(d, ignore_errors=True)
json.dump(rows, open(os.path.join(OUT, f"teeth-{i}.json"), "w"), indent=1); print("DONE")
