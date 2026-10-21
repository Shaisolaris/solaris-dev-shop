"""M15 r6 probe (Grok self-validation, not independent review): units in both arms count toward expected_units.
Usage: m15r6_probe.py TREE OUT.json. Uses the six two-arm units already in the retention-lift fixture."""
import json, os, shutil, subprocess, sys, tempfile
TREE = os.path.abspath(sys.argv[1]); OUT = sys.argv[2]; ROWS = []
TOOL = os.path.join(TREE, "employees/data/data-scientist/experiment_readout.py")
FX = os.path.join(TREE, "examples/capabilities/G15/fixtures/retention-lift")
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
def run(eu, extra=()):
    d = tempfile.mkdtemp(prefix="m15r6-"); r = os.path.join(d, "x"); shutil.copytree(FX, r)
    p = json.load(open(os.path.join(r, "package.json"))); p["randomization"]["expected_units"] = eu
    json.dump(p, open(os.path.join(r, "package.json"), "w"))
    if extra:
        open(os.path.join(r, "assignments.csv"), "a").write("".join(x + "\n" for x in extra))
    q = subprocess.run([sys.executable, TOOL, "analyse", os.path.join(r, "package.json"), "--json"], capture_output=True, text=True, env=ENV)
    shutil.rmtree(d, ignore_errors=True)
    return q.returncode, (json.loads(q.stdout) if q.returncode == 0 else {})
def row(rid, name, ok, detail):
    ROWS.append({"row": rid, "name": name, "pass": bool(ok), "detail": detail})
rc, j = run(1206); ac = j.get("assignment_check", {})
row("R01", "fixture: 1200 one-arm + 6 two-arm units; expected_units 1206 is verified (two-arm units counted)",
    rc == 0 and ac.get("units_in_log") == 1206 and ac.get("verified") is True and len(j["exclusions"]["multiple_arms"]) == 6, [rc, ac])
rc, j = run(1200); t = " ".join(j.get("trace", []))
row("R02", "expected_units 1200 (two-arm units left out of the count) is invalid: units added to the log",
    rc == 0 and j.get("outcome") == "invalid_experiment" and "holds 1206 cohort units but the declared randomization assigned 1200: units are added" in t, [rc, j.get("outcome")])
rc, j = run(1206, ["u001220,control,2026-08-20T10:00:00Z", "u001220,treatment,2026-08-21T10:00:00Z"])
ac = j.get("assignment_check", {})
row("R03", "more rows for a two-arm unit do not add to the count (still 1206, verified)", rc == 0 and ac.get("units_in_log") == 1206 and ac.get("verified") is True, [rc, ac])
rc, j = run(1206); a = j.get("arms", {})
row("R04", "two-arm units are excluded from the effect (600 + 600 units in the arms)", rc == 0 and a.get("control", {}).get("units") == 600 and a.get("treatment", {}).get("units") == 600, [a.get("control", {}).get("units"), a.get("treatment", {}).get("units")])
json.dump({"python": sys.version.split()[0], "rows": ROWS}, open(OUT, "w"), indent=1)
for r in ROWS: print(("PASS " if r["pass"] else "FAIL ") + r["row"] + " " + r["name"] + " " + json.dumps(r["detail"])[:300])
print("M15R6 PROBE %d/%d" % (sum(r["pass"] for r in ROWS), len(ROWS)))
