"""M31 r2 probe (Grok self-validation, not independent review). Usage: m31r2_probe.py WT [PY]"""
import copy, json, os, subprocess, sys, tempfile, shutil
WT = sys.argv[1]; PY = sys.argv[2] if len(sys.argv) > 2 else sys.executable
TOOL = os.path.join(WT, "employees/product-project/business-analyst/scope_acceptance.py")
FIX = os.path.join(WT, "examples/capabilities/G31/fixtures")
BASE = json.load(open(os.path.join(FIX, "portal.json")))
def req(P, k): return [r for r in P["requirements"] if r["id"] == k][0]
def run(P):
    d = tempfile.mkdtemp(); 
    for n in os.listdir(FIX):
        s = os.path.join(FIX, n)
        (shutil.copytree if os.path.isdir(s) else shutil.copy)(s, os.path.join(d, n))
    p = os.path.join(d, "portal.json"); json.dump(P, open(p, "w"))
    r = subprocess.run([PY, TOOL, "check", p, "--json"], capture_output=True, text=True)
    shutil.rmtree(d)
    try: j = json.loads(r.stdout)
    except Exception: j = {"_raw": (r.stdout + r.stderr)[-300:]}
    return r.returncode, j
def codes(j): return sorted({(f["code"], f["ref"]) for f in j.get("findings", [])})
def amb(P, about, status, aid="AMBX"):
    a = {"id": aid, "about": about, "question": "Which one holds?", "escalated_to": "Client sponsor", "status": status}
    if status == "resolved": a["resolution"] = {"text": "business hours only", "source": "call notes 2026-09-29", "date": "2026-09-29"}
    P["ambiguities"].append(a)
cases = []
def case(name, expect_rc, mut, check=None, obs=False):
    P = copy.deepcopy(BASE); mut(P); rc, j = run(P)
    ok = rc == expect_rc and (check(j) if check else True)
    cases.append((name, ok, rc, codes(j)[:6], obs, j.get("_raw")))
case("P01 baseline ready", 0, lambda P: None)
case("P02 declared conflicts_with, no ambiguity -> unresolved_conflict both", 1,
     lambda P: req(P, "R1").__setitem__("conflicts_with", ["R2"]),
     lambda j: {("unresolved_conflict", "R1"), ("unresolved_conflict", "R2")} <= set(codes(j)))
def m3(P): req(P, "R3")["text"] += ", sent 24/7"; req(P, "R4")["acceptance"][0]["criterion"] += " during business hours"
case("P03 opposite terms across requirement and other criterion -> blocked", 1, m3,
     lambda j: ("unresolved_conflict", "R3") in codes(j) and ("unresolved_conflict", "R4") in codes(j))
def m4(P): m3(P); amb(P, ["R3", "R4"], "resolved")
case("P04 resolved ambiguity -> ready and C4 qualified_by", 0, m4,
     lambda j: [m for m in j["trace_matrix"] if m["commitment"] == "C4"][0].get("qualified_by") == ["AMBX"]
     and any(c["status"] == "resolved" for c in j.get("conflicts", [])))
def m5(P): m3(P); amb(P, ["R3", "R4"], "open")
case("P05 open ambiguity -> blocked and escalated", 1, m5,
     lambda j: ("open_ambiguity", "R3") in codes(j) and any(e["id"] == "AMBX" for e in j["escalations"]))
def m6(P): req(P, "R4")["acceptance"][0]["criterion"] += " during business hours"; P["proposal"]["commitments"].append({"id": "C5", "kind": "sla", "text": "Support desk answers 24/7", "refs": ["R4"]})
case("P06 commitment text vs in-scope criterion -> conflicting_commitment", 1, m6, lambda j: ("conflicting_commitment", "C5") in codes(j))
def m7(P):
    P["proposal"]["commitments"].append({"id": "C5", "kind": "sla", "text": "Support desk answers 24/7", "refs": ["R2"]})
    P["proposal"]["commitments"].append({"id": "C6", "kind": "sla", "text": "Support desk answers during office hours only", "refs": ["R2"]})
case("P07 two commitments contradict each other (requirements silent) -> blocked", 1, m7,
     lambda j: any(c[0] == "conflicting_commitment" for c in codes(j)))
case("P08 both sides inside one requirement text -> blocked", 1,
     lambda P: req(P, "R3").__setitem__("text", req(P, "R3")["text"] + ", 24/7 but only during business hours"),
     lambda j: ("unresolved_conflict", "R3") in codes(j))
def m9(P): [i for i in P["inputs"] if i["id"] == "IN1"][0]["text"] += " without an account"; req(P, "R1")["text"] += ", login required"
case("P09 requirement vs its own traced input -> blocked", 1, m9, lambda j: ("unresolved_conflict", "R1") in codes(j))
def m10(P): m3(P); amb(P, ["R3"], "resolved")
case("P10 resolved ambiguity covering one side only -> still blocked", 1, m10, lambda j: ("unresolved_conflict", "R4") in codes(j))
def m11(P): req(P, "R3")["text"] += " ONLINE ONLY"; req(P, "R4")["text"] += " works Offline"
case("P11 case-insensitive match -> blocked", 1, m11, lambda j: any(c[0] == "unresolved_conflict" for c in codes(j)))
case("P12 OBS excluded requirement conflicting with in-scope one -> not a finding", 0,
     lambda P: req(P, "R5").__setitem__("conflicts_with", ["R1"]), obs=True)
def m13(P): req(P, "R3")["text"] += " with no offline mode"; req(P, "R4")["text"] += ", online only"
case("P13 OBS negated term still flagged (fails closed)", 1, m13, obs=True)
def m14(P): m4(P); P["proposal"]["commitments"].append({"id": "C5", "kind": "other", "text": "Reminders as listed in the brief", "refs": ["IN3"]})
case("P14 OBS commitment resting only on a traced input of a resolved conflict (qualified_by printed)", 0, m14,
     lambda j: print("   P14 C5 qualified_by =", [m for m in j["trace_matrix"] if m["commitment"] == "C5"][0].get("qualified_by")) or True, obs=True)
for n, ok, rc, cs, obs, raw in cases:
    print("%s %s rc=%s %s%s" % ("OBS " if obs else ("PASS" if ok else "FAIL"), n, rc, cs, (" RAW " + raw) if raw else ""))
nonobs = [c for c in cases if not c[4]]
print("PROBE %d/%d" % (sum(c[1] for c in nonobs), len(nonobs)))
