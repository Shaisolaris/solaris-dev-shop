#!/usr/bin/env python3
"""M39 r3 probes (Grok self-validation, not independent review). Spellings and paths the r3 fix for M39 r2 P2-1 did
not name, plus the status of M39 r2 P3-1..P3-3. Reuses the M39 r2 contract oracle helpers unchanged (source above its
first row). R rows are scored (a pass means the change is caught or refused); Q rows are observations.
Usage: PY m39r3_probe.py SRC OUT.json [--tool PATH]."""
import os, sys, json, tempfile
_here = os.path.dirname(os.path.abspath(__file__))
_src = open(os.path.join(_here, "m39r2_contract.py")).read()
exec(compile(_src[: _src.index("@safe\ndef c01")], "m39r2_contract_helpers", "exec"))

def recgo(setup, cmd, mutate, extra=()):
    b = B2(); b.order()
    if setup: setup(b)
    k = b.rd(cmd(b) if callable(cmd) else cmd, extra=extra); g0 = b.go()
    rec = json.loads(b.lines()[-1]) if k[0] == 0 else {}
    mutate(b); g1 = b.go(); b.close()
    return k, g0, g1, rec

def caught(k, g0, g1):
    return (k[0] == 2 and "Traceback" not in k[2]) or (k[0] == 0 and g0[1] == "GO" and g1[1] != "GO")

@safe
def r01():
    k, g0, g1, rec = recgo(None, ["inp/../inp/a.csv"], lambda b: w(b, "inp/a.csv", "id,v\n1,11\n"))
    row("R01 an input spelled with a dot-dot segment inside ROOT (inp/../inp/a.csv) is bound or refused",
        caught(k, g0, g1), {"caught": (caught(k, g0, g1), (k[0], g0[:3], g1[:3])), "claimed_inputs": rec.get("claimed_inputs", rec.get("inputs"))})

@safe
def r02():
    ext = tempfile.mkdtemp(prefix="m39r3-ext-"); f = os.path.join(ext, "e.csv"); open(f, "w").write("id,v\n5,5\n")
    k, g0, g1, rec = recgo(lambda b: os.symlink(f, b.p("inp", "ext.csv")), ["inp"], lambda b: open(f, "w").write("id,v\n5,6\n"))
    row("R02 a named folder holding a symlink to a file outside ROOT: refused at record, or the outside change is caught",
        caught(k, g0, g1), {"caught": (caught(k, g0, g1), (k[0], g0[:3], g1[:3], k[2].strip()[-160:]))})

@safe
def r03():
    k, g0, g1, rec = recgo(lambda b: os.symlink("inp", b.p("lnk")), ["lnk/a.csv"], lambda b: w(b, "inp/a.csv", "id,v\n1,11\n"))
    row("R03 an input reached through a symlinked parent folder (lnk/a.csv, lnk -> inp) is bound or refused",
        caught(k, g0, g1), {"caught": (caught(k, g0, g1), (k[0], g0[:3], g1[:3], k[2].strip()[-160:]))})

@safe
def r04():
    def retarget(b):
        os.makedirs(b.p("inp2")); w(b, "inp2/a.csv", "id,v\n1,77\n"); os.remove(b.p("lnk")); os.symlink("inp2", b.p("lnk"))
    k, g0, g1, rec = recgo(lambda b: os.symlink("inp", b.p("lnk")), ["lnk/a.csv"], retarget)
    row("R04 retargeting that symlinked parent to other content is caught (or the record was refused)",
        caught(k, g0, g1), {"caught": (caught(k, g0, g1), (k[0], g0[:3], g1[:3]))})

@safe
def r05():
    k, g0, g1, rec = recgo(None, ["./inp/a.csv"], lambda b: w(b, "inp/a.csv", "id,v\n1,11\n"))
    row("R05 ./inp/a.csv is bound", caught(k, g0, g1), {"caught": (caught(k, g0, g1), (k[0], g0[:3], g1[:3]))})

@safe
def r06():
    k, g0, g1, rec = recgo(None, ["../d/inp/a.csv"], lambda b: w(b, "inp/a.csv", "id,v\n1,11\n"))
    row("R06 an input spelled through the parent of ROOT (../d/inp/a.csv, still inside ROOT) is bound or refused",
        caught(k, g0, g1), {"caught": (caught(k, g0, g1), (k[0], g0[:3], g1[:3])), "claimed_inputs": rec.get("claimed_inputs", rec.get("inputs"))})

@safe
def q05():
    ext = tempfile.mkdtemp(prefix="m39r3-abs-"); f = os.path.join(ext, "o.csv"); open(f, "w").write("id,v\n8,8\n")
    k, g0, g1, rec = recgo(None, [f], lambda b: open(f, "w").write("id,v\n8,9\n"))
    row("Q05 an absolute input outside ROOT (documented: cannot be re-checked) - verdict after it changes, and whether the record says so",
        True, {"record_exit": k[0], "go_before": g0[:3], "go_after": g1[:3], "record_mentions_outside": "outside" in json.dumps(rec).lower() or "unbound" in json.dumps(rec).lower()})

@safe
def q06():
    # M39 r2 P3-2: an input the run itself rewrites
    b = B2(); b.order()
    open(b.p("bin", "rewriter.py"), "w").write("import sys\nopen(sys.argv[1],'a').write('more\\n')\nopen(sys.argv[2],'w').write('x\\n')\n")
    k = b.rec(SCR, ["reports/r.txt"], ["bin/rewriter.py", "inp/a.csv", "reports/r.txt"]); g = b.go()
    rec = json.loads(b.lines()[-1]) if k[0] == 0 else {}; b.close()
    row("Q06 (M39 r2 P3-2) an input rewritten by the run: verdict and how the record shows it", True,
        {"record_exit": k[0], "verdict": g[:3], "inputs_changed_during_run": rec.get("inputs_changed_during_run")})

@safe
def q07():
    # M39 r2 P3-3: verify exit codes for GO_WITH_GAPS
    b = B2(); b.order(); ENV["M39R2_EXIT"] = "1"
    k = b.rd(["inp/a.csv"], ok_exit="0,1"); ENV.pop("M39R2_EXIT")
    rc, j, e = b.verify(b.cl(gaps=True, name="g.json")); b.close()
    row("Q07 (M39 r2 P3-3) verify exit code when the verdict is GO_WITH_GAPS", True, {"record_exit": k[0], "verify_rc": rc, "verdict": j.get("verdict")})

for f in (r01, r02, r03, r04, r05, r06, q05, q06, q07):
    f()
scored = [r for r in ROWS if r["row"][0] == "R"]
json.dump({"rows": ROWS}, open(OUT, "w"), indent=1, default=str)
print("M39R3 PROBES %d/%d" % (sum(r["pass"] for r in scored), len(scored)))
