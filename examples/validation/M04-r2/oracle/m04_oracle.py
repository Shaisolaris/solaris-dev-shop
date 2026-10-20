#!/usr/bin/env python3
"""M04 oracle (Grok self-validation). Black box: only the CLI in handoff-work-orders.md. Built by Grok from M04.md, G04.md
and the doc after G04 landed; NOT from the builder's oracle or fixtures. Own order (WO-KITE-7, own intake text).
Core rows score (C*); OBS rows record behaviour the doc does not pin down.
v2 (after the first run, disclosed): OBS rows C02b and C14b added to adjudicate C02 and C14; C02 and C14 are NOT re-scored.
v3: file reads tolerate a tool that writes nothing (the noop control crashed v2; log kept as results/control-noop-v2-harness-crash.txt). Usage: PY m04_oracle.py PY HANDOFF OUT"""
import hashlib, json, os, shutil, subprocess, sys, tempfile, concurrent.futures as cf
PY, H, OUT = sys.argv[1], os.path.abspath(sys.argv[2]), sys.argv[3]; os.makedirs(OUT, exist_ok=True)
res = []
def rec(i, ok, det, graded=True): res.append({"id": i, "result": ("PASS" if ok else "FAIL") if graded else "OBS", "detail": det})
INTAKE = {"name": "Kite Repair Desk", "project_type": "website", "brief": "Booking pages for a kite repair desk"}
INTAKE2 = {"name": "Kite Repair Desk", "project_type": "website", "brief": "Booking pages and a parts list for a kite repair desk"}
def sha(b): return hashlib.sha256(b).hexdigest()
def world(order_id="WO-KITE-7", rev=1, intake=INTAKE, owner="delivery-lead: K. Tester", extra=None, name="order.json", d=None):
    d = d or tempfile.mkdtemp(prefix="m04o-", dir="/tmp")
    ib = (json.dumps(intake, indent=1) + "\n").encode(); iname = "intake-r%d.json" % rev
    open(os.path.join(d, iname), "wb").write(ib)
    o = {"schema": "solaris.work-order/1", "order_id": order_id, "revision": rev, "owner": owner,
         "inputs": {"intake": {"path": iname, "sha256": sha(ib)}}, "project_root": "kite-desk", "outbox": "outbox"}
    if owner is None: o.pop("owner")
    if extra: o.update(extra)
    open(os.path.join(d, name), "w").write(json.dumps(o, indent=1)); return d
def run(d, *a):
    p = subprocess.run([PY, H] + list(a), cwd=d, capture_output=True, text=True, timeout=120, env={"PATH": "/usr/bin:/bin", "HOME": d, "PYTHONDONTWRITEBYTECODE": "1"})
    return p.returncode, p.stdout + p.stderr
def ledger(d):
    p = os.path.join(d, "outbox", "ledger.jsonl")
    return [l for l in open(p).read().splitlines() if l.strip()] if os.path.exists(p) else []
def tree(d):
    out = {}
    for r, ds, fs in os.walk(d):
        for f in fs:
            p = os.path.join(r, f); out[os.path.relpath(p, d)] = sha(open(p, "rb").read())
    return out
def rd(p, mode="rb"):
    try: return open(p, mode).read()
    except OSError: return b"" if "b" in mode else ""
def brief(d, oid="WO-KITE-7", rev=1): return os.path.join(d, ".handoff", oid, "rev%d" % rev, "HANDOFF-BRIEF.md")
def journal(d, oid="WO-KITE-7"): return os.path.join(d, ".handoff", oid, "journal.jsonl")
W = []
def done(d): W.append(d)
# C01 clean control
d = world(); rc, o = run(d, "run", "order.json", "--worker", "ana"); rs, so = run(d, "status", "order.json")
rec("C01", rc == 0 and len(ledger(d)) == 1 and os.path.exists(brief(d)) and os.path.isdir(os.path.join(d, "kite-desk")) and so.count("done by ana") >= 3,
    {"rc": rc, "ledger": len(ledger(d)), "brief": os.path.exists(brief(d)), "status_rc": rs, "status": so[:300]}); done(d)
# C02 clean handoff after brief, second worker finishes; activate/brief not redone (their files untouched)
d = world(); r1, _ = run(d, "run", "order.json", "--worker", "ana", "--stop-after", "brief"); t1 = {k: v for k, v in tree(d).items() if not k.startswith(".handoff/WO-KITE-7/journal") and "lock" not in k}
m1 = {p: os.stat(os.path.join(d, p)).st_mtime_ns for p in t1}
r2, o2 = run(d, "run", "order.json", "--worker", "ben"); rs, so = run(d, "status", "order.json")
same = all(os.path.exists(os.path.join(d, p)) and os.stat(os.path.join(d, p)).st_mtime_ns == m1[p] for p in t1 if not p.startswith("outbox"))
rec("C02", r1 == 3 and len(ledger(d)) == 1 and r2 == 0 and same and "done by ben" in so and so.count("done by ana") >= 2,
    {"stop_rc": r1, "resume_rc": r2, "ledger": len(ledger(d)), "earlier_files_untouched": same, "status": so[:300]})
