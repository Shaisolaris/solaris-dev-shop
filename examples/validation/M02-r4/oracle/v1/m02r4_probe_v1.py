#!/usr/bin/env python3
"""M02 r4 probe (Grok self-validation, not independent review). Written for this pass from M02 r3 P4-1 (placeholder
deploy answers recorded as the deploy model) and OBS-1 (UNRESOLVED with a look-alike letter read as an answer), with
inputs chosen here and not copied from the G02 r5 test. Drives activate() in process.
Usage: PY m02r4_probe.py REPO OUT.json"""
import contextlib, importlib.util, io, json, os, shutil, sys, tempfile
REPO = os.path.abspath(sys.argv[1]); OUT = sys.argv[2]
TOOL = os.path.join(REPO, "employees/product-project/project-onboarding/activate.py")
spec = importlib.util.spec_from_file_location("act", TOOL); act = importlib.util.module_from_spec(spec); spec.loader.exec_module(act)
ROWS = []
def row(rid, name, ok, detail): ROWS.append({"row": rid, "name": name, "pass": bool(ok), "detail": detail})
def run(deploy):
    t = tempfile.mkdtemp(prefix="m02r4-"); root = os.path.join(t, "proj")
    try:
        with contextlib.redirect_stderr(io.StringIO()):
            r = act.activate(root, {"name": "Probe", "project_type": "website", "brief": "a site", "deploy_model": deploy})
        status = open(os.path.join(root, "STATUS.md"), encoding="utf-8").read() if os.path.exists(os.path.join(root, "STATUS.md")) else ""
        return r["status"], (r.get("intake") or {}).get("deploy_model"), "DEPLOY-MODEL: UNRESOLVED" in status
    except BaseException as e:
        return "raised", "%s: %s" % (type(e).__name__, e), False
    finally:
        shutil.rmtree(t, ignore_errors=True)
def unresolved(cases):
    bad = {}
    for c in cases:
        s, d, line = run(c)
        if s == "complete" or d is not None or not line: bad[c] = [s, d, line]
    return bad
def kept(cases):
    bad = {}
    for c in cases:
        s, d, _ = run(c)
        if d != c: bad[c] = [s, d]
    return bad
P = ["TBC", "t.b.d.", "N/A.", "n / a", "???", "-?-", "TODO", "To Be Determined", "UNKNOWN!", "pending.", "\u00a0tbd\u00a0",
     "T\u200bBD", "\uff34\uff22\uff24", "none.", "(tbd)", "\u2013", "*", "#", "_", "null"]
H = ["\u0055\u041d\u0052ESOLVED", "UNRESOLV\u0415D", "unres\u043flved", "\u0423NRESOLVED later", "UNR\u0395SOLVED ask",
     "\u03bfnresolved", "UNRESOL\u1d20ED", "un\u0280esolved"]
C = ["Vercel", "AWS Amplify (region TBD)", "Netlify; staging n/a", "none of these, Fly.io", "Pending: Cloudflare Pages",
     "Heroku", "unresolvable? no: Render", "\u30c7\u30d7\u30ed\u30a4: Vercel", "Unknown Worlds hosting", "TBD Corp private cloud"]
b = unresolved(P); row("R01", "20 placeholder spellings not in the G02 r5 test stay UNRESOLVED (partial, STATUS line)", not b, b or "all unresolved")
b = unresolved(H); row("R02", "8 look-alike spellings of UNRESOLVED (Cyrillic, Greek, small capitals) stay UNRESOLVED", not b, b or "all unresolved")
b = kept(C); row("R03", "controls: 10 real deploy answers that mention a placeholder word are recorded unchanged", not b, b or "all kept")
s, d, line = run(None); row("R04", "control: no deploy answer stays UNRESOLVED", s != "complete" and d is None and line, [s, d, line])
s, d, line = run("Vercel"); row("R05", "control: plain answer is complete", s == "complete" and d == "Vercel", [s, d])
for r in ROWS: print(r["row"], "PASS" if r["pass"] else "FAIL", r["name"], "|", json.dumps(r["detail"], ensure_ascii=True)[:400])
n = sum(r["pass"] for r in ROWS); print("M02R4 PROBE %d/%d" % (n, len(ROWS)))
json.dump(ROWS, open(OUT, "w"), indent=1, ensure_ascii=False)
sys.exit(0 if n == len(ROWS) else 1)
