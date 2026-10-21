#!/usr/bin/env python3
"""M04 r3 probe (Grok self-validation, not independent review). Black-box CLI checks written for this pass from
M04 P4-1 (an exit-2 refusal created an empty .handoff/<order>/.worker.lock in a new folder) and the G04 contract
(one delivery per order revision; refusals write nothing). Inputs chosen here, not copied from the G04 r4 test.
Usage: PY m04r3_probe.py REPO OUT.json"""
import json, os, shutil, subprocess, sys, tempfile
from pathlib import Path
REPO = Path(sys.argv[1]).resolve(); OUT = sys.argv[2]
TOOL = REPO / "employees/infrastructure/fleet-dispatcher/handoff.py"; FIX = REPO / "examples/capabilities/G04/fixtures"
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1"); ROWS = []
def row(rid, name, ok, detail): ROWS.append({"row": rid, "name": name, "pass": bool(ok), "detail": detail})
def world():
    t = Path(tempfile.mkdtemp(prefix="m04r3-")); d = t / "w"; shutil.copytree(str(FIX), str(d)); return t, d
def cli(d, *a, order="order.json"):
    p = subprocess.run([sys.executable, str(TOOL), a[0], str(d / order)] + list(a[1:]), cwd=str(d), env=ENV,
                       capture_output=True, text=True, timeout=120)
    return p.returncode, p.stderr.strip()[-200:]
def set_owner(d, who, name="order.json"):
    p = d / name; o = json.loads(p.read_text()); o["owner"] = who; p.write_text(json.dumps(o, indent=2) + "\n")
def tree(p):
    return sorted(str(x.relative_to(p)) for x in p.rglob("*")) if p.exists() else None
def ledger(d):
    p = d / "outbox" / "ledger.jsonl"; return len(p.read_text().strip().splitlines()) if p.exists() else 0
# Q1 owner change after delivery, brand new --state folder: nothing left
t, d = world(); r1 = cli(d, "run", "--worker", "ana"); set_owner(d, "ops: Other Person"); s = t / "s1"
r2 = cli(d, "run", "--worker", "ben", "--state", str(s))
row("Q1", "owner change after delivery into a new --state folder: exit 2, folder not left behind, ledger 1",
    r1[0] == 0 and r2[0] == 2 and not s.exists() and ledger(d) == 1, {"rc": [r1[0], r2[0]], "left": tree(s), "ledger": ledger(d)})
# Q2 same with an existing --state folder that holds another order: that order is untouched, no new subfolder
s2 = t / "s2"; s2.mkdir(); (s2 / "WO-KEEP").mkdir(); (s2 / "WO-KEEP" / "note.txt").write_text("keep")
r3 = cli(d, "run", "--worker", "ben", "--state", str(s2))
row("Q2", "refusal into an existing --state folder with another order: exit 2, only WO-KEEP/note.txt remains",
    r3[0] == 2 and tree(s2) == ["WO-KEEP", "WO-KEEP/note.txt"], {"rc": r3[0], "tree": tree(s2)})
# Q3 deep new --state path (several missing parents)
s3 = t / "a" / "b" / "c"
r4 = cli(d, "run", "--worker", "ben", "--state", str(s3))
row("Q3", "refusal into a deep new --state path a/b/c: exit 2, no lock and no order folder (empty parents observed)",
    r4[0] == 2 and not (s3 / "WO-HARBOR-1").exists(), {"rc": r4[0], "a_tree": tree(t / "a")})
# Q4 refusal in the default .handoff folder that already holds the order keeps lock, journal and receipts
before = tree(d / ".handoff"); r5 = cli(d, "run", "--worker", "ben")
row("Q4", "refusal in the existing order folder: exit 2, files unchanged", r5[0] == 2 and tree(d / ".handoff") == before,
    {"rc": r5[0], "same": tree(d / ".handoff") == before})
shutil.rmtree(str(t), True)
# Q5 a held lock is not removed by a second worker (exit 4) and the holder still finishes
t, d = world(); import fcntl
sd = d / ".handoff" / "WO-HARBOR-1"; sd.mkdir(parents=True); lk = open(str(sd / ".worker.lock"), "w"); fcntl.flock(lk, fcntl.LOCK_EX)
r6 = cli(d, "run", "--worker", "ben"); exists = (sd / ".worker.lock").exists(); fcntl.flock(lk, fcntl.LOCK_UN); lk.close()
r7 = cli(d, "run", "--worker", "ana")
row("Q5", "held lock: second worker exits 4 and the lock stays; the holder can then run (exit 0)", r6[0] == 4 and exists and r7[0] == 0,
    {"rc": [r6[0], r7[0]], "lock_kept": exists})
shutil.rmtree(str(t), True)
# Q6 intake JSON that is not an object, fresh order: refused before anything is created
t, d = world(); o = json.loads((d / "order.json").read_text()); import hashlib
ip = d / o["inputs"]["intake"]["path"]; ip.write_text("[1, 2]"); o["inputs"]["intake"]["sha256"] = hashlib.sha256(ip.read_bytes()).hexdigest()
(d / "order.json").write_text(json.dumps(o, indent=2) + "\n"); r8 = cli(d, "run", "--worker", "ana")
row("Q6", "intake that is valid JSON but not an object, fresh order: exit 2, no .handoff and no outbox",
    r8[0] == 2 and not (d / ".handoff").exists() and not (d / "outbox").exists(), {"rc": r8[0], "err": r8[1], "handoff": tree(d / ".handoff")})
shutil.rmtree(str(t), True)
# Q7 control: normal run then rerun, one delivery
t, d = world(); a = cli(d, "run", "--worker", "ana"); b = cli(d, "run", "--worker", "ben")
row("Q7", "control: run then rerun exit 0, ledger 1", a[0] == 0 and b[0] == 0 and ledger(d) == 1, {"rc": [a[0], b[0]], "ledger": ledger(d)})
shutil.rmtree(str(t), True)
for r in ROWS: print(r["row"], "PASS" if r["pass"] else "FAIL", r["name"], "|", json.dumps(r["detail"])[:400])
n = sum(r["pass"] for r in ROWS); print("M04R3 PROBE %d/%d" % (n, len(ROWS))); json.dump(ROWS, open(OUT, "w"), indent=1)
sys.exit(0 if n == len(ROWS) else 1)