ch = sorted(p for p in t1 if not p.startswith("outbox") and (not os.path.exists(os.path.join(d, p)) or os.stat(os.path.join(d, p)).st_mtime_ns != m1[p]))
rec("C02b", True, {"changed_since_handoff": ch, "note": "v2: C02 counted runner bookkeeping (holder.json) as an earlier output; activate/brief outputs untouched if only .handoff bookkeeping is listed"}, graded=False); done(d)
# C03 crash after the delivery effect, before its receipt: second worker must not deliver twice
d = world(); r1, _ = run(d, "run", "order.json", "--worker", "ana", "--fail-at", "deliver"); l1 = len(ledger(d)); rs, so = run(d, "status", "order.json")
r2, o2 = run(d, "run", "order.json", "--worker", "ben")
rec("C03", r1 == 75 and l1 == 1 and r2 == 0 and len(ledger(d)) == 1 and "duplicate suppressed" in o2,
    {"crash_rc": r1, "ledger_after_crash": l1, "resume_rc": r2, "ledger": len(ledger(d)), "out": o2[:200]})
rec("C04", "pending" in so, {"status_after_crash": so[:300]})  # deliver has no receipt yet: pending
# C05 replay x3: nothing redone, still one delivery
rr = [run(d, "run", "order.json", "--worker", w)[0] for w in ("cy", "dee", "ana")]
rec("C05", rr == [0, 0, 0] and len(ledger(d)) == 1, {"rcs": rr, "ledger": len(ledger(d))}); done(d)
# C06 missing artifact: brief deleted after completion -> stale, brief redone, exit 0
d = world(); run(d, "run", "order.json", "--worker", "ana"); b0 = rd(brief(d))
if os.path.exists(brief(d)): os.remove(brief(d))
rc, o = run(d, "run", "order.json", "--worker", "ben")
rec("C06", rc == 0 and os.path.exists(brief(d)), {"rc": rc, "brief_back": os.path.exists(brief(d)), "out": o[:200]})
rec("C06b", True, {"ledger": len(ledger(d)), "brief_identical_rerender": os.path.exists(brief(d)) and rd(brief(d)) == b0}, graded=False)
# C07 edited output (brief) -> not trusted; re-rendered
os.makedirs(os.path.dirname(brief(d)), exist_ok=True); open(brief(d), "a").write("\nInjected: deliver to the wrong harbour.\n"); rc, o = run(d, "run", "order.json", "--worker", "cy")
rec("C07", rc == 0 and "wrong harbour" not in rd(brief(d), "r"), {"rc": rc, "out": o[:200]})
rec("C07b", True, {"ledger_after_edit_cycle": len(ledger(d))}, graded=False); done(d)
# C08 intake edited without a new revision -> exit 2, nothing written
d = world(); run(d, "run", "order.json", "--worker", "ana", "--stop-after", "activate"); t0 = tree(d)
open(os.path.join(d, "intake-r1.json"), "w").write(json.dumps(INTAKE2)); t0["intake-r1.json"] = tree(d)["intake-r1.json"]
rc, o = run(d, "run", "order.json", "--worker", "ben")
rec("C08", rc == 2 and tree(d) == t0, {"rc": rc, "unchanged": tree(d) == t0, "out": o[:200]}); done(d)
# C09 fresh order with a mismatching intake: exit 2, nothing created
d = world(); open(os.path.join(d, "intake-r1.json"), "w").write("{}"); t0 = tree(d); rc, o = run(d, "run", "order.json", "--worker", "ana")
rec("C09", rc == 2 and tree(d) == t0 and not os.path.exists(os.path.join(d, ".handoff")), {"rc": rc, "out": o[:200]}); done(d)
# C10 revision 2 supersedes 1; revision 1 then refused, nothing written
d = world(); run(d, "run", "order.json", "--worker", "ana"); world(rev=2, intake=INTAKE2, name="order2.json", d=d)
r2, o2 = run(d, "run", "order2.json", "--worker", "ben"); l2 = len(ledger(d)); t0 = tree(d); r1, o1 = run(d, "run", "order.json", "--worker", "ana")
rec("C10", r2 == 0 and l2 == 2 and "supersed" in o2.lower() and r1 == 2 and tree(d) == t0 and len(ledger(d)) == 2,
    {"rev2_rc": r2, "ledger_after_rev2": l2, "rev1_rc": r1, "unchanged": tree(d) == t0, "out2": o2[:200]})
