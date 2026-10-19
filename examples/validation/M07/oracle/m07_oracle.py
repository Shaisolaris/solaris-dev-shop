#!/usr/bin/env python3
"""M07 oracle (Grok self-validation, written by Grok, black box; expectations from fleet-registration.md,
handoff-work-orders.md and G07/README.md, never from the tool's output).
Usage: PY m07_oracle.py REPO [--tool REGISTRY.py] OUT.json
Core rows (C*) score; OBS rows record only."""
import json, os, random, shutil, signal, subprocess, sys, tempfile, time, hashlib
from pathlib import Path
REPO = Path(sys.argv[1]).resolve(); args = sys.argv[2:]
TOOL = REPO / "employees/infrastructure/fleet-provisioner/registry.py"
if args and args[0] == "--tool": TOOL = Path(args[1]).resolve(); args = args[2:]
OUT = args[0]; PY = sys.executable
H = REPO / "employees/infrastructure/fleet-dispatcher/handoff.py"
FIX = REPO / "examples/capabilities/G07/fixtures"; G04 = REPO / "examples/capabilities/G04/fixtures"
ENV = {"PATH": "/usr/bin:/bin", "HOME": "/tmp", "PYTHONDONTWRITEBYTECODE": "1", "LC_ALL": "C"}
rows = []
TOP = Path(tempfile.mkdtemp(prefix="m07top-", dir="/tmp")).resolve()  # v3: private parent dir; cleanup removes only this run's folders
def row(rid, ok, detail, obs=False):
    rows.append({"id": rid, "kind": "OBS" if obs else "core", "result": "OBS" if obs else ("PASS" if ok else "FAIL"), "detail": detail})
def R(*a, cwd=None, env=None, timeout=60):
    p = subprocess.run([PY, str(TOOL)] + [str(x) for x in a], cwd=cwd, env=env or ENV, capture_output=True, text=True, timeout=timeout)
    return p.returncode, p.stdout, p.stderr
