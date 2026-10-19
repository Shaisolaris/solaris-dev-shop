#!/usr/bin/env python3
"""M25 r3 probes (Grok self-validation) for G25 r3 (eb9c7c4). Expectations from device-event-protocol.md at eb9c7c4:
body_sha256 covers every other checkpoint field; lines is recounted from the ingested bytes; JSON that is not a checkpoint
object exits 4; --record refuses an existing file there or anywhere above it (exit 2). LIMIT/OBS rows are recorded, not graded.
Usage: m25r3_probes.py PY TOOL OUT"""
import hashlib, json, os, shutil, subprocess, sys, tempfile
PY, TOOL, OUT = sys.argv[1:4]; os.makedirs(OUT, exist_ok=True)
T = tempfile.mkdtemp(prefix="m25r3p-", dir="/tmp")
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
def body_sha3(s):
    rest = {k: v for k, v in s.items() if k != "body_sha256"}
    return hashlib.sha256(json.dumps(rest, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
sim = lambda rec: run(["simulate", "--devices", "2", "--steps", "20", "--seed", "3", "--record", rec])
def write(st, s): open(st, "w").write(json.dumps(s, sort_keys=True))
st, s = crash_state("base"); rc, rep, out, _ = resume(st)
probe("H00", rc == 1 and strip(rep) == strip(full) and body_sha3(s) == s.get("body_sha256"), {"rc": rc, "same": strip(rep) == strip(full), "doc_hash_formula_matches": body_sha3(s) == s.get("body_sha256")})
# every non-hash field edited WITHOUT recomputing: exit 4, unchanged
edits = [("H01", "lines", lambda v: v + 1), ("H02", "offset", lambda v: v + 1), ("H03", "events_prefix_sha256", lambda v: "f" * 64), ("H04", "tool_version", lambda v: "1.2.1"),
         ("H05", "devices", lambda v: v), ("H06", "anomalies", lambda v: (v + [v[0]]) if isinstance(v, list) and v else v)]
for pid, f, fn in edits:
    st, s = crash_state(pid)
    if f == "devices":
        k = next(iter(s["devices"])); s["devices"][k] = dict(s["devices"][k], _x=1) if isinstance(s["devices"][k], dict) else s["devices"][k]
    else:
        s[f] = fn(s[f])
    write(st, s); rc, rep, out, un = resume(st)
    probe(pid, rc == 4 and un and not tb(out), {"edited": f, "rc": rc, "unchanged": un, "msg": out.strip()[-90:]})
# forged WITH the r3 hash recomputed
st, s = crash_state("H10"); s["lines"] += 1; s["body_sha256"] = body_sha3(s); write(st, s); rc, rep, out, un = resume(st)
probe("H10", rc == 4 and un and not tb(out), {"forged": "lines+1, hash recomputed", "rc": rc, "msg": out.strip()[-90:]})
st, s = crash_state("H11"); s["lines"] -= 1; s["body_sha256"] = body_sha3(s); write(st, s); rc, rep, out, un = resume(st)
probe("H11", rc == 4 and un and not tb(out), {"forged": "lines-1, hash recomputed", "rc": rc, "msg": out.strip()[-90:]})
st, s = crash_state("H12"); s["offset"] -= 1; s["body_sha256"] = body_sha3(s); write(st, s); rc, rep, out, un = resume(st)
probe("H12", rc in (2, 4) and un and not tb(out), {"forged": "offset-1, hash recomputed (prefix hash now differs)", "rc": rc, "msg": out.strip()[-90:]})
st, s = crash_state("H13"); s["extra"] = "x"; s["body_sha256"] = body_sha3(s); write(st, s); rc, rep, out, un = resume(st)
probe("H13", True, {"forged": "unknown top-level key, hash recomputed", "rc": rc, "same": strip(rep) == strip(full)}, graded=False)
st, s = crash_state("H14"); del s["body_sha256"]; write(st, s); rc, rep, out, un = resume(st)
probe("H14", rc == 4 and un and not tb(out), {"case": "body_sha256 missing", "rc": rc})
st, s = crash_state("H15"); s["body_sha256"] = 12345; write(st, s); rc, rep, out, un = resume(st)
probe("H15", rc == 4 and un and not tb(out), {"case": "body_sha256 a number", "rc": rc, "tb": tb(out)})
st, s = crash_state("H16"); s["lines"] = str(s["lines"]); s["body_sha256"] = body_sha3(s); write(st, s); rc, rep, out, un = resume(st)
probe("H16", rc == 4 and un and not tb(out), {"forged": "lines as a string, hash recomputed", "rc": rc, "tb": tb(out), "msg": out.strip()[-90:]})
st, s = crash_state("H17"); s["offset"] = 10 ** 12; s["body_sha256"] = body_sha3(s); write(st, s); rc, rep, out, un = resume(st)
probe("H17", rc in (2, 4) and un and not tb(out), {"forged": "offset past end of file, hash recomputed", "rc": rc, "tb": tb(out), "msg": out.strip()[-90:]})
st, s = crash_state("H18"); s["schema"] = "solaris.device-protocol-state/2"; write(st, s); rc, rep, out, un = resume(st)
probe("H18", rc == 2 and un and not tb(out), {"case": "schema /2 checkpoint", "rc": rc})
# non-object JSON and other damage
for pid, txt in [("N01", "1"), ("N02", "true"), ("N03", "[{}]"), ("N04", "{}"), ("N05", "\ufeff{}")]:
    st = os.path.join(T, f"st-{pid}.json"); open(st, "w").write(txt); rc, rep, out, un = resume(st)
    probe(pid, rc == 4 and un and not tb(out), {"checkpoint": txt, "rc": rc, "msg": out.strip()[-90:]}, graded=(pid != "N04"))  # N04 '{}' is an object with no schema: exit 2 'another tool' is also a reading of the doc, so recorded only
st = os.path.join(T, "st-N06.json"); open(st, "wb").write(b"\xff\xfe{"); rc, rep, out, un = resume(st)
probe("N06", rc == 4 and un and not tb(out), {"checkpoint": "invalid utf-8", "rc": rc, "tb": tb(out)})
st = os.path.join(T, "st-N07.json"); os.mkdir(st); p = subprocess.run([PY, TOOL, "ingest", "--commands", C, "--events", E, "--state", st, "--json"], capture_output=True, text=True, cwd=T, env=ENV)
probe("N07", p.returncode in (2, 4) and not tb(p.stdout + p.stderr), {"checkpoint": "a folder", "rc": p.returncode, "tb": tb(p.stdout + p.stderr)})
# lines recount with an unterminated last line, and growth after the crash
lines = open(E, "rb").read().split(b"\n"); body = [l for l in lines if l]
E2 = os.path.join(T, "e-unterm.jsonl"); open(E2, "wb").write(b"\n".join(body))  # no final newline
_, full2, _ = run(["ingest", "--commands", C, "--events", E2, "--json"])
st = os.path.join(T, "st-U1.json"); run(["ingest", "--commands", C, "--events", E2, "--state", st, "--crash-after", str(len(body) - 1)])
rc, rep, out = run(["ingest", "--commands", C, "--events", E2, "--state", st, "--json"])
probe("U01", rc == 1 and strip(rep) == strip(full2), {"case": "unterminated last line, crash before it, resume", "rc": rc, "same": strip(rep) == strip(full2)})
E3 = os.path.join(T, "e-grow.jsonl"); open(E3, "wb").write(b"\n".join(body[:-1]))  # stops mid-stream, no final newline
st = os.path.join(T, "st-U2.json"); rcA, _, _ = run(["ingest", "--commands", C, "--events", E3, "--state", st, "--crash-after", str(len(body) + 5)])
st_exists = os.path.exists(st)
open(E3, "wb").write(b"\n".join(body[:-1]) + b"\n" + body[-1] + b"\n")  # the file grows: newline then the last line
_, full3, _ = run(["ingest", "--commands", C, "--events", E3, "--json"])
rc, rep, out = run(["ingest", "--commands", C, "--events", E3, "--state", st, "--json"]) if st_exists else (None, None, "")
dk = sorted(k for k in set(strip(rep or {})) | set(strip(full3 or {})) if strip(rep or {}).get(k) != strip(full3 or {}).get(k))
probe("U02", True, {"case": "checkpoint written at an unterminated end, file then grows", "first_rc": rcA, "state_written": st_exists, "resume_rc": rc, "same_as_unbroken": strip(rep) == strip(full3) if rep else None,
      "differs": {k: [json.dumps((rep or {}).get(k))[:200], json.dumps((full3 or {}).get(k))[:200]] for k in dk}}, graded=False)
# --record ancestors
os.makedirs(os.path.join(T, "rd2"), exist_ok=True); open(os.path.join(T, "f2"), "w").write("x")
os.symlink(os.path.join(T, "nowhere"), os.path.join(T, "dang")); os.symlink(os.path.join(T, "rd2"), os.path.join(T, "ldir"))
for pid, rec, want, note in [("Q01", "f2/a/b/c", 2, "file three levels above"), ("Q02", "dang/sub", 2, "dangling symlink above"),
                             ("Q03", "ldir/sub", None, "symlinked folder above (doc silent)")]:
    rc, _, out = sim(rec)
    probe(pid, (rc == want and not tb(out)) if want else True, {"record": rec, "rc": rc, "tb": tb(out), "msg": out.strip()[-100:], "note": note}, graded=want is not None)
probe("Q04", not os.path.exists(os.path.join(T, "f2/a")) and open(os.path.join(T, "f2")).read() == "x", {"note": "nothing written under or over the file"})
os.makedirs(os.path.join(T, "ro"), exist_ok=True); os.chmod(os.path.join(T, "ro"), 0o555)
rc, _, out = sim("ro/sub"); os.chmod(os.path.join(T, "ro"), 0o755)
probe("Q05", rc == 2 and not tb(out), {"record": "read-only/sub", "rc": rc, "msg": out.strip()[-100:]})
rc, _, out = run(["ingest", "--commands", C, "--events", E, "--json", "--record", "f2/x"]) 
probe("Q06", True, {"note": "ingest with --record (is it accepted?)", "rc": rc, "msg": out.strip()[-80:]}, graded=False)
json.dump(res, open(os.path.join(OUT, "probes.json"), "w"), indent=1)
g = [r for r in res if r["result"] != "LIMIT"]
print("TOTAL %d/%d FAILS %s" % (sum(r["result"] == "PASS" for r in g), len(g), [r["id"] for r in g if r["result"] == "FAIL"]))
os.chmod(T, 0o755); shutil.rmtree(T, ignore_errors=True)