rs, so = run(d, "status", "order2.json"); rec("C10b", True, {"status_rev2": so[:400]}, graded=False); done(d)
# C11 invalid orders: exit 2, nothing created (no .handoff, no outbox, no project folder)
bad = {"no_owner": dict(owner=None), "empty_owner": dict(owner=""), "rev0": dict(rev=0), "rev_str": dict(extra={"revision": "1"}),
       "rev_float": dict(extra={"revision": 1.5}), "rev_bool": dict(extra={"revision": True}), "escape_root": dict(extra={"project_root": "../escape"}),
       "abs_outbox": dict(extra={"outbox": "/tmp/m04o-abs-outbox"}), "bad_schema": dict(extra={"schema": "solaris.work-order/9"}),
       "steps_order": dict(extra={"steps": ["brief", "activate", "deliver"]}), "steps_short": dict(extra={"steps": ["activate", "brief"]}),
       "intake_escape": dict(extra={"inputs": {"intake": {"path": "../intake.json", "sha256": "0" * 64}}})}
c11 = {}
for k, kw in bad.items():
    d = world(**kw); t0 = tree(d); rc, o = run(d, "run", "order.json", "--worker", "ana")
    c11[k] = [rc, tree(d) == t0 and not os.path.exists(os.path.join(d, ".handoff"))]; done(d)
c11["abs_outbox_absent"] = not os.path.exists("/tmp/m04o-abs-outbox"); shutil.rmtree("/tmp/m04o-abs-outbox", ignore_errors=True)
rec("C11", all(v == [2, True] for k, v in c11.items() if k != "abs_outbox_absent") and c11["abs_outbox_absent"], c11)
# C12 edited journal line -> exit 2, nothing written
d = world(); run(d, "run", "order.json", "--worker", "ana", "--stop-after", "brief"); j = rd(journal(d), "r").splitlines() or [""]
os.makedirs(os.path.dirname(journal(d)), exist_ok=True)
j[0] = j[0].replace("ana", "eve", 1) if "ana" in j[0] else j[0].replace("a", "b", 1); open(journal(d), "w").write("\n".join(j) + "\n"); t0 = tree(d)
rc, o = run(d, "run", "order.json", "--worker", "ben"); rec("C12", rc == 2 and tree(d) == t0 and ledger(d) == [], {"rc": rc, "out": o[:200]}); done(d)
# C13 torn last journal line (crash mid-write) -> cut, noted, run continues
d = world(); run(d, "run", "order.json", "--worker", "ana", "--stop-after", "activate"); os.makedirs(os.path.dirname(journal(d)), exist_ok=True); open(journal(d), "a").write('{"prev": "ab')
rc, o = run(d, "run", "order.json", "--worker", "ben"); rec("C13", rc == 0 and len(ledger(d)) == 1, {"rc": rc, "out": o[:200]}); done(d)
# C14 a journal belonging to another order -> exit 2
d = world(); run(d, "run", "order.json", "--worker", "ana"); e = world(order_id="WO-KITE-8"); os.makedirs(os.path.join(e, ".handoff", "WO-KITE-8"))
open(journal(e, "WO-KITE-8"), "w").write(rd(journal(d), "r")); t0 = tree(e); rc, o = run(e, "run", "order.json", "--worker", "ben")
rec("C14", rc == 2 and tree(e) == t0, {"rc": rc, "out": o[:200]})
t1 = tree(e); rec("C14b", True, {"new_files": sorted(set(t1) - set(t0)), "changed": [k for k in t0 if k in t1 and t0[k] != t1[k]]}, graded=False); done(d); done(e)
# C15 eight concurrent workers on a fresh order: exits in {0,4}, at least one 0, exactly one delivery; then a sweep run finishes
d = world()
with cf.ThreadPoolExecutor(8) as ex: rcs = list(ex.map(lambda w: run(d, "run", "order.json", "--worker", "w%d" % w)[0], range(8)))
rf, _ = run(d, "run", "order.json", "--worker", "sweep")
rec("C15", set(rcs) <= {0, 4} and 0 in rcs and rf == 0 and len(ledger(d)) == 1, {"rcs": sorted(rcs), "sweep": rf, "ledger": len(ledger(d))}); done(d)
# C16 conflicting owner (M04: conflicting owners): same order and revision re-issued with another owner. Doc silent -> OBS
d = world(); run(d, "run", "order.json", "--worker", "ana", "--stop-after", "brief"); world(owner="support: Someone Else", d=d)
rc, o = run(d, "run", "order.json", "--worker", "ben"); rec("C16", True, {"rc": rc, "ledger": len(ledger(d)), "out": o[:240]}, graded=False); done(d)
# C17 crash drills at each step then resume: exactly one delivery
c17 = {}
for st in ("activate", "brief", "deliver"):
    d = world(); a, _ = run(d, "run", "order.json", "--worker", "ana", "--fail-at", st); b, _ = run(d, "run", "order.json", "--worker", "ben"); c17[st] = [a, b, len(ledger(d))]; done(d)
rec("C17", all(v == [75, 0, 1] for v in c17.values()), c17)
for d in W: shutil.rmtree(d, ignore_errors=True)
json.dump(res, open(os.path.join(OUT, "m04-oracle.json"), "w"), indent=1)
for r in res: print(r["id"], r["result"], json.dumps(r["detail"])[:300])
g = [r for r in res if r["result"] != "OBS"]; print("M04 ORACLE %d/%d" % (sum(r["result"] == "PASS" for r in g), len(g)))