def snap(d):
    d = Path(d); return {str(p.relative_to(d)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(d.rglob("*")) if p.is_file() and p.name != ".registry.lock"}
def status(root):
    rc, o, e = R("status", "--root", root)
    try: return rc, json.loads(o)["machines"]
    except Exception: return rc, None
def new():
    t = Path(tempfile.mkdtemp(prefix="m07o-", dir=str(TOP))).resolve(); (t / "fleet").mkdir(); shutil.copytree(FIX, t / "id")
    for i in range(3, 70):
        (t / "id" / ("gen-%02d.json" % i)).write_text(json.dumps({"machine_id": "synth-%04d-node" % i}))
    return t, t / "fleet"
def ident(t, n): return t / "id" / ("identity-%s.json" % n)
def guard(rid, f):
    try: f()
    except Exception as e: row(rid, False, "harness or tool crash: %r" % (e,))
def reg(root, alias, idf, owner, req, *extra): return R("register", "--root", root, "--alias", alias, "--identity", idf, "--owner", owner, "--request-id", req, *extra)[0]
def xfer(root, alias, fo, ep, to, req, *extra): return R("transfer", "--root", root, "--alias", alias, "--from-owner", fo, "--expect-epoch", ep, "--to-owner", to, "--request-id", req, *extra)[0]
def claim(root, alias, idf, owner, ep): return R("claim", "--root", root, "--alias", alias, "--identity", idf, "--owner", owner, "--epoch", ep)[0]
def m_of(ms, alias): return [m for m in (ms or []) if m.get("alias") == alias]

def c01():  # clean control
    t, f = new(); rc = reg(f, "mini1", ident(t, "mini1"), "ana", "reg-1"); s, ms = status(f)
    fl = (f / "FLEET.md").read_text() if (f / "FLEET.md").exists() else ""
    ok = rc == 0 and s == 0 and len(ms or []) == 1 and ms[0].get("owner") == "ana" and ms[0].get("owner_epoch") == 1 and ms[0].get("machine_id") == "mini-7f3a-0001" and "mini1" in fl and claim(f, "mini1", ident(t, "mini1"), "ana", 1) == 0
    row("C01_clean_register_claim", ok, {"rc": rc, "machines": ms, "fleet_md_has_alias": "mini1" in fl})
def c02():  # concurrent registration races: same machine, 8 racers, 8 aliases, distinct request ids
    t, f = new(); ps = [subprocess.Popen([PY, str(TOOL), "register", "--root", str(f), "--alias", "race%d" % i, "--identity", str(ident(t, "mini1")), "--owner", "own%d" % i, "--request-id", "rr-%d" % i], env=ENV, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) for i in range(8)]
    rcs = [p.wait(60) for p in ps]; s, ms = status(f)
    ok = sorted(rcs).count(0) == 1 and sorted(rcs).count(2) == 7 and len(ms or []) == 1
    row("C02_race_same_machine_8_aliases", ok, {"rcs": rcs, "machines": len(ms or [])})
def c03():  # race: 8 different machines on one alias
    t, f = new(); ps = [subprocess.Popen([PY, str(TOOL), "register", "--root", str(f), "--alias", "hot", "--identity", str(t / "id" / ("gen-%02d.json" % (i + 3))), "--owner", "ana", "--request-id", "ra-%d" % i], env=ENV, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) for i in range(8)]
    rcs = [p.wait(60) for p in ps]; s, ms = status(f)
    ok = rcs.count(0) == 1 and rcs.count(2) == 7 and len(ms or []) == 1
    row("C03_race_8_machines_one_alias", ok, {"rcs": rcs, "machines": len(ms or [])})
def c04():  # race: same request id from 6 processes (retry storm)
    t, f = new(); ps = [subprocess.Popen([PY, str(TOOL), "register", "--root", str(f), "--alias", "mini1", "--identity", str(ident(t, "mini1")), "--owner", "ana", "--request-id", "same-1"], env=ENV, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True) for i in range(6)]
    outs = [(p.wait(60), p.stdout.read()) for p in ps]; s, ms = status(f)
    ops = [json.loads(l) for l in (f / "ops.jsonl").read_text().splitlines()] if (f / "ops.jsonl").exists() else []
    commits = [o for o in ops if o.get("phase") == "commit"]
    ok = all(rc == 0 for rc, _ in outs) and len(ms or []) == 1 and len(commits) == 1
    row("C04_retry_storm_same_request", ok, {"rcs": [r for r, _ in outs], "machines": len(ms or []), "commits": len(commits)})
def c05():  # race: 8 transfers from one view
    t, f = new(); reg(f, "mini1", ident(t, "mini1"), "ana", "reg-1")
    ps = [subprocess.Popen([PY, str(TOOL), "transfer", "--root", str(f), "--alias", "mini1", "--from-owner", "ana", "--expect-epoch", "1", "--to-owner", "o%d" % i, "--request-id", "tx-%d" % i], env=ENV, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) for i in range(8)]
    rcs = [p.wait(60) for p in ps]; s, ms = status(f); m = m_of(ms, "mini1")
    ok = rcs.count(0) == 1 and rcs.count(2) == 7 and len(m) == 1 and m[0]["owner_epoch"] == 2 and m[0]["owner"] == "o%d" % rcs.index(0)
    row("C05_race_8_transfers_one_view", ok, {"rcs": rcs, "machine": m})
def c06():  # wrong machine, same hostname; and missing/garbled identity
    t, f = new(); reg(f, "mini1", ident(t, "mini1"), "ana", "reg-1"); b = snap(f)
    (t / "bad.json").write_text("{nope"); (t / "upper.json").write_text(json.dumps({"machine_id": "MINI-7F3A-0001"}))
    r = [claim(f, "mini1", ident(t, "impostor"), "ana", 1), claim(f, "mini1", t / "missing.json", "ana", 1), claim(f, "mini1", t / "bad.json", "ana", 1), claim(f, "mini1", ident(t, "mini2"), "ana", 1)]
    ok = r == [2, 2, 2, 2] and snap(f) == b and claim(f, "mini1", ident(t, "mini1"), "ana", 1) == 0
    row("C06_wrong_machine_cannot_claim", ok, {"rcs": r, "unchanged": snap(f) == b})
    row("C06b_case_variant_identity_claim", True, {"claim_rc_with_MINI-7F3A-0001": claim(f, "mini1", t / "upper.json", "ana", 1), "register_second_alias_rc": reg(f, "minix", t / "upper.json", "ana", "reg-up")}, obs=True)
def c07():  # epoch and stale owner
    t, f = new(); reg(f, "mini1", ident(t, "mini1"), "ana", "reg-1"); x1 = xfer(f, "mini1", "ana", 1, "ben", "t-1"); b = snap(f)
    r = {"old_owner_old_epoch_claim": claim(f, "mini1", ident(t, "mini1"), "ana", 1), "new_owner_old_epoch_claim": claim(f, "mini1", ident(t, "mini1"), "ben", 1),
         "old_owner_new_epoch_claim": claim(f, "mini1", ident(t, "mini1"), "ana", 2), "future_epoch_claim": claim(f, "mini1", ident(t, "mini1"), "ben", 3),
         "stale_transfer_old_owner": xfer(f, "mini1", "ana", 1, "cy", "t-2"), "stale_transfer_right_owner_old_epoch": xfer(f, "mini1", "ben", 1, "cy", "t-3"),
         "transfer_wrong_owner_right_epoch": xfer(f, "mini1", "ana", 2, "cy", "t-4"), "self_transfer": xfer(f, "mini1", "ben", 2, "ben", "t-5"),
         "reregister_by_old_owner": reg(f, "mini1", ident(t, "mini1"), "ana", "reg-9")}
    unchanged = snap(f) == b; good = claim(f, "mini1", ident(t, "mini1"), "ben", 2)
    ok = x1 == 0 and all(v == 2 for v in r.values()) and unchanged and good == 0
    row("C07_stale_owner_and_epoch", ok, dict(r, transfer=x1, unchanged=unchanged, current_claim=good))
    x2 = xfer(f, "mini1", "ben", 2, "ana", "t-6"); s, ms = status(f); m = m_of(ms, "mini1")
    ok = x2 == 0 and m and m[0]["owner_epoch"] == 3 and claim(f, "mini1", ident(t, "mini1"), "ana", 1) == 2 and claim(f, "mini1", ident(t, "mini1"), "ana", 3) == 0
    row("C08_abab_old_epoch_stays_stale", ok, {"transfer_back": x2, "machine": m})
def c09():  # crash drills
    t, f = new(); reg(f, "mini1", ident(t, "mini1"), "ana", "reg-1")
    a = xfer(f, "mini1", "ana", 1, "ben", "t-1", "--fail-at", "before-replace"); s, ms = status(f); m1 = m_of(ms, "mini1")
    c_prior = claim(f, "mini1", ident(t, "mini1"), "ana", 1)
    b = xfer(f, "mini1", "ana", 1, "ben", "t-1"); s, ms = status(f); m2 = m_of(ms, "mini1")
    ok = a == 75 and m1 and m1[0]["owner"] == "ana" and m1[0]["owner_epoch"] == 1 and c_prior == 0 and b == 0 and m2[0]["owner"] == "ben" and m2[0]["owner_epoch"] == 2
    row("C09_crash_before_replace_prior_owner_kept", ok, {"drill": a, "after_drill": m1, "prior_claim": c_prior, "retry": b, "after_retry": m2})
    a = xfer(f, "mini1", "ben", 2, "cy", "t-2", "--fail-at", "after-replace"); s, ms = status(f); m1 = m_of(ms, "mini1")
    b = xfer(f, "mini1", "ben", 2, "cy", "t-2"); s2, ms2 = status(f); m2 = m_of(ms2, "mini1")
    ok = a == 75 and m1 and m1[0]["owner"] == "cy" and m1[0]["owner_epoch"] == 3 and b == 0 and m2 == m1
    row("C10_crash_after_replace_settles_once", ok, {"drill": a, "after_drill": m1, "retry": b, "after_retry": m2})
def c11():  # real SIGKILL at random points during transfers; invariants hold
    random.seed(7); bad = []; t, f = new(); reg(f, "mini1", ident(t, "mini1"), "ana", "reg-1"); owner, ep = "ana", 1
    for i in range(30):
        to = "w%d" % i; p = subprocess.Popen([PY, str(TOOL), "transfer", "--root", str(f), "--alias", "mini1", "--from-owner", owner, "--expect-epoch", str(ep), "--to-owner", to, "--request-id", "k-%d" % i], env=ENV, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(random.uniform(0.0, 0.06)); p.send_signal(signal.SIGKILL); p.wait()
        s, ms = status(f); m = m_of(ms, "mini1")
        if s != 0 or len(m) != 1: bad.append((i, "status", s)); break
        m = m[0]
        if (m["owner"], m["owner_epoch"]) not in ((owner, ep), (to, ep + 1)): bad.append((i, "state", m)); break
        rc = xfer(f, "mini1", owner, ep, to, "k-%d" % i); s, ms = status(f); m2 = m_of(ms, "mini1")[0]
        if rc != 0 or (m2["owner"], m2["owner_epoch"]) != (to, ep + 1): bad.append((i, "retry", rc, m2)); break
        owner, ep = to, ep + 1
    left = sorted(p.name for p in f.iterdir() if p.name.startswith(".reg-"))
    row("C11_sigkill_mid_change_30x", not bad, {"bad": bad, "final": (owner, ep)})
    row("C11b_temp_files_left_after_sigkill", True, {"leftover_tmp": left}, obs=True)
def c12():  # hand-edit detection
    t, f = new(); reg(f, "mini1", ident(t, "mini1"), "ana", "reg-1"); p = f / "registry.json"; orig = p.read_bytes()
    st = json.loads(orig); st["machines"][0]["owner"] = "mallory"; p.write_text(json.dumps(st, indent=2, sort_keys=True) + "\n")
    r = {"claim_edited_owner": claim(f, "mini1", ident(t, "mini1"), "mallory", 1), "claim_orig_owner": claim(f, "mini1", ident(t, "mini1"), "ana", 1),
         "status": status(f)[0], "transfer": xfer(f, "mini1", "mallory", 1, "eve", "t-e"), "register": reg(f, "mini2", ident(t, "mini2"), "ana", "reg-2")}
    p.write_bytes(orig); restored = claim(f, "mini1", ident(t, "mini1"), "ana", 1)
    p.write_bytes(orig.replace(b"\n", b"\r\n")); ws = claim(f, "mini1", ident(t, "mini1"), "ana", 1); p.write_bytes(orig)
    ok = all(v == 2 for v in r.values()) and restored == 0 and ws == 2
    row("C12_hand_edit_refused_everywhere_restore_works", ok, dict(r, restored_claim=restored, whitespace_only_edit_claim=ws))
    (f / "FLEET.md").write_text("| mini1 | mallory |\n"); r2 = claim(f, "mini1", ident(t, "mini1"), "ana", 1); reg(f, "mini2", ident(t, "mini2"), "ana", "reg-3")
    row("C12b_fleet_md_hand_edit", True, {"claim_rc_after_fleet_md_edit": r2, "fleet_md_rerendered_on_next_change": "mallory" not in (f / "FLEET.md").read_text()}, obs=True)
    t, f = new(); reg(f, "mini1", ident(t, "mini1"), "ana", "reg-1"); (f / "ops.jsonl").unlink()
    row("C13_ops_log_deleted_refused", claim(f, "mini1", ident(t, "mini1"), "ana", 1) == 2 and reg(f, "mini2", ident(t, "mini2"), "ana", "r2") == 2, {})
    t, f = new(); reg(f, "mini1", ident(t, "mini1"), "ana", "reg-1"); o = f / "ops.jsonl"; lines = o.read_bytes().splitlines(True)
    o.write_bytes(lines[0] + b"garbage\n" + b"".join(lines[1:])); r3 = claim(f, "mini1", ident(t, "mini1"), "ana", 1)
    o.write_bytes(b"".join(lines) + b'{"phase":"commit","request_id":"x"'); r4 = claim(f, "mini1", ident(t, "mini1"), "ana", 1); torn_cut = o.read_bytes() == b"".join(lines)
    row("C14_ops_corrupt_stops_torn_tail_cut", r3 == 2 and r4 == 0 and torn_cut, {"mid_garbage_claim": r3, "torn_tail_claim": r4, "torn_cut": torn_cut})
def c15():  # request id reuse; retire; retired alias
    t, f = new(); reg(f, "mini1", ident(t, "mini1"), "ana", "reg-1"); b = snap(f)
    r = {"reuse_for_other_machine": reg(f, "mini2", ident(t, "mini2"), "ana", "reg-1"), "reuse_for_transfer": xfer(f, "mini1", "ana", 1, "ben", "reg-1")}
    ok = all(v == 2 for v in r.values()) and snap(f) == b and reg(f, "mini1", ident(t, "mini1"), "ana", "reg-1") == 0 and snap(f) == b
    row("C15_request_id_reuse_refused_repeat_noop", ok, r)
    rr = R("retire", "--root", f, "--alias", "mini1", "--from-owner", "ana", "--expect-epoch", 1, "--request-id", "x-1")[0]
    r = {"retire": rr, "claim_retired": claim(f, "mini1", ident(t, "mini1"), "ana", 2), "reuse_alias_other_machine": reg(f, "mini1", ident(t, "mini2"), "ana", "r-5"),
         "transfer_retired": xfer(f, "mini1", "ana", 2, "ben", "t-9"), "stale_retire": R("retire", "--root", f, "--alias", "mini1", "--from-owner", "ana", "--expect-epoch", 1, "--request-id", "x-2")[0]}
    ok = rr == 0 and all(v == 2 for k, v in r.items() if k != "retire")
    row("C16_retire_blocks_work_and_alias", ok, r)
    row("C16b_retired_machine_new_alias", True, {"register_same_machine_new_alias_rc": reg(f, "mini1b", ident(t, "mini1"), "ana", "r-6")}, obs=True)
def c17():  # invalid inputs leave nothing; missing root not created
    t, f = new(); b = snap(f)
    bad = [reg(f, "Mini1", ident(t, "mini1"), "ana", "a1"), reg(f, "mini1", ident(t, "mini1"), "a|b", "a2"), reg(f, "mini1", ident(t, "mini1"), "ana", "bad id"),
           reg(f, "../x", ident(t, "mini1"), "ana", "a3"), reg(f, "mini1", ident(t, "mini1"), " ", "a4"), R("transfer", "--root", f, "--alias", "mini1", "--from-owner", "ana", "--expect-epoch", "x", "--to-owner", "b", "--request-id", "a5")[0],
           reg(t / "nope", "mini1", ident(t, "mini1"), "ana", "a6")]
    un = snap(f) == b; nope = (t / "nope").exists(); pos = reg(f, "mini1", ident(t, "mini1"), "ana", "a7")
    ok = all(x == 2 for x in bad) and un and not nope and pos == 0  # v2: detail captured before the positive control
    row("C17_invalid_inputs_create_nothing", ok, {"rcs": bad, "unchanged": un, "nope_created": nope, "positive_control": pos})
def c18():  # scale: 40 machines, 4 concurrent registrars each retrying and trying a duplicate alias
    t, f = new(); n = 40
    sc = t / "w.py"; sc.write_text("import subprocess,sys\nPY,T,F,ID,k=sys.argv[1:6]\nfor i in range(int(k),40,4):\n for rq,al in (('r%d'%i,'m%d'%i),('r%d'%i,'m%d'%i),('d%d'%i,'dup%d'%i)):\n  subprocess.run([PY,T,'register','--root',F,'--alias',al,'--identity',ID+'/gen-%02d.json'%(i+3),'--owner','own%d'%i,'--request-id',rq],capture_output=True)\n")
    ps = [subprocess.Popen([PY, str(sc), PY, str(TOOL), str(f), str(t / "id"), str(k)], env=ENV) for k in range(4)]
    [p.wait(300) for p in ps]; s, ms = status(f); ids = [m["machine_id"] for m in ms or []]
    ok = len(ms or []) == n and len(set(ids)) == n and not any(m["alias"].startswith("dup") for m in ms or [])
    row("C18_scale_40_machines_4_registrars", ok, {"machines": len(ms or []), "distinct": len(set(ids))})
def handoff_case(t, f, order_extra, ident_path, env_extra=None):
    w = t / ("wo-%d" % random.randrange(10**9)); shutil.copytree(G04, w)
    o = json.loads((w / "order.json").read_text()); o.update(order_extra); (w / "order.json").write_text(json.dumps(o))
    env = dict(ENV); env.update(env_extra or {})
    a = [PY, str(H), "run", str(w / "order.json"), "--worker", "ana"] + (["--identity", str(ident_path)] if ident_path else [])
    p = subprocess.run(a, cwd=w, env=env, capture_output=True, text=True, timeout=120)
    led = w / "outbox" / "ledger.jsonl"; n = len(led.read_text().splitlines()) if led.exists() else 0
    created = sorted(str(x.relative_to(w)) for x in w.rglob("*") if not (G04 / x.relative_to(w)).exists())
    return p.returncode, n, created, w
def c19():  # G04 runner gate
    t, f = new(); OW = "delivery-lead: A. Example"
    reg(f, "mini1", ident(t, "mini1"), OW, "reg-1"); fe = {"SOLARIS_FLEET_ROOT": str(f)}
    r = {}
    r["impostor"] = handoff_case(t, f, {"fleet": {"machine": "mini1", "owner_epoch": 1}}, ident(t, "impostor"), fe)[:3]
    r["no_identity"] = handoff_case(t, f, {"fleet": {"machine": "mini1", "owner_epoch": 1}}, None, fe)[:3]
    r["wrong_epoch"] = handoff_case(t, f, {"fleet": {"machine": "mini1", "owner_epoch": 2}}, ident(t, "mini1"), fe)[:3]
    r["good"] = handoff_case(t, f, {"fleet": {"machine": "mini1", "owner_epoch": 1}}, ident(t, "mini1"), fe)[:3]
    xfer(f, "mini1", OW, 1, "someone-else", "t-1")
    r["after_transfer"] = handoff_case(t, f, {"fleet": {"machine": "mini1", "owner_epoch": 1}}, ident(t, "mini1"), fe)[:3]
    r["plain_order_no_fleet"] = handoff_case(t, f, {}, None, {})[:2]
    ok = all(r[k][0] == 2 and r[k][1] == 0 and r[k][2] == [] for k in ("impostor", "no_identity", "wrong_epoch", "after_transfer")) and r["good"][:2] == (0, 1) and r["plain_order_no_fleet"] == (0, 1)
    row("C19_handoff_gate_refuses_with_nothing_created", ok, r)
def c20():  # registry path confinement
    t, f = new(); OW = "delivery-lead: A. Example"; reg(f, "mini1", ident(t, "mini1"), OW, "reg-1"); r = {}
    for name, rel in (("dotdot", "../fleet"), ("absolute", str(f)), ("empty", ""), ("nul", "a\x00b")):
        r[name] = handoff_case(t, f, {"fleet": {"machine": "mini1", "owner_epoch": 1, "registry": rel}}, ident(t, "mini1"))[:3]
    w = t / "wo-link"; shutil.copytree(G04, w); os.symlink(str(f), str(w / "reglink"))
    o = json.loads((w / "order.json").read_text()); o["fleet"] = {"machine": "mini1", "owner_epoch": 1, "registry": "reglink"}; (w / "order.json").write_text(json.dumps(o))
    p = subprocess.run([PY, str(H), "run", str(w / "order.json"), "--worker", "ana", "--identity", str(ident(t, "mini1"))], cwd=w, env=ENV, capture_output=True, text=True)
    led = w / "outbox" / "ledger.jsonl"; r["symlink_out"] = (p.returncode, len(led.read_text().splitlines()) if led.exists() else 0)
    # inside the folder: a registry folder within the order folder works
    w2 = t / "wo-in"; shutil.copytree(G04, w2); shutil.copytree(f, w2 / "fleet")
    o = json.loads((w2 / "order.json").read_text()); o["fleet"] = {"machine": "mini1", "owner_epoch": 1, "registry": "fleet"}; (w2 / "order.json").write_text(json.dumps(o))
    p = subprocess.run([PY, str(H), "run", str(w2 / "order.json"), "--worker", "ana", "--identity", str(ident(t, "mini1"))], cwd=w2, env=ENV, capture_output=True, text=True)
    led = w2 / "outbox" / "ledger.jsonl"; r["inside_ok"] = (p.returncode, len(led.read_text().splitlines()) if led.exists() else 0)
    ok = all(r[k][0] == 2 and r[k][1] == 0 for k in ("dotdot", "absolute", "empty", "nul", "symlink_out")) and all(r[k][2] == [] for k in ("dotdot", "absolute", "empty", "nul")) and r["inside_ok"] == (0, 1)
    row("C20_registry_path_confined", ok, r)
def c21():  # __pycache__ leftover: run as a caller would (no PYTHONDONTWRITEBYTECODE) on a copy of the repo
    t, f = new(); cp = t / "repo"; shutil.copytree(REPO, cp, ignore=shutil.ignore_patterns(".git", "__pycache__"))
    tool = cp / TOOL.relative_to(REPO) if str(TOOL).startswith(str(REPO)) else TOOL
    env = {"PATH": "/usr/bin:/bin", "HOME": str(t)}
    OW = "delivery-lead: A. Example"
    subprocess.run([PY, str(tool), "register", "--root", str(f), "--alias", "mini1", "--identity", str(ident(t, "mini1")), "--owner", OW, "--request-id", "r1"], env=env, capture_output=True)
    w = t / "wo"; shutil.copytree(G04, w); o = json.loads((w / "order.json").read_text()); o["fleet"] = {"machine": "mini1", "owner_epoch": 1}; (w / "order.json").write_text(json.dumps(o))
    p = subprocess.run([PY, str(cp / H.relative_to(REPO)), "run", str(w / "order.json"), "--worker", "ana", "--identity", str(ident(t, "mini1"))], cwd=w, env=dict(env, SOLARIS_FLEET_ROOT=str(f)), capture_output=True, text=True)
    pc = sorted(str(x.relative_to(cp)) for x in cp.rglob("__pycache__"))
    row("C21_no_pycache_left_in_repo_after_fleet_order", p.returncode == 0 and pc == [], {"run_rc": p.returncode, "pycache_dirs": pc})
def s1():
    src = TOOL.read_text(); bad = [m for m in ("import subprocess", "import socket", "urllib", "http.client") if m in src]
    row("C22_static_no_subprocess_network", not bad, {"found": bad})
for rid, fn in (("C01", c01), ("C02", c02), ("C03", c03), ("C04", c04), ("C05", c05), ("C06", c06), ("C07", c07), ("C09", c09), ("C11", c11), ("C12", c12), ("C15", c15), ("C17", c17), ("C18", c18), ("C19", c19), ("C20", c20), ("C21", c21), ("C22", s1)):
    guard(rid, fn)
shutil.rmtree(TOP, ignore_errors=True)
json.dump(rows, open(OUT, "w"), indent=1, default=str)
core = [r for r in rows if r["kind"] == "core"]
for r in rows: print(r["id"], r["result"], json.dumps(r["detail"], default=str)[:300])
print("M07 ORACLE %d/%d core PASS" % (sum(r["result"] == "PASS" for r in core), len(core)))
