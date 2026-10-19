#!/usr/bin/env python3
"""M39 oracle (Grok self-validation, not independent review). Written from M39.md, G39.md and delivery-evidence.md
before reading the builder's drill_oracle.py. It builds its own delivery folders (a G04 work order, a G13 reconciliation,
a G03 snapshot of a SQLite folder it creates, a ROOT-local script) and drives the real CLIs. D rows are scored;
O rows are observations (always pass, not scored). Usage: PY m39_oracle.py SRC OUT.json [--tool PATH]."""
import hashlib, json, os, shutil, signal, sqlite3, subprocess, sys, tempfile, time
SRC = os.path.abspath(sys.argv[1]); OUT = sys.argv[2]; PY = sys.executable
TOOL = os.path.join(SRC, "employees/product-project/delivery-lead/delivery_evidence.py")
if "--tool" in sys.argv: TOOL = os.path.abspath(sys.argv[sys.argv.index("--tool") + 1])
HO = os.path.join(SRC, "employees/infrastructure/fleet-dispatcher/handoff.py")
CSV = os.path.join(SRC, "employees/data/data-engineer/csv_reconcile.py")
SQ = os.path.join(SRC, "employees/infrastructure/database-administrator/sqlite_recovery.py")
FX = os.path.join(SRC, "examples/capabilities/G39/fixtures"); G13 = os.path.join(SRC, "examples/capabilities/G13/fixtures")
# a tool that offers --inputs (the M39 proposed fix) is told the reconciliation reads data/; the candidate has no such flag
INPUTS = ["--inputs", "data"] if "\"--inputs\"" in open(TOOL).read() else []
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1"); ROWS = []
DE, DBA, SCR = "data/data-engineer", "infrastructure/database-administrator", "engineering/backend-developer"

def row(name, ok, det):
    sub = {k: bool(v[0]) for k, v in det.items() if isinstance(v, (tuple, list)) and len(v) == 2 and isinstance(v[0], bool)}
    ROWS.append({"row": name, "pass": bool(ok), "sub": sub, "detail": det})
    print(("PASS " if ok else "FAIL ") + name[:110] + " " + json.dumps(det, default=str)[:600], flush=True)
def safe(fn):
    def g():
        try: fn()
        except Exception as e: row(fn.__name__ + " crash", False, {"crash": repr(e)[:300]})
    return g
def run(root, *a, timeout=300):
    p = subprocess.run([PY] + [str(x) for x in a], cwd=root, capture_output=True, text=True, env=ENV, timeout=timeout)
    return p.returncode, p.stdout, p.stderr
