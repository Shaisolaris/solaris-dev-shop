#!/usr/bin/env python3
"""M31 r3 probe (Grok self-validation, not independent review). Written for this pass from M31 r2 P4-1 (qualified_by
only covered commitments that name a requirement in the conflict) and the doc's Contradictions section. Copies the
G31 fixture folder, edits portal.json, runs `check --json` and the text report. Inputs chosen here, not copied from
the G31 r4 test. Usage: PY m31r3_probe.py REPO OUT.json"""
import copy, json, os, shutil, subprocess, sys, tempfile
REPO = os.path.abspath(sys.argv[1]); OUT = sys.argv[2]
TOOL = os.path.join(REPO, "employees/product-project/business-analyst/scope_acceptance.py")
FIX = os.path.join(REPO, "examples/capabilities/G31/fixtures"); BASE = json.load(open(os.path.join(FIX, "portal.json")))
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1"); ROWS = []
def row(rid, name, ok, detail, obs=False): ROWS.append({"row": rid, "name": name, "pass": bool(ok), "obs": obs, "detail": detail})
def run(P, text=False):
    d = tempfile.mkdtemp(prefix="m31r3-")
    for n in os.listdir(FIX):
        s = os.path.join(FIX, n); (shutil.copytree if os.path.isdir(s) else shutil.copy)(s, os.path.join(d, n))
    p = os.path.join(d, "portal.json"); json.dump(P, open(p, "w"))
    r = subprocess.run([sys.executable, TOOL, "check", p] + ([] if text else ["--json"]), capture_output=True, text=True, env=ENV, timeout=120)
    shutil.rmtree(d, True)
    if text: return r.returncode, r.stdout
    try: return r.returncode, json.loads(r.stdout)
    except ValueError: return r.returncode, {"_raw": (r.stdout + r.stderr)[-300:]}
def req(P, k): return [r for r in P["requirements"] if r["id"] == k][0]
def qual(j, c): return [m for m in j.get("trace_matrix", []) if m["commitment"] == c][0]["qualified_by"]
def codes(j): return sorted({(f["code"], f["ref"]) for f in j.get("findings", [])})
def resolve(P, about, aid="AMBQ", status="resolved"):
    a = {"id": aid, "about": about, "question": "which holds?", "escalated_to": "Clinic owner", "status": status}
    if status == "resolved": a["resolution"] = {"text": "owner decided", "source": "owner call 2026-10-04", "date": "2026-10-04"}
    P["ambiguities"].append(a)
def commit(P, cid, refs, kind="other", text="As described in the brief"):
    P["proposal"]["commitments"].append({"id": cid, "kind": kind, "text": text, "refs": refs})
# Q1 declared conflict R2 vs R3 resolved; commitments on IN2 (R2 traces), IN3 (R3 traces), IN4 (neither) and A1
P = copy.deepcopy(BASE); req(P, "R3")["conflicts_with"] = ["R2"]; resolve(P, ["R2", "R3"])
commit(P, "Q2", ["IN2"]); commit(P, "Q3", ["IN3"]); commit(P, "Q4", ["IN4"]); commit(P, "QA", ["A1"])
rc, j = run(P); got = {c: qual(j, c) for c in ("Q2", "Q3", "Q4", "QA")} if rc == 0 else j
row("Q1", "declared conflict R2/R3 resolved: commitments on IN2 and IN3 are qualified, on IN4 and A1 are not",
    rc == 0 and got == {"Q2": ["AMBQ"], "Q3": ["AMBQ"], "Q4": [], "QA": []}, {"rc": rc, "qualified_by": got})
# Q2 the text report prints the qualification for an input-only commitment
rc, out = run(P, text=True); line = [l for l in out.splitlines() if "Q3" in l]
row("Q2", "text report: the input-only commitment line says [qualified by owner resolution AMBQ]", rc == 0 and line and "qualified by owner resolution AMBQ" in line[0], line[:1])
# Q3 two resolved conflicts both touch one input: both ambiguities listed
P = copy.deepcopy(BASE); req(P, "R3")["conflicts_with"] = ["R2"]; req(P, "R1")["conflicts_with"] = ["R2"]
resolve(P, ["R2", "R3"], "AMBK"); resolve(P, ["R1", "R2"], "AMBL"); commit(P, "Q2", ["IN2"]); commit(P, "Q1", ["IN1"])
rc, j = run(P); got = {c: qual(j, c) for c in ("Q1", "Q2")} if rc == 0 else j
row("Q3", "two resolved conflicts on R2: a commitment on IN2 lists AMBK and AMBL; on IN1 only AMBL", rc == 0 and got == {"Q1": ["AMBL"], "Q2": ["AMBK", "AMBL"]}, {"rc": rc, "got": got})
# Q4 control: a requirement-named commitment keeps its qualification (r3 behaviour)
P = copy.deepcopy(BASE); req(P, "R3")["conflicts_with"] = ["R2"]; resolve(P, ["R2", "R3"]); commit(P, "QR", ["R3"], kind="feature")
rc, j = run(P); row("Q4", "control: a commitment naming R3 stays qualified", rc == 0 and qual(j, "QR") == ["AMBQ"], {"rc": rc})
# Q5 control: no conflict, nothing is qualified
P = copy.deepcopy(BASE); commit(P, "Q2", ["IN2"]); rc, j = run(P)
row("Q5", "control: with no conflict, an input-only commitment has an empty qualified_by", rc == 0 and qual(j, "Q2") == [], {"rc": rc})
# Q6 OBS: open conflict, commitment on the traced input only (not a requirement): is it blocked?
P = copy.deepcopy(BASE); req(P, "R3")["conflicts_with"] = ["R2"]; resolve(P, ["R2", "R3"], status="open"); commit(P, "Q3", ["IN3"])
rc, j = run(P); c = [x for x in codes(j) if x[1] == "Q3"]
row("Q6", "OBS: open conflict on R2/R3: a commitment on IN3 alone gets no commitment finding of its own (report is blocked anyway)", True, {"rc": rc, "Q3_findings": c, "status": j.get("status")}, obs=True)
for r in ROWS: print(r["row"], "OBS " if r["obs"] else ("PASS" if r["pass"] else "FAIL"), r["name"], "|", json.dumps(r["detail"])[:300])
sc = [r for r in ROWS if not r["obs"]]; n = sum(r["pass"] for r in sc); print("M31R3 PROBE %d/%d" % (n, len(sc)))
json.dump(ROWS, open(OUT, "w"), indent=1); sys.exit(0 if n == len(sc) else 1)
