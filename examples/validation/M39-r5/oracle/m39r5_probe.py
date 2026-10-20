#!/usr/bin/env python3
"""M39 r5 probes (Grok self-validation, not independent review) for the older M39 r2 P3-2 (an input the run rewrote
was a plain GO) and P3-3 (verify exit 0 for GO_WITH_GAPS and EVIDENCED_NO_ORDER). Self-contained: a tool script in
bin/, a delivered G04 work order from the G39 fixtures, and spellings the G39 r5 tests do not use (--flag=VALUE, a
folder through --inputs, a removed file, a -journal sidecar, an untouched -shm). T rows are scored.
Usage: PY m39r5_probe.py SRC OUT.json [--tool PATH]."""
import json, os, shutil, subprocess, sys, tempfile
SRC = os.path.abspath(sys.argv[1]); OUT = sys.argv[2]; PY = sys.executable
TOOL = os.path.join(SRC, "employees/product-project/delivery-lead/delivery_evidence.py")
if "--tool" in sys.argv: TOOL = os.path.abspath(sys.argv[sys.argv.index("--tool") + 1])
HANDOFF = os.path.join(SRC, "employees/infrastructure/fleet-dispatcher/handoff.py")
FX = os.path.join(SRC, "examples/capabilities/G39/fixtures")
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
ROLE = "data/data-analyst"
rows = []

def row(name, ok, detail):
    rows.append({"row": name, "pass": bool(ok), "detail": detail}); print("%s %s %s" % ("PASS" if ok else "FAIL", name, json.dumps(detail)[:300]))

class Box:
    def __init__(self):
        self.t = tempfile.mkdtemp(prefix="m39r5-"); self.r = os.path.join(self.t, "dl"); os.makedirs(os.path.join(self.r, "bin"))
        open(os.path.join(self.r, "bin", "job.py"), "w").write(
            "import os, sys\nmode, out = sys.argv[1], sys.argv[-1]\nsrc = [a.split('=', 1)[1] for a in sys.argv if a.startswith('--src=')]\n"
            "if mode == 'append': open(src[0], 'a').write('9,9\\n')\n"
            "if mode == 'remove': os.remove('feed/old.csv')\n"
            "if mode == 'journal': open('feed/t.db-journal', 'w').write('j2')\n"
            "if mode == 'shmnew': open('feed/t.db-shm', 'w').write('s2'); open('feed/fresh.csv', 'w').write('n')\n"
            "open(out, 'w').write('report\\n')\n")
        for f in ("intake.json", "order.json"): shutil.copy2(os.path.join(FX, f), os.path.join(self.r, f))
        os.makedirs(os.path.join(self.r, "feed")); self.w("inp.csv", "id,v\n1,1\n")
        for f, t in (("t.db", "d"), ("t.db-shm", "s"), ("t.db-journal", "j"), ("old.csv", "o")): self.w("feed/" + f, t)
    def w(self, rel, t): open(os.path.join(self.r, rel), "w").write(t)
    def run(self, *a):
        p = subprocess.run([PY] + [str(x) for x in a], cwd=self.r, capture_output=True, text=True, env=ENV, timeout=300)
        return p.returncode, p.stdout, p.stderr
    def deliver(self): return self.run(HANDOFF, "run", "order.json", "--worker", "ana")[0]
    def rec(self, mode, extra=()):
        return self.run(TOOL, "record", ".", "--role", ROLE, *extra, "--outputs", "rep.txt", "--", PY, "bin/job.py", mode, "--src=inp.csv", "rep.txt")[0]
    def last(self): return json.loads(open(os.path.join(self.r, ".delivery/contributions.jsonl")).read().splitlines()[-1])
    def verify(self, order=True, accept=False, strict=False, text=False):
        c = {"schema": "solaris.delivery-claims/1", "contributions": [{"role": ROLE, "outputs": ["rep.txt"], "accept_gaps": accept}]}
        if order: c["order"] = "order.json"
        open(os.path.join(self.r, "cl.json"), "w").write(json.dumps(c))
        rc, o, e = self.run(TOOL, "verify", ".", "--claims", "cl.json", *([] if text else ["--json"]) + (["--strict"] if strict else []))
        if text: return rc, o + e
        try: j = json.loads(o)
        except ValueError: j = {}
        return rc, j
    def close(self): shutil.rmtree(self.t, ignore_errors=True)

def safe(f):
    def g():
        try: f()
        except Exception as e: row(f.__name__.upper() + " crashed", False, {"error": "%s: %s" % (type(e).__name__, str(e)[:200])})
    g.__name__ = f.__name__; return g

def st(j): return ((j.get("contributions") or [{}])[0]).get("state")

@safe
def t01():
    b = Box(); dl = b.deliver(); k = b.rec("append")
    n_rc, n = b.verify(); a_rc, a = b.verify(accept=True); x_rc, x = b.verify(accept=True, text=True); b.close()
    ok = dl == 0 and k == 0 and (n_rc, n.get("verdict"), st(n)) == (1, "NO_GO", "evidenced_with_gaps") and \
        (a_rc, a.get("verdict")) == (0, "GO_WITH_GAPS") and "inp.csv" in x and "GO_WITH_GAPS" in x
    row("T01 --src=inp.csv rewritten by the run, delivered order: NO_GO without accept_gaps, GO_WITH_GAPS with it, text names the file, never GO", ok,
        {"deliver": dl, "rec": k, "no_accept": [n_rc, n.get("verdict"), st(n)], "accept": [a_rc, a.get("verdict")], "text_names_file": "inp.csv" in x})

