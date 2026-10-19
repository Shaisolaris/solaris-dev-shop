#!/usr/bin/env python3
"""M25 r3 (Grok self-validation): show the 4 surviving r3g mutants are not equivalent. Usage: PY TOOL_DIR OUT"""
import json, os, re, shutil, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(__file__)); from r3_extra import R3
PY, SRC, OUT = sys.argv[1:4]
base = tempfile.mkdtemp(prefix="m25r3-dist-", dir="/tmp")
def make(name):
    d = os.path.join(base, name); os.makedirs(d); s = open(os.path.join(SRC, "device_protocol.py")).read()
    if name != "cand":
        a, b = R3[name]; assert s.count(a) == 1, name; s = s.replace(a, b)
    open(os.path.join(d, "device_protocol.py"), "w").write(s); return os.path.join(d, "device_protocol.py")
def run(tool, args, cwd):
    p = subprocess.run([PY, tool] + args, capture_output=True, text=True, cwd=cwd, env={"PATH": "/usr/bin:/bin", "HOME": cwd})
    return p.returncode, (p.stdout + p.stderr).strip()[-160:]
def case_record(tool, setup, rec):
    w = tempfile.mkdtemp(prefix="m25r3-dw-", dir="/tmp"); setup(w)
    rc, msg = run(tool, ["simulate", "--devices", "2", "--steps", "20", "--seed", "3", "--record", rec], w)
    shutil.rmtree(w, ignore_errors=True); return {"rc": rc, "msg": msg}
def f2(w): open(os.path.join(w, "f2"), "w").write("x")
def dang(w): os.symlink(os.path.join(w, "nowhere"), os.path.join(w, "dang"))
def case_recount(tool):
    w = tempfile.mkdtemp(prefix="m25r3-dw-", dir="/tmp")
    run(tool, ["simulate", "--devices", "4", "--steps", "100", "--seed", "5", "--record", "d/"], w)
    C, E = os.path.join(w, "d/commands.jsonl"), os.path.join(w, "d/events.jsonl")
    body = [l for l in open(E, "rb").read().split(b"\n") if l]
    open(E, "wb").write(b"\n".join(body))  # unterminated end
    st = os.path.join(w, "st.json")
    rcA, _ = run(tool, ["ingest", "--commands", C, "--events", E, "--state", st], w)
    s = json.load(open(st)) if os.path.exists(st) else None
    open(E, "ab").write(b"\n")  # the writer finishes the line
    rcB, msg = run(tool, ["ingest", "--commands", C, "--events", E, "--state", st, "--json"], w)
    shutil.rmtree(w, ignore_errors=True)
    return {"first_rc": rcA, "state": {k: s.get(k) for k in ("offset", "lines")} if s else None, "resume_rc": rcB, "msg": msg[-100:]}
tools = {n: make(n) for n in ("cand", "r3g_parent_walk_off", "r3g_parent_first_only", "r3g_parent_no_symlink", "r3g_recount_no_tail")}
res = {}
for n, t in tools.items():
    res[n] = {"file_3_up": case_record(t, f2, "f2/a/b/c"), "dangling_above": case_record(t, dang, "dang/sub"), "unterminated_then_finished": case_recount(t)}
json.dump(res, open(OUT, "w"), indent=1)
for n, r in res.items():
    print(n); [print("  ", k, json.dumps(v)) for k, v in r.items()]
shutil.rmtree(base, ignore_errors=True)
