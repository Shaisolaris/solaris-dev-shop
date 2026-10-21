#!/usr/bin/env python3
"""M32 r5 probe (Grok self-validation, not independent review). Written for this pass from M32 r3 P4 (the doc said a
CRM merge keeps the suppression, but suppression is keyed by handle). Checks that G32 r5 changes no behaviour (code
equal to r4 once docstrings are removed) and that what the doc now says holds. Inputs chosen here.
Usage: PY m32r5_probe.py REPO OUT.json [R4_TOOL_COPY]"""
import ast, json, os, shutil, subprocess, sys, tempfile
from pathlib import Path
REPO = Path(sys.argv[1]).resolve(); OUT = sys.argv[2]; R4 = Path(sys.argv[3]) if len(sys.argv) > 3 else None
TOOL = REPO / "employees/sales-outreach/customer-success/followthrough.py"; DOC = TOOL.parent / "consent-follow-through.md"
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1"); ROWS = []
def row(rid, name, ok, detail): ROWS.append({"row": rid, "name": name, "pass": bool(ok), "detail": detail})
def strip_doc(src):
    t = ast.parse(src)
    for n in ast.walk(t):
        if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)) and n.body and isinstance(n.body[0], ast.Expr) \
                and isinstance(getattr(n.body[0], "value", None), ast.Constant) and isinstance(n.body[0].value.value, str):
            n.body = n.body[1:] or [ast.Pass()]
    return ast.dump(t)
if R4 and R4.is_file():
    same = strip_doc(TOOL.read_text()) == strip_doc(R4.read_text())
    row("R01", "followthrough.py equals G32 r4 once docstrings are removed (no behaviour change)", same, same)
doc = DOC.read_text(); mod = TOOL.read_text()
row("R02", "doc and module docstring both say the stored suppression is keyed by handle", "follows the handle, not the record id" in doc and "keyed by handle" in mod,
    ["follows the handle, not the record id" in doc, "keyed by handle" in mod])
T = Path(tempfile.mkdtemp(prefix="m32r5-")); S = T / "state"; n = [0]
def run(contacts, events, now="2026-07-01T00:00:00+00:00"):
    n[0] += 1; a = T / ("a%d.json" % n[0]); e = T / ("e%d.jsonl" % n[0])
    a.write_text(json.dumps({"schema": "solaris.cs-account/1", "account_id": "acc-7", "owner": "cs-lead", "contacts": contacts}))
    e.write_text("".join(json.dumps(x) + "\n" for x in events))
    p = subprocess.run([sys.executable, str(TOOL), "run", str(S), "--account", str(a), "--events", str(e), "--now", now, "--worker", "w%d" % n[0], "--json"],
                       capture_output=True, text=True, env=ENV, timeout=120)
    try: return p.returncode, json.loads(p.stdout)
    except ValueError: return p.returncode, {"_raw": (p.stdout + p.stderr)[-200:]}
def C(cid, h): return {"id": cid, "name": "Kim", "handle": h, "consent": "granted"}
def signup(eid, cid): return {"id": eid, "type": "signup", "contact": cid, "at": "2026-06-01T00:00:00+00:00"}
rc, j = run([C("k1", "crm:kim-7")], [signup("s1", "k1"), {"id": "o1", "type": "opt_out", "contact": "k1", "scope": "all", "at": "2026-06-02T00:00:00+00:00"}])
row("R03", "setup: opt-out all suppresses k1", rc == 0 and j.get("suppressed_contacts") == ["k1"], [rc, j.get("suppressed_contacts")])
res = {}
for i, h in enumerate(["CRM:Kim-7", " crm:kim-7 ", "crm:k\u200bim-7", "\uff43rm:kim-7"]):
    rc, j = run([C("k-m%d" % i, h)], [signup("s-m%d" % i, "k-m%d" % i)])
    res[repr(h)] = [rc, j.get("suppressed_contacts"), len(j.get("drafted", []))]
row("R04", "merged record keeping the handle (case, spaces, zero-width, fullwidth): stays suppressed, nothing drafted",
    all(v[0] == 0 and v[2] == 0 and v[1] for v in res.values()), res)
rc, j = run([C("k-new", "crm:kim-seven")], [signup("s-new", "k-new")])
row("R05", "as documented: a new handle with the history dropped is a new person (welcome drafted)", rc == 0 and not j.get("suppressed_contacts") and j.get("drafted"),
    [rc, j.get("suppressed_contacts"), [d.get("action") for d in j.get("drafted", [])]])
rc, j = run([C("k-new2", "crm:kim-eight")], [signup("s-new2", "k-new2"), {"id": "o2", "type": "opt_out", "contact": "k-new2", "scope": "all", "at": "2026-06-02T00:00:00+00:00"}])
row("R06", "as the doc advises: the opt-out put back on the merged record suppresses it", rc == 0 and j.get("suppressed_contacts") == ["k-new2"] and not j.get("drafted"), [rc, j.get("suppressed_contacts")])
shutil.rmtree(str(T), True)
for r in ROWS: print(r["row"], "PASS" if r["pass"] else "FAIL", r["name"], "|", json.dumps(r["detail"])[:300])
k = sum(r["pass"] for r in ROWS); print("M32R5 PROBE %d/%d" % (k, len(ROWS))); json.dump(ROWS, open(OUT, "w"), indent=1); sys.exit(0 if k == len(ROWS) else 1)
