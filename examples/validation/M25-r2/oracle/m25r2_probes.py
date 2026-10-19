#!/usr/bin/env python3
"""M25 r2 probes (Grok self-validation) for G25 r2. Expectations from device-event-protocol.md at a902bc4:
"an edited, truncated or damaged checkpoint exits 4 and nothing is written"; "a resume onto changed input is
refused (exit 2)"; "--record creates its folder (an existing file there is exit 2)"; buffer "next+1 to next+32";
whole-string id patterns. Rows marked LIMIT test the documented hash-is-not-a-signature limit: recorded, not graded.
Usage: m25r2_probes.py PY TOOL OUT"""
import hashlib, json, os, shutil, subprocess, sys, tempfile
PY, TOOL, OUT = sys.argv[1:4]; os.makedirs(OUT, exist_ok=True)
T = tempfile.mkdtemp(prefix="m25r2p-", dir="/tmp")
ENV = {"PATH": "/usr/bin:/bin", "HOME": T, "PYTHONDONTWRITEBYTECODE": "1"}
res = []
def run(args, cwd=T):
    p = subprocess.run([PY, TOOL] + args, capture_output=True, text=True, cwd=cwd, timeout=300, env=ENV)
    try:
        rep = json.loads(p.stdout)
    except ValueError:
        rep = None
    return p.returncode, rep, p.stdout + p.stderr
def probe(pid, ok, obs, graded=True):
    res.append({"id": pid, "result": ("PASS" if ok else "FAIL") if graded else "LIMIT", "observed": obs})
    print(f"{pid:5} {res[-1]['result']:5} {json.dumps(obs)[:240]}")
tb = lambda s: "Traceback" in s
# data: a faulted simulation
rc, _, out = run(["simulate", "--devices", "6", "--steps", "200", "--seed", "11", "--faults", "drop=0.1,dup=0.2,reorder=0.3,reboot=0.02", "--record", "data/"])
C, E = os.path.join(T, "data/commands.jsonl"), os.path.join(T, "data/events.jsonl")
_, full, _ = run(["ingest", "--commands", C, "--events", E, "--json"])
strip = lambda r: {k: v for k, v in (r or {}).items() if k not in ("resume", "tool_version", "resumed_from_line")}  # v2: resumed_from_line differs by design
def crash_state(tag):
    st = os.path.join(T, f"st-{tag}.json")
    run(["ingest", "--commands", C, "--events", E, "--state", st, "--crash-after", "300"])
    return st, json.load(open(st))
def resume(st):
    before = open(st, "rb").read()
    rc, rep, out = run(["ingest", "--commands", C, "--events", E, "--state", st, "--json"])
    return rc, rep, out, open(st, "rb").read() == before