@safe
def t02():
    b = Box(); b.deliver(); k = b.rec("remove", ["--inputs", "feed"]); r = b.last(); rc, j = b.verify(accept=True); b.close()
    ok = k == 0 and "feed/old.csv" in (r.get("inputs_changed_during_run") or []) and j.get("verdict") == "GO_WITH_GAPS" and \
        "feed/old.csv" in json.dumps(j.get("contributions"))
    row("T02 a file in an --inputs folder removed by the run is a named gap (GO_WITH_GAPS with accept_gaps)", ok,
        {"rec": k, "changed": r.get("inputs_changed_during_run"), "verdict": [rc, j.get("verdict")]})

@safe
def t03():
    b = Box(); b.deliver(); k = b.rec("journal", ["--inputs", "feed"]); rc, j = b.verify(); b.close()
    ok = k == 0 and (rc, j.get("verdict"), st(j)) == (1, "NO_GO", "evidenced_with_gaps")
    row("T03 a SQLite -journal sidecar rewritten by the run holds data, so it is a gap (NO_GO without accept_gaps)", ok, {"rec": k, "verdict": [rc, j.get("verdict"), st(j)]})

@safe
def t04():
    b = Box(); b.deliver(); k = b.rec("shmnew", ["--inputs", "feed"]); r = b.last(); rc, j = b.verify(); b.close()
    ok = k == 0 and (rc, j.get("verdict"), st(j)) == (0, "GO", "evidenced") and set(r.get("inputs_changed_during_run") or []) >= {"feed/t.db-shm", "feed/fresh.csv"}
    row("T04 false-positive guard: a -shm index next to a bound db and a file that appeared during the run are listed but are not gaps (GO)", ok,
        {"rec": k, "changed": r.get("inputs_changed_during_run"), "verdict": [rc, j.get("verdict"), st(j)]})

@safe
def t05():
    b = Box(); b.deliver(); b.rec("plain"); go = b.verify(strict=True); nord = b.verify(order=False, strict=True)
    b.rec("append"); gaps = b.verify(accept=True, strict=True); nogo = b.verify(strict=True)
    os.remove(os.path.join(b.r, "cl.json")); inv = b.run(TOOL, "verify", ".", "--claims", "cl.json", "--strict")[0]; b.close()
    got = {"GO": [go[0], go[1].get("verdict")], "EVIDENCED_NO_ORDER": [nord[0], nord[1].get("verdict")], "GO_WITH_GAPS": [gaps[0], gaps[1].get("verdict")],
           "NO_GO": [nogo[0], nogo[1].get("verdict")], "invalid": inv}
    ok = got == {"GO": [0, "GO"], "EVIDENCED_NO_ORDER": [4, "EVIDENCED_NO_ORDER"], "GO_WITH_GAPS": [3, "GO_WITH_GAPS"], "NO_GO": [1, "NO_GO"], "invalid": 2}
    row("T05 verify --strict: 0 only for GO; 3 GO_WITH_GAPS, 4 EVIDENCED_NO_ORDER, 1 NO_GO, 2 invalid", ok, got)

@safe
def t06():
    b = Box(); b.deliver(); b.rec("plain"); g = b.verify(); n = b.verify(order=False)
    cmd = [PY, "-c", "import sys;open('rep.txt','w').write('r');sys.exit(1)"]
    b.run(TOOL, "record", ".", "--role", ROLE, "--ok-exit", "0,1", "--outputs", "rep.txt", "--", *cmd); w = b.verify(accept=True); b.close()
    got = [[g[0], g[1].get("verdict")], [n[0], n[1].get("verdict")], [w[0], w[1].get("verdict")]]
    ok = got == [[0, "GO"], [0, "EVIDENCED_NO_ORDER"], [0, "GO_WITH_GAPS"]]
    row("T06 compatibility control: without --strict the exit mapping is unchanged (0 for GO, EVIDENCED_NO_ORDER, GO_WITH_GAPS)", ok, got)

@safe
def t07():
    b = Box(); b.deliver(); k = b.rec("plain"); rc, j = b.verify(); b.close()
    ok = k == 0 and (rc, j.get("verdict"), st(j)) == (0, "GO", "evidenced")
    row("T07 control: a run that reads its inputs without changing them is a clean GO", ok, {"rec": k, "verdict": [rc, j.get("verdict"), st(j)]})

for f in (t01, t02, t03, t04, t05, t06, t07): f()
n = sum(r["pass"] for r in rows)
json.dump({"probe": "m39r5", "tool": TOOL, "python": sys.version.split()[0], "rows": rows, "score": "%d/%d" % (n, len(rows))}, open(OUT, "w"), indent=1)
print("M39R5 PROBES %d/%d" % (n, len(rows)))
