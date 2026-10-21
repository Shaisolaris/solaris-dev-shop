#!/usr/bin/env python3
"""M12 r2 probe (Grok self-validation, not independent review). Written for this pass from M12 P4-1 (a plan text over
300 characters was refused as "expected a non-empty string"). Black-box CLI runs of daily_integration.py check on
plans changed here; inputs chosen here, not copied from the G12 r3 test.
Usage: PY m12r2_probe.py REPO OUT.json"""
import json, os, subprocess, sys, tempfile
REPO = os.path.abspath(sys.argv[1]); OUT = sys.argv[2]
TOOL = os.path.join(REPO, "employees/quality-security/assurance/daily_integration.py")
PLAN = json.load(open(os.path.join(REPO, "examples/capabilities/G12/plan.json")))
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1"); ENV.pop("G20_CHROME", None); ROWS = []
def row(rid, name, ok, detail): ROWS.append({"row": rid, "name": name, "pass": bool(ok), "detail": detail})
def check(plan, keep=None):
    d = tempfile.mkdtemp(prefix="m12r2-"); p, out = os.path.join(d, "p.json"), os.path.join(d, "r.json")
    json.dump(plan, open(p, "w"))
    if keep is not None: open(out, "w").write(keep)
    r = subprocess.run([sys.executable, TOOL, "check", "--plan", p, "--repo", REPO, "--out", out], capture_output=True, text=True, env=ENV, timeout=600)
    after = open(out).read() if os.path.exists(out) else None
    return r.returncode, r.stderr.strip().splitlines()[:1], after
def with_(key, value):
    p = json.loads(json.dumps(PLAN)); p[key] = value; return p
cases = {"reason 301": (with_("resolved_overlaps", [{"path": "x.txt", "reason": "w" * 301}]), "301 characters is too long; at most 300"),
         "reason 5000": (with_("resolved_overlaps", [{"path": "x.txt", "reason": "w " * 2500}]), "5000 characters is too long; at most 300"),
         "path 400": (with_("resolved_overlaps", [{"path": "d/" * 200, "reason": "ok"}]), "400 characters is too long"),
         "cross_check arg 350": (with_("cross_checks", [["examples/capabilities/G12/cross_checks.py", "a" * 350]]), "350 characters is too long")}
bad = {}
for k, (plan, want) in cases.items():
    rc, err, _ = check(plan)
    if rc != 2 or not err or want not in err[0]: bad[k] = [rc, err]
row("R01", "4 over-long texts in three fields: exit 2 and the message names the length and the limit", not bad, bad or "all named")
bad = {}
for k, v in {"empty": "", "number": 12, "null": None, "list": ["a"]}.items():
    rc, err, _ = check(with_("resolved_overlaps", [{"path": "x.txt", "reason": v}]))
    if rc != 2 or not err or "expected a non-empty string" not in err[0]: bad[k] = [rc, err]
row("R02", "empty, number, null and list reasons still say expected a non-empty string", not bad, bad or "all")
rc, err, after = check(with_("resolved_overlaps", [{"path": "x.txt", "reason": "w" * 301}]), keep="PREVIOUS")
row("R03", "an over-long refusal keeps a previous --out report", rc == 2 and after == "PREVIOUS", [rc, after])
rc, err, after = check(with_("resolved_overlaps", [{"path": "x.txt", "reason": "w" * 300}]))
row("R04", "boundary: a 300-character reason is not refused as invalid input (exit 0 or 1, not 2)", rc in (0, 1), [rc, err])
for r in ROWS: print(r["row"], "PASS" if r["pass"] else "FAIL", r["name"], "|", json.dumps(r["detail"])[:300])
n = sum(r["pass"] for r in ROWS); print("M12R2 PROBE %d/%d" % (n, len(ROWS))); json.dump(ROWS, open(OUT, "w"), indent=1)
sys.exit(0 if n == len(ROWS) else 1)