def body_sha(s):
    snap = {k: s.get(k) for k in ("devices", "claims", "counts", "anomalies")}
    return hashlib.sha256(json.dumps(snap, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
st, s = crash_state("ok"); rc, rep, out, _ = resume(st)
probe("R00", rc == 1 and strip(rep) == strip(full), {"rc": rc, "same_as_unbroken": strip(rep) == strip(full), "claims": (rep or {}).get("effects_claimed")})
# out-of-body fields (not covered by body_sha256)
for pid, field, fn in [("R01", "lines", lambda v: v + 1000), ("R02", "lines", lambda v: 0), ("R03", "offset", lambda v: v - 1),
                       ("R04", "events_prefix_sha256", lambda v: "0" * 64), ("R05", "tool_version", lambda v: "9.9.9")]:
    st, s = crash_state(pid); s0_lines = s["lines"]; s[field] = fn(s[field]); open(st, "w").write(json.dumps(s, sort_keys=True))
    rc, rep, out, unchanged = resume(st)
    same = strip(rep) == strip(full)
    probe(pid, (rc in (2, 4) and unchanged and not tb(out)) or (rc == 1 and same), {"edited": field, "rc": rc, "same_as_unbroken": same, "resumed_from_line": (rep or {}).get("resumed_from_line"), "true_line": s0_lines, "state_unchanged_on_refusal": unchanged, "msg": out.strip()[-110:]})
# damaged shapes
for pid, txt in [("R06", "[]"), ("R07", ""), ("R08", "{\"schema\": 1"), ("R09", "null"), ("R10", "\"text\"")]:
    st = os.path.join(T, f"st-{pid}.json"); open(st, "w").write(txt)
    rc, rep, out, unchanged = resume(st)
    probe(pid, rc == 4 and unchanged and not tb(out), {"checkpoint": txt or "(empty)", "rc": rc, "unchanged": unchanged, "msg": out.strip()[-100:]})
# edited body without recomputing the hash
st, s = crash_state("R11"); k = next(iter(s["counts"])); s["counts"][k] += 5; open(st, "w").write(json.dumps(s, sort_keys=True))
rc, rep, out, unchanged = resume(st); probe("R11", rc == 4 and unchanged, {"rc": rc, "unchanged": unchanged})
# forged with recomputed hash (documented limit)
st, s = crash_state("L01"); n = len(s["claims"]); s["claims"] = []; s["body_sha256"] = body_sha(s); open(st, "w").write(json.dumps(s, sort_keys=True))
rc, rep, out, _ = resume(st); probe("L01", None, {"forged": f"claims removed ({n}), hash recomputed", "rc": rc, "claims": (rep or {}).get("effects_claimed"), "unbroken_claims": full.get("effects_claimed")}, graded=False)
st, s = crash_state("L02"); s["counts"]["duplicates_dropped"] = s["counts"].get("duplicates_dropped", 0) + 777; s["body_sha256"] = body_sha(s); open(st, "w").write(json.dumps(s, sort_keys=True))
rc, rep, out, _ = resume(st); probe("L02", None, {"forged": "duplicates_dropped +777, hash recomputed", "rc": rc, "dups": ((rep or {}).get("counts") or {}).get("duplicates_dropped"), "unbroken": full["counts"].get("duplicates_dropped")}, graded=False)
# --record
os.makedirs(os.path.join(T, "realdir"), exist_ok=True); open(os.path.join(T, "afile"), "w").write("x"); os.symlink(os.path.join(T, "realdir"), os.path.join(T, "linkdir"))
sim = lambda rec: run(["simulate", "--devices", "2", "--steps", "20", "--seed", "3", "--record", rec])
rc, _, out = sim("new/deep/dir/"); probe("D01", rc == 0 and os.path.exists(os.path.join(T, "new/deep/dir/events.jsonl")), {"rc": rc})
rc, _, out = sim("afile"); probe("D02", rc == 2 and not tb(out) and open(os.path.join(T, "afile")).read() == "x", {"rc": rc, "msg": out.strip()[-90:]})
rc, _, out = sim("linkdir"); probe("D03", rc == 2 and not tb(out) and not os.listdir(os.path.join(T, "realdir")), {"rc": rc, "msg": out.strip()[-90:]})
rc, _, out = sim("afile/sub"); probe("D04", rc == 2 and not tb(out), {"rc": rc, "traceback": tb(out), "msg": out.strip()[-120:], "note": "parent is a file"})
rc, _, out = sim("realdir"); probe("D05", rc == 0 and os.path.exists(os.path.join(T, "realdir/commands.jsonl")), {"rc": rc, "note": "existing empty folder"})
# window
def ev(d, b, s, k="hello", **kw):
    x = {"v": 1, "device": d, "boot": b, "seq": s, "kind": k}; x.update(kw); return json.dumps(x)
def ing(lines, cmds=()):
    d = tempfile.mkdtemp(dir=T); c, e = os.path.join(d, "c.jsonl"), os.path.join(d, "e.jsonl")
    open(c, "w").write("".join(x + "\n" for x in cmds)); open(e, "w").write("".join(x + "\n" for x in lines))
    return run(["ingest", "--commands", c, "--events", e, "--json"])
gaps = lambda r: sum(1 for a in (r or {}).get("anomalies", []) if a.get("kind") == "gap")
for pid, ahead, want_gap in [("W32", 32, 0), ("W33", 33, 1)]:
    lines = [ev("v", 1, 1)] + [ev("v", 1, s) for s in range(3, 3 + ahead)] + [ev("v", 1, 2)]
    rc, rep, out = ing(lines); probe(pid, gaps(rep) == want_gap, {"records_ahead_of_hole": ahead, "gaps": gaps(rep), "rc": rc})
# whole-string ids
rc, rep, out = ing([ev("v", 1, 1), ev("v1\n", 1, 1)]); probe("I01", list((rep or {}).get("devices", {})) == ["v"], {"devices": list((rep or {}).get("devices", {})), "rc": rc})
rc, rep, out = ing([ev("v", 1, 1), ev("v", 1, 2, "ack", cmd="c-1\n", result="done", state="open")], [json.dumps({"cmd": "c-1", "device": "v", "action": "open"})])
probe("I02", (rep or {}).get("effects_claimed") in (0, []) or not (rep or {}).get("claims"), {"rc": rc, "claims": (rep or {}).get("claims"), "note": "ack cmd 'c-1\\n' must not claim c-1"})
# rejected then done for one command (doc ambiguous; recorded)
rc, rep, out = ing([ev("v", 1, 1), ev("v", 1, 2, "ack", cmd="c-1", result="rejected", state="closed"), ev("v", 1, 3, "ack", cmd="c-1", result="done", state="open")], [json.dumps({"cmd": "c-1", "device": "v", "action": "open"})])
probe("L03", None, {"rc": rc, "claims": (rep or {}).get("claims"), "counts": (rep or {}).get("counts"), "note": "doc: rejected ack makes no claim; repeats are duplicate_acks; behaviour pinned by builder"}, graded=False)
json.dump(res, open(os.path.join(OUT, "probes.json"), "w"), indent=1)
g = [r for r in res if r["result"] != "LIMIT"]
print(f"TOTAL {sum(r['result'] == 'PASS' for r in g)}/{len(g)} FAILS {[r['id'] for r in g if r['result'] == 'FAIL']}")
shutil.rmtree(T)
