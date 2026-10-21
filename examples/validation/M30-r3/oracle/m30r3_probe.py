#!/usr/bin/env python3
"""M30 r3 probe (Grok self-validation, not independent review). Written for this pass from M12 P4-1 (plan text
over 300 characters refused as "expected a non-empty string") as carried onto the G30 day 5 stack. CLI rows run
`check --plan` on copies of the shipped G30 plan with one field changed. Inputs chosen here.
Usage: PY m30r3_probe.py REPO OUT.json"""
import copy, json, os, subprocess, sys, tempfile
REPO = os.path.abspath(sys.argv[1]); OUT = sys.argv[2]
TOOL = os.path.join(REPO, "employees/quality-security/assurance/daily_integration.py")
PLAN = json.load(open(os.path.join(REPO, "examples/capabilities/G30/plan.json"), encoding="utf-8"))
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1"); ROWS = []
def row(rid, name, ok, detail, obs=False): ROWS.append({"row": rid, "name": name, "pass": bool(ok), "obs": obs, "detail": detail})
def check(plan, keep_old=False):
    with tempfile.TemporaryDirectory() as d:
        p, out = os.path.join(d, "p.json"), os.path.join(d, "r.json")
        json.dump(plan, open(p, "w", encoding="utf-8"), ensure_ascii=False)
        if keep_old: open(out, "w").write("OLD")
        r = subprocess.run([sys.executable, TOOL, "check", "--plan", p, "--repo", REPO, "--out", out], capture_output=True, text=True, env=ENV, timeout=300)
        kept = open(out).read() if os.path.exists(out) else None
        return r.returncode, [r.stderr.strip()], kept
def with_reason(v):
    pl = copy.deepcopy(PLAN); pl["resolved_overlaps"] = [dict(PLAN["resolved_overlaps"][0], reason=v)] + PLAN["resolved_overlaps"][1:]; return pl
rc, e, kept = check(with_reason("y" * 301))
row("R01", "a 301-character overlap reason exits 2 and is named with its length and the limit", rc == 2 and "301 characters is too long; at most 300" in e[0] and kept is None, {"rc": rc, "err": e[0][:160]})
rc, e, kept = check(with_reason("\u00e9" * 301), keep_old=True)
row("R02", "the limit counts characters, not bytes (301 x U+00E9 named as 301), and a previous --out is kept", rc == 2 and "301 characters" in e[0] and kept == "OLD", {"rc": rc, "err": e[0][:160], "old_out": kept})
rc, e, _ = check(with_reason("z" * 300))
row("R03", "exactly 300 characters is not refused for length", "too long" not in e[0] and rc != 2, {"rc": rc, "err": e[0][:160]})
res = {}
for label, v in (("empty", ""), ("int", 5), ("null", None), ("list", ["a"])):
    rc, e, _ = check(with_reason(v)); res[label] = (rc, "expected a non-empty string" in e[0])
row("R04", "blank and non-string reasons keep the old message (exit 2)", all(x == (2, True) for x in res.values()), res)
pl = copy.deepcopy(PLAN); pl["external"] = [{"id": "X91", "reply_url": "https://" + "u" * 392, "reply_sha256": "0" * 64, "validation_manifest_sha256": "0" * 64}]
rc, e, _ = check(pl)
row("R05", "another text field (external reply_url, an https URL of 400 characters) also gets the length message", rc == 2 and "400 characters is too long" in e[0], {"rc": rc, "err": e[0][:160]})
rc, e, kept = check(PLAN)
row("R06", "the shipped plan is unchanged by the fix: not exit 2 (binds the stack)", rc == 0, {"rc": rc})
row("R07", "OBS: the 300 limit is a fixed constant per field; the message names it but the plan schema has no field to raise it", True, None, obs=True)
scored = [r for r in ROWS if not r["obs"]]; n = sum(r["pass"] for r in scored)
json.dump({"probe": "m30r3", "python": sys.version.split()[0], "rows": ROWS, "score": "%d/%d" % (n, len(scored))}, open(OUT, "w"), indent=1)
for r in ROWS: print("%s %s %s" % ("OBS " if r["obs"] else ("PASS" if r["pass"] else "FAIL"), r["row"], r["name"]))
print("SCORE %d/%d" % (n, len(scored))); sys.exit(0 if n == len(scored) else 1)