def sha(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()

class Box:
    def __init__(s, sep=False):
        s.top = tempfile.mkdtemp(prefix="m39o-"); s.r = os.path.join(s.top, "d"); os.makedirs(s.r); r = s.r
        for f in ("intake.json", "order.json"): shutil.copy(os.path.join(FX, f), r)
        shutil.copytree(os.path.join(G13, "september" if sep else "clean"), os.path.join(r, "data"))
        os.makedirs(os.path.join(r, "db")); os.makedirs(os.path.join(r, "reports")); os.makedirs(os.path.join(r, "bin"))
        c = sqlite3.connect(os.path.join(r, "db", "app.db")); c.execute("create table t(a)"); c.execute("insert into t values (1)"); c.commit(); c.close()
        open(os.path.join(r, "bin", "make_note.py"), "w").write("import sys\nopen(sys.argv[1],'w').write('note v1\\n')\nsys.exit(int(sys.argv[2]) if len(sys.argv)>2 else 0)\n")
        s.claims({DE: ["reports/metrics.json"], DBA: ["snapshots/s1"]})
    def claims(s, m, order=True, name="claims.json"):
        c = {"schema": "solaris.delivery-claims/1", "contributions": [{"role": k, "outputs": v} for k, v in m.items()]}
        if order: c["order"] = "order.json"
        json.dump(c, open(os.path.join(s.r, name), "w")); return name
    def p(s, *x): return os.path.join(s.r, *x)
    def rec(s, role, outs, cmd, ok_exit=None, worker="ana", extra=()):
        a = [TOOL, "record", ".", "--role", role, "--worker", worker] + (["--ok-exit", ok_exit] if ok_exit else []) + list(extra) + ["--outputs"] + outs + ["--", PY] + cmd
        return run(s.r, *a)
    def recon(s, **k): return s.rec(DE, ["reports/metrics.json"], [CSV, "reconcile", "data/contract.json", "--out", "reports/metrics.json"], extra=INPUTS, **k)
    def snap(s, **k): return s.rec(DBA, ["snapshots/s1"], [SQ, "snapshot", "db", "--out", "snapshots/s1"], **k)
    def note(s, code=0, **k): return s.rec(SCR, ["reports/note.txt"], ["bin/make_note.py", "reports/note.txt", str(code)], **k)
    def order(s, worker="ana", *x): return run(s.r, HO, "run", "order.json", "--worker", worker, *x)
    def verify(s, claims="claims.json"):
        rc, o, e = run(s.r, TOOL, "verify", ".", "--claims", claims, "--json")
        try: j = json.loads(o)
        except ValueError: j = {}
        return rc, j, e
    def full(s):
        a = s.order(); b = s.recon(); c = s.snap(); return (a[0], b[0], c[0])
    def led(s): return open(s.p(".delivery", "contributions.jsonl"), "rb").read()
    def lines(s): return s.led().split(b"\n")[:-1]
    def put(s, ls, tail=b""): open(s.p(".delivery", "contributions.jsonl"), "wb").write(b"".join(l + b"\n" for l in ls) + tail)
    def head(s): return json.load(open(s.p(".delivery", "head.json")))
    def sethead(s, h): json.dump(h, open(s.p(".delivery", "head.json"), "w"))
    def close(s): shutil.rmtree(s.top, ignore_errors=True)
def states(j): return {c["role"]: c.get("state") for c in j.get("contributions", [])}
def V(t): rc, j, e = t; return (rc, j.get("verdict"), j.get("blockers"), "Traceback" in e)

@safe
def d01():
    b = Box(); rcs = b.full(); rc, j, e = b.verify(); res = {}
    res["steps_exit_0"] = (rcs == (0, 0, 0), rcs)
    res["clean_go_exit_0"] = (rc == 0 and j.get("verdict") == "GO" and j.get("blockers") == [], V((rc, j, e)))
    recs = [json.loads(l) for l in b.lines()]
    res["true_output_digest"] = (recs[0]["outputs"].get("reports/metrics.json") == sha(b.p("reports/metrics.json")), recs[0]["outputs"])
    res["real_exit_codes"] = ([r["exit"] for r in recs] == [0, 0], [r["exit"] for r in recs])
    res["chain_prev_is_sha_of_previous_line"] = (recs[0]["prev"] == "0" * 64 and recs[1]["prev"] == hashlib.sha256(b.lines()[0]).hexdigest(), recs[1]["prev"][:12])
    res["head_is_sha_of_last_line"] = (b.head() == {"seq": 1, "sha256": hashlib.sha256(b.lines()[-1]).hexdigest()}, b.head())
    res["tool_digest_of_csv_reconcile"] = (any(v == sha(CSV) for v in recs[0]["tools"].values()), list(recs[0]["tools"]))
    lg = recs[0].get("log"); res["log_digest_true"] = (bool(lg) and recs[0].get("log_sha256") == sha(b.p(lg)), lg)
    ob = open(b.p("outbox", "ledger.jsonl")).read().splitlines(); res["one_delivery"] = (len(ob) == 1, len(ob))
    b.close()
    row("D01 clean control: a full delivery (G04 order, G13 reconcile, G03 snapshot) is GO with true digests, real exits, a sound chain and head, and one delivery", all(v[0] for v in res.values()), res)

@safe
def d02():
    res = {}
    for step in ("activate", "brief"):
        b = Box(); a = b.order("ana", "--fail-at", step); b.recon(); b.snap(); r1 = b.verify()
        st1 = r1[1].get("handoff", {}).get("state")
        z = b.order("ben"); r2 = b.verify(); w = r2[1].get("handoff", {}).get("workers", {})
        res["g04_crash_after_%s_no_go_then_resume_go" % step] = (a[0] == 75 and r1[0] == 1 and st1 == "incomplete" and z[0] == 0 and r2[0] == 0 and "ben" in w.values(), (a[0], r1[0], st1, z[0], r2[0], w))
        b.close()
    # recorder killed while its command runs: no record, ledger still verifies, another worker records next
    b = Box(); b.full(); n0 = len(b.lines())
    open(b.p("bin", "slow.py"), "w").write("import time,sys\nopen(sys.argv[1],'w').write('x')\ntime.sleep(30)\n")
    pr = subprocess.Popen([PY, TOOL, "record", ".", "--role", SCR, "--outputs", "reports/slow.txt", "--", PY, "bin/slow.py", "reports/slow.txt"], cwd=b.r, env=ENV, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    for _ in range(100):
        if os.path.exists(b.p("reports", "slow.txt")): break
        time.sleep(0.05)
    os.killpg(pr.pid, signal.SIGKILL); pr.wait()
    n1 = len(b.lines()); rv = b.verify(); nt = b.note(worker="ben"); rv2 = b.verify(b.claims({DE: ["reports/metrics.json"], SCR: ["reports/note.txt"]}, name="c2.json"))
    res["killed_recorder_leaves_no_record_and_next_worker_records"] = (n1 == n0 and rv[0] == 0 and nt[0] == 0 and rv2[0] == 0, (n0, n1, rv[0], nt[0], rv2[0]))
    b.close()
    # crash between the line write and the head write: head lags by one; verify GO; next append repairs the head
    b = Box(); b.order(); b.recon(); h0 = b.head(); b.snap(); b.sethead(h0); r1 = b.verify(); nt = b.note(); h2 = b.head(); ls = b.lines()
    res["head_lag_one_tolerated_and_repaired"] = (r1[0] == 0 and nt[0] == 0 and h2 == {"seq": 2, "sha256": hashlib.sha256(ls[-1]).hexdigest()}, (r1[0], nt[0], h2.get("seq")))
    b.close()
    # crash mid-line: a cut-short tail is ignored, then dropped by the next append
    b = Box(); b.full(); ls = b.lines(); b.put(ls[:-1], ls[-1][: len(ls[-1]) // 2]); h = b.head()
    # authoring fix after the first run (disclosed): the G03 snapshot refuses an existing --out folder, so the re-run removes it first
    b.sethead({"seq": 0, "sha256": hashlib.sha256(ls[0]).hexdigest()}); r1 = b.verify(); st = states(r1[1]); shutil.rmtree(b.p("snapshots", "s1")); nt = b.snap(worker="ben"); ls2 = b.lines(); r2 = b.verify()
    res["torn_tail_ignored_then_dropped"] = (r1[0] == 1 and st.get(DBA) == "unevidenced" and r1[1].get("ledger", {}).get("torn_tail_ignored") is True and nt[0] == 0 and len(ls2) == 2 and r2[0] == 0 and json.loads(ls2[1]).get("dropped_torn_tail") is True, (r1[0], st, nt[0], len(ls2), r2[0]))
    b.close()
    # crash during the atomic head write leaves a temp file: harmless
    b = Box(); b.full(); open(b.p(".delivery", ".head.json.abc123"), "w").write('{"seq": 9'); r1 = b.verify(); nt = b.note()
    res["stray_head_temp_file_harmless"] = (r1[0] == 0 and nt[0] == 0, (r1[0], nt[0]))
    b.close()
    row("D02 crashes at other points: G04 crash after activate or brief, a recorder killed mid-command, a crash between line and head, a cut-short line and a stray head temp file all recover safely", all(v[0] for v in res.values()), res)

@safe
def d03():
    res = {}
    b = Box(); b.full(); ok_line = b.lines()[0]
    # stale record: a later failed run of the same role supersedes an earlier ok one
    open(b.p("data", "contract.json"), "a").write("garbage"); f = b.recon(); r = b.verify(); st = states(r[1])
    res["later_failed_run_supersedes_ok"] = (f[0] == 1 and r[0] == 1 and st.get(DE) == "failed", (f[0], r[0], st.get(DE)))
    b.close()
    # stale review: output changed, tool script changed (ROOT-local script), output dir member added or removed
    b = Box(); b.full(); b.note(); c2 = b.claims({DE: ["reports/metrics.json"], DBA: ["snapshots/s1"], SCR: ["reports/note.txt"]}, name="c2.json")
    g = b.verify(c2)[0]
    open(b.p("bin", "make_note.py"), "a").write("# changed\n"); r = b.verify(c2); st = states(r[1])
    res["root_tool_changed_stale"] = (g == 0 and r[0] == 1 and st.get(SCR) == "stale", (g, r[0], st.get(SCR)))
    b.close()
    b = Box(); b.full(); fs = sorted(os.listdir(b.p("snapshots", "s1")))
    open(b.p("snapshots", "s1", "extra.txt"), "w").write("x"); r = b.verify(); st1 = states(r[1]).get(DBA); os.remove(b.p("snapshots", "s1", "extra.txt"))
    os.remove(b.p("snapshots", "s1", fs[0])); r2 = b.verify(); st2 = states(r2[1]).get(DBA)
    res["output_dir_member_added_or_removed_blocks"] = (r[0] == 1 and r2[0] == 1 and st1 != "evidenced" and st2 != "evidenced", (st1, st2, fs))
    b.close()
    # forged record: a record copied from another delivery folder, and a replaced (re-hashed) first record
    b1 = Box(); b1.full(); b2 = Box(); b2.order(); b2.snap(); other = b1.lines()[0]
    b2.put([other] + b2.lines()); r = b2.verify(); rr = b2.note()
    res["record_from_other_folder_breaks_chain"] = (r[0] == 1 and r[1].get("ledger", {}).get("chain") == "broken" and rr[0] == 3, (r[0], r[1].get("ledger"), rr[0]))
    b1.close(); b2.close()
    row("D03 stale and forged records: a later failed run supersedes an ok one; a changed ROOT tool script or a changed output folder is not evidenced; a record copied in from another delivery breaks the chain and blocks record (exit 3)", all(v[0] for v in res.values()), res)

@safe
def d04():
    res = {}
    def broken(name, fn):
        b = Box(); b.full(); b.note(); fn(b); r = b.verify(); rr = b.snap(worker="ben")
        res[name] = (r[0] == 1 and r[1].get("verdict") == "NO_GO" and "ledger" in (r[1].get("blockers") or []) and set(states(r[1]).values()) == {"unevidenced"} and rr[0] == 3, (r[0], (r[1].get("ledger") or {}).get("chain"), rr[0]))
        b.close()
    def edit_first(b): ls = b.lines(); r = json.loads(ls[0]); r["exit"] = 0; r["worker"] = "zed"; ls[0] = json.dumps(r, sort_keys=True, separators=(",", ":")).encode(); b.put(ls)
    def ws_first(b): ls = b.lines(); ls[0] = json.dumps(json.loads(ls[0]), sort_keys=True).encode(); b.put(ls)
    def drop_first(b): b.put(b.lines()[1:])
    def edit_last(b): ls = b.lines(); r = json.loads(ls[-1]); r["exit"] = 7; ls[-1] = json.dumps(r, sort_keys=True, separators=(",", ":")).encode(); b.put(ls)
    def drop_last(b): b.put(b.lines()[:-1])
    def swap(b): ls = b.lines(); b.put([ls[1], ls[0], ls[2]])
    def dup_last(b): ls = b.lines(); b.put(ls + [ls[-1]])
    def head_gone(b): os.remove(b.p(".delivery", "head.json"))
    def head_garbage(b): open(b.p(".delivery", "head.json"), "w").write("{")
    def head_future(b): h = b.head(); h["seq"] += 1; b.sethead(h)
    def head_lag_two(b): ls = b.lines(); b.sethead({"seq": 0, "sha256": hashlib.sha256(ls[0]).hexdigest()})
    def tail_parses(b): ls = b.lines(); b.put(ls[:-1], ls[-1])
    for n, f in (("edit_first_record", edit_first), ("reserialise_first_record", ws_first), ("remove_first_record", drop_first),
                 ("edit_last_record", edit_last), ("remove_last_record", drop_last), ("reorder_records", swap), ("duplicate_last_record", dup_last),
                 ("head_removed", head_gone), ("head_unreadable", head_garbage), ("head_ahead", head_future), ("head_lags_two", head_lag_two),
                 ("complete_last_record_without_newline", tail_parses)):
        broken(n, f)
    row("D04 edits to the log head and tail: an edited, re-serialised, removed, reordered or duplicated record, first or last, and a removed, unreadable, ahead or two-behind head all make verify NO_GO with every contribution unevidenced and make record refuse (exit 3)", all(v[0] for v in res.values()), res)

@safe
def d05():
    res = {}
    b = Box(); a = b.order("ana", "--fail-at", "deliver"); b.recon(); b.snap(); z = b.order("ben"); z2 = b.order("cy"); r = b.verify()
    ob = open(b.p("outbox", "ledger.jsonl")).read().splitlines()
    res["crash_after_delivery_resume_twice_one_delivery_go"] = (a[0] == 75 and z[0] == 0 and z2[0] == 0 and len(ob) == 1 and r[0] == 0, (a[0], z[0], z2[0], len(ob), r[0]))
    open(b.p("outbox", "ledger.jsonl"), "a").write(ob[0] + "\n"); r = b.verify()
    res["duplicated_delivery_line_no_go"] = (r[0] == 1 and "handoff" in (r[1].get("blockers") or []), (r[0], r[1].get("handoff", {}).get("state")))
    b.close()
    b = Box(); b.full(); o = json.load(open(b.p("order.json"))); open(b.p("intake.json"), "a").write("\n")
    o["revision"] = 2; o["inputs"]["intake"]["sha256"] = sha(b.p("intake.json")); json.dump(o, open(b.p("order.json"), "w")); r = b.verify()
    res["new_revision_without_its_delivery_no_go"] = (r[0] == 1 and "handoff" in (r[1].get("blockers") or []), (r[0], r[1].get("handoff", {}).get("state")))
    z = b.order("ben"); r2 = b.verify(); ob = open(b.p("outbox", "ledger.jsonl")).read().splitlines()
    res["new_revision_delivered_once_go"] = (z[0] == 0 and r2[0] == 0 and len(ob) == 2, (z[0], r2[0], len(ob)))
    b.close()
    row("D05 duplicate-delivery suppression: resuming twice after a crash after delivery leaves one delivery and GO; a duplicated delivery line or a new revision without its delivery is NO_GO; the new revision delivered once is GO", all(v[0] for v in res.values()), res)

@safe
def d06():
    res = {}
    b = Box(sep=True); b.order(); f = b.recon(); r = b.verify(); st = states(r[1])
    res["dirty_month_exit_1_blocks_by_default"] = (f[0] == 1 and r[0] == 1 and st.get(DE) == "failed", (f[0], r[0], st.get(DE)))
    b.close()
    b = Box(); b.full(); f = b.rec(DE, ["reports/metrics.json"], [CSV, "reconcile", "data/missing.json", "--out", "reports/metrics.json"])
    r = b.verify(); res["invalid_input_exit_2_blocks_by_default"] = (f[0] == 1 and r[0] == 1, (f[0], r[0]))
    b.close()
    row("D06 exit codes by default: a dirty-month reconciliation (exit 1) and an invalid-input run (exit 2) block the delivery", all(v[0] for v in res.values()), res)

@safe
def d07():
    res = {}
    for name, fn in (("orders_csv_row_added", lambda b: open(b.p("data", "orders.csv"), "a").write("X999,C1,5000.00,USD,paid,2026-09-15T10:00:00-07:00,2026-09-15T11:00:00-07:00,2026-09-15T11:00:00-07:00\n")),
                     ("contract_timezone_changed", lambda b: open(b.p("data", "contract.json"), "w").write(open(b.p("data", "contract.json")).read().replace("America/Los_Angeles", "UTC")))):
        b = Box(); b.full(); g = b.verify()[0]; fn(b); r = b.verify(); st = states(r[1])
        res[name] = (g == 0 and r[0] == 1, (g, r[0], r[1].get("verdict"), st))
        b.close()
    row("D07 upstream input changed after review (M39 goal): a changed source CSV or a changed data contract makes the delivery NO_GO", all(v[0] for v in res.values()), res)

@safe
def d08():
    res = {}
    b = Box(); b.full(); c = b.claims({DE: ["reports/metrics.json"], "data/no-such-role": ["x"]}, name="c2.json"); r = b.verify(c)
    res["unknown_role_in_claims_exit_2"] = (r[0] == 2 and "Traceback" not in r[2], (r[0], r[2].strip()[-120:]))
    for n, extra in (("credential_in_command", ["ghp_" + "a" * 36]), ):
        k = b.rec(SCR, ["reports/note.txt"], ["bin/make_note.py", "reports/note.txt"] + extra); led = b.led()
        res[n + "_refused_never_written"] = (k[0] == 2 and b"ghp_" not in led and not any(b"ghp_" in open(os.path.join(b.p(".delivery", "logs"), x), "rb").read() for x in os.listdir(b.p(".delivery", "logs"))), k[0])
    for n, outs in (("output_in_ledger_dir", [".delivery/x"]), ("output_outside_root", ["../x"]), ("absolute_output", ["/tmp/x"])):
        k = b.rec(SCR, outs, ["bin/make_note.py", "reports/note.txt"]); res[n + "_refused"] = (k[0] == 2 and "Traceback" not in k[2], k[0])
    k = run(b.r, TOOL, "verify", ".", "--claims", "nope.json"); res["missing_claims_exit_2"] = (k[0] == 2 and "Traceback" not in k[2], k[0])
    b.close()
    row("D08 fresh-caller input errors: an unknown role, a credential-shaped argument, outputs inside .delivery, outside ROOT or absolute, and a missing claims file give exit 2 with no traceback and write nothing secret", all(v[0] for v in res.values()), res)

@safe
def d09():
    res = {}
    b = Box(); b.order(); b.recon()
    for i in range(8): open(b.p("bin", "w%d.py" % i), "w").write("import sys\nopen(sys.argv[1],'w').write('w%d\\n')\n" % i)
    ps = [subprocess.Popen([PY, TOOL, "record", ".", "--role", SCR, "--worker", "w%d" % i, "--outputs", "reports/w%d.txt" % i, "--", PY, "bin/w%d.py" % i, "reports/w%d.txt" % i],
                           cwd=b.r, env=ENV, stdout=subprocess.PIPE, stderr=subprocess.PIPE) for i in range(8)]
    rcs = [q.wait(120) for q in ps]
    for q in ps: q.stdout.close(); q.stderr.close()
    ls = b.lines(); recs = [json.loads(l) for l in ls]
    chain = all(recs[i]["seq"] == i and recs[i]["prev"] == (hashlib.sha256(ls[i - 1]).hexdigest() if i else "0" * 64) for i in range(len(recs)))
    r = b.verify(); ws = sorted(x["worker"] for x in recs if x["role"] == SCR)
    res["eight_concurrent_recorders_all_appended_chain_intact"] = (rcs == [0] * 8 and len(recs) == 9 and chain and r[1].get("ledger", {}).get("chain") == "intact" and ws == ["w%d" % i for i in range(8)], (rcs, len(recs), chain, ws))
    open(b.p("bin", "slow.py"), "w").write("import time\ntime.sleep(20)\n")
    t0 = time.time(); k = b.rec(SCR, ["reports/w0.txt"], ["bin/slow.py"], extra=("--timeout", "1")); dt_ = time.time() - t0; last = json.loads(b.lines()[-1])
    res["timeout_kills_and_records_not_ok"] = (k[0] == 1 and last.get("ok") is False and "timeout" in str(last.get("reason")) and dt_ < 15, (k[0], last.get("ok"), last.get("reason"), round(dt_, 1)))
    for n, t in (("timeout_zero", "0"), ("timeout_too_long", "999999")):
        k = b.rec(SCR, ["reports/w0.txt"], ["bin/w0.py", "reports/w0.txt"], extra=("--timeout", t)); res[n + "_refused"] = (k[0] == 2 and "Traceback" not in k[2], k[0])
    b.close()
    row("D09 concurrency and timeouts: eight concurrent recorders all append under the lock with an intact chain; a timed-out command is killed and recorded as not ok; out-of-range timeouts give exit 2", all(v[0] for v in res.values()), res)

@safe
def o09():
    det = {}
    b = Box(); b.full(); k = b.note(code=1, ok_exit="0,1"); r = b.verify(b.claims({DE: ["reports/metrics.json"], SCR: ["reports/note.txt"]}, name="c2.json"))
    det["ok_exit_0_1_with_exit_1_verdict"] = [k[0], r[1].get("verdict"), states(r[1]).get(SCR)]
    rc, o, e = run(b.r, TOOL, "verify", ".", "--claims", "c2.json"); det["text_output_mentions_exit_1"] = "exit 1" in o or "exit=1" in o
    k = b.rec(DE, ["reports/metrics.json"], [CSV, "reconcile", "data/missing.json", "--out", "reports/metrics.json"], ok_exit="0,1,2"); r = b.verify()
    det["ok_exit_0_1_2_invalid_input_verdict"] = [k[0], r[1].get("verdict")]
    b.close()
    b = Box(); b.full(); c = b.claims({DE: ["reports/metrics.json"]}, order=False, name="c3.json"); shutil.rmtree(b.p("outbox")); r = b.verify(c)
    det["claims_without_order_outbox_removed_verdict"] = r[1].get("verdict")
    b.close(); b = Box(); b.full(); open(b.p("intake.json"), "a").write("tampered\n"); r = b.verify(); det["intake_changed_after_delivery_verdict"] = r[1].get("verdict")
    b.close()
    # forged single appended record, no command run, head untouched (tolerated as a lag of one)
    b = Box(); b.full(); ls = b.lines(); x = json.loads(ls[-1])
    x.update(seq=len(ls), prev=hashlib.sha256(ls[-1]).hexdigest(), role=SCR, worker="mallory", argv=["true"], tools={}, log=".delivery/logs/none.log", log_sha256="0" * 64,
             outputs={"intake.json": sha(b.p("intake.json"))}, claimed_outputs=["intake.json"])
    b.put(ls + [json.dumps(x, sort_keys=True, separators=(",", ":")).encode()]); r = b.verify(b.claims({DE: ["reports/metrics.json"], SCR: ["intake.json"]}, name="c4.json"))
    det["forged_append_no_run_no_log_head_untouched_verdict"] = r[1].get("verdict")
    b.close()
    # remove a failed latest record and rewrite the head to match: the earlier ok record resurfaces
    b = Box(); b.full(); open(b.p("data", "contract.json"), "a").write("garbage"); b.recon(); ls = b.lines()[:-1]; b.put(ls)
    b.sethead({"seq": len(ls) - 1, "sha256": hashlib.sha256(ls[-1]).hexdigest()}); shutil.copy(os.path.join(G13, "clean", "contract.json"), b.p("data", "contract.json")); r = b.verify()
    det["failed_record_removed_head_rewritten_verdict"] = r[1].get("verdict")
    os.remove(b.p(".delivery", "contributions.jsonl")); k = b.note(); det["ledger_deleted_head_kept_then_record_exit"] = [k[0], b.head().get("seq")]
    b.close()
    b = Box(); b.full(); fs = sorted(os.listdir(b.p("snapshots", "s1"))); b2 = open(b.p("reports", "metrics.json"), "rb").read()
    open(b.p("reports", "metrics.json"), "wb").write(b2 + b" "); open(b.p("reports", "metrics.json"), "wb").write(b2); det["output_changed_then_restored_verdict"] = b.verify()[1].get("verdict")
    c = sqlite3.connect(b.p("db", "app.db")); c.execute("insert into t values (2)"); c.commit(); c.close(); det["db_changed_after_snapshot_verdict"] = b.verify()[1].get("verdict")
    b.close()
    row("O09 OBS: accepted non-zero exits, claims without an order, intake changed after delivery, a forged single append, a failed record removed with the head rewritten, a deleted ledger, an output restored byte for byte (recorded, not scored)", True, det)

for f in (d01, d02, d03, d04, d05, d06, d07, d08, d09, o09): f()
json.dump({"tool": TOOL, "python": sys.version.split()[0], "rows": ROWS}, open(OUT, "w"), indent=1, default=str)
core = [r for r in ROWS if r["row"].startswith("D") or "crash" in r["row"]]; n = sum(r["pass"] for r in core)
print("M39 ORACLE %d/%d core %s" % (n, len(core), "PASS" if n == len(core) else "FAIL"))
