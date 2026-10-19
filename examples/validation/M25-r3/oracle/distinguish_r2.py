"""M25 r2 distinguishing inputs for teeth survivors (Grok self-validation). Each case forges a checkpoint after
--crash-after 300 and recomputes body_sha256 (so the hash check passes), then breaks exactly one invariant that
check_snapshot guards. Candidate expectation: refused (rc 4 or 2, checkpoint unchanged). Usage: PY distinguish_r2.py PY OUT"""
import hashlib, json, os, subprocess, sys, tempfile
PY, OUT = sys.argv[1:3]; os.makedirs(OUT, exist_ok=True)
SRC = "/tmp/m25r2-eval/employees/engineering/iot-engineer/device_protocol.py"
HERE = os.path.dirname(os.path.abspath(__file__)); T = tempfile.mkdtemp(prefix="m25r2-dist-", dir="/tmp")
ENV = {"PATH": "/usr/bin:/bin", "HOME": T, "PYTHONDONTWRITEBYTECODE": "1"}
def run(tool, a): return subprocess.run([PY, tool] + a, capture_output=True, text=True, cwd=T, timeout=300, env=ENV)
def body_sha(s):
    snap = {k: s.get(k) for k in ("devices", "claims", "counts", "anomalies")}
    return hashlib.sha256(json.dumps(snap, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
tools = {"candidate": SRC}
for m in ("r2_applied_ge_off", "r2_counts_check_off", "r2_ack_owner_off"):
    p = os.path.join(T, m + ".py"); subprocess.run([PY, os.path.join(HERE, "make_mutants_r2.py"), SRC, m, p], check=True); tools[m] = p
run(SRC, ["simulate", "--devices", "6", "--steps", "200", "--seed", "11", "--faults", "drop=0.1,dup=0.2,reorder=0.3,reboot=0.02", "--record", "data/"])
C, E = os.path.join(T, "data/commands.jsonl"), os.path.join(T, "data/events.jsonl")
cmdlog = [json.loads(l) for l in open(C) if l.strip()]
def f_applied(s): s["counts"]["applied"] = 0
def f_counts_neg(s): s["counts"]["applied"] = -1
def f_counts_str(s): s["counts"]["duplicates_dropped"] = "7"
def f_ack_other(s):
    names = sorted(s["devices"]); a = names[0]
    other = next(c["cmd"] for c in cmdlog if c["device"] != a and c["cmd"] not in s["devices"][a]["acked"])
    s["devices"][a]["acked"].append(other)
cases = {"D_applied_lt_claims": f_applied, "D_counts_negative": f_counts_neg, "D_counts_string": f_counts_str, "D_ack_other_device": f_ack_other}
rows = []
for cid, fn in cases.items():
    for tname, tool in tools.items():
        st = os.path.join(T, f"st-{cid}-{tname}.json")
        run(tool, ["ingest", "--commands", C, "--events", E, "--state", st, "--crash-after", "300"])
        s = json.load(open(st)); fn(s); s["body_sha256"] = body_sha(s); open(st, "w").write(json.dumps(s, sort_keys=True))
        before = open(st, "rb").read(); cp = run(tool, ["ingest", "--commands", C, "--events", E, "--state", st, "--json"])
        rows.append({"case": cid, "tool": tname, "rc": cp.returncode, "unchanged": open(st, "rb").read() == before, "msg": (cp.stdout + cp.stderr).strip()[-140:] if cp.returncode not in (0, 1) else "(report)"})
        print(json.dumps(rows[-1]))
json.dump(rows, open(os.path.join(OUT, "distinguish.json"), "w"), indent=1)
