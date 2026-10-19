#!/usr/bin/env python3
"""G39 oracle: checks a delivery-evidence tool by its effects, with expectations derived here.

    python3 examples/capabilities/G39/drill_oracle.py [--tool PATH] [--only o1,o5]

Each check builds a fresh temporary delivery folder, drives the tool with real commands and the G04
work-order runner, then reads the ledger and the files itself (its own sha256 and its own chain check).
A tool that echoes success, trusts its own records or skips the work order fails. Prints one line per
check and a final "ACCEPTED n/n" or "REJECTED k/n".
"""
import argparse, hashlib, json, os, secrets, shutil, signal, subprocess, sys, tempfile, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
PY = sys.executable
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
HANDOFF = REPO / "employees/infrastructure/fleet-dispatcher/handoff.py"
CSV = REPO / "employees/data/data-engineer/csv_reconcile.py"
TOOL = REPO / "employees/product-project/delivery-lead/delivery_evidence.py"
R1, R2 = "data/data-engineer", "quality-security/security-auditor"


def sha(b):
    return hashlib.sha256(b).hexdigest()


def run(root, *args, timeout=300):
    p = subprocess.run([PY, str(TOOL)] + [str(a) for a in args], cwd=str(root), capture_output=True, text=True,
                       env=ENV, timeout=timeout)
    return p.returncode, p.stdout, p.stderr


def handoff(root, *args):
    return subprocess.run([PY, str(HANDOFF)] + list(args), cwd=str(root), capture_output=True, text=True,
                          env=ENV, timeout=120).returncode


def writer(path, content, rc=0):
    """A real specialist-style command: writes CONTENT to PATH, then exits RC."""
    return [PY, "-c", "import sys,pathlib;p=pathlib.Path(sys.argv[1]);p.parent.mkdir(parents=True,exist_ok=True);"
                      "p.write_text(sys.argv[2]);sys.exit(int(sys.argv[3]))", path, content, str(rc)]


def record(root, role, outputs, cmd, ok="0", worker="w"):
    return run(root, "record", ".", "--role", role, "--worker", worker, "--ok-exit", ok, "--outputs", *outputs,
               "--", *cmd)


def verify(root, claims="claims.json"):
    rc, out, err = run(root, "verify", ".", "--claims", claims, "--json")
    try:
        return rc, json.loads(out)
    except ValueError:
        return rc, {}


def ledger(root):
    """Own reading: list of records, and whether the prev chain holds."""
    p = root / ".delivery/contributions.jsonl"
    if not p.exists():
        return [], True
    lines = p.read_bytes().split(b"\n")
    lines.pop()
    recs, prev, ok = [], "0" * 64, True
    for line in lines:
        try:
            r = json.loads(line)
        except ValueError:
            return recs, False
        ok = ok and r.get("prev") == prev
        prev = sha(line)
        recs.append(r)
    return recs, ok


MADE = []  # folders this process created; only these are removed


def fresh(claims_roles, order=True):
    parent = Path(tempfile.mkdtemp(prefix="g39o-"))  # private parent, so ../ escapes stay ours
    MADE.append(parent)
    root = parent / "delivery"
    root.mkdir()
    fx = HERE / "fixtures"
    shutil.copy2(fx / "intake.json", root / "intake.json")
    shutil.copy2(fx / "order.json", root / "order.json")
    c = {"schema": "solaris.delivery-claims/1",
         "contributions": [{"role": r, "outputs": o} for r, o in claims_roles]}
    if order:
        c["order"] = "order.json"
    (root / "claims.json").write_text(json.dumps(c))
    return root


def state(rep, role):
    for c in rep.get("contributions", []):
        if c.get("role") == role:
            return c.get("state")
    return None


def complete_order(root):
    return handoff(root, "run", "order.json", "--worker", "ana", "--fail-at", "deliver"), \
        handoff(root, "run", "order.json", "--worker", "ben")


# ---- checks: each returns (ok, note)

def o1_clean():
    """Two specialists recorded, order crashed by ana and resumed by ben: GO with true digests."""
    root = fresh([(R1, ["r/a.json"]), (R2, ["r/b.json"])])
    na, nb = secrets.token_hex(8), secrets.token_hex(8)
    a = record(root, R1, ["r/a.json"], writer("r/a.json", na))[0]
    b = record(root, R2, ["r/b.json"], writer("r/b.json", nb), worker="ben")[0]
    h = complete_order(root)
    rc, rep = verify(root)
    recs, chain = ledger(root)
    want = {"r/a.json": sha(na.encode()), "r/b.json": sha(nb.encode())}
    got = {k: v for r in recs for k, v in (r.get("outputs") or {}).items()}
    outbox = (root / "outbox/ledger.jsonl").read_text().splitlines()
    ok = (a, b, h) == (0, 0, (75, 0)) and rc == 0 and rep.get("verdict") == "GO" and chain and got == want \
        and len(recs) == 2 and len(outbox) == 1 and (rep.get("handoff") or {}).get("workers", {}).get("deliver") == "ben"
    return ok, "rc %s verdict %s chain %s digests %s" % (rc, rep.get("verdict"), chain, got == want)


def o2_exit_truth():
    """The record carries the command's real exit; an exit outside --ok-exit is recorded as not ok."""
    root = fresh([(R1, ["r/a.json"])])
    rc = record(root, R1, ["r/a.json"], writer("r/a.json", "x", rc=3))[0]
    recs, chain = ledger(root)
    complete_order(root)
    vrc, rep = verify(root)
    ok = rc == 1 and len(recs) == 1 and recs[0].get("exit") == 3 and recs[0].get("ok") is False and \
        vrc == 1 and state(rep, R1) == "failed"
    return ok, "record rc %s exit %s verify %s %s" % (rc, recs[0].get("exit") if recs else None, vrc, state(rep, R1))


def o3_unevidenced():
    """A claimed specialist with no record blocks the delivery."""
    root = fresh([(R1, ["r/a.json"]), (R2, ["r/b.json"])])
    record(root, R1, ["r/a.json"], writer("r/a.json", "x"))
    (root / "r/b.json").write_text("made by hand, never run through a tool")
    complete_order(root)
    rc, rep = verify(root)
    ok = rc == 1 and state(rep, R2) == "unevidenced" and state(rep, R1) == "evidenced"
    return ok, "rc %s %s" % (rc, state(rep, R2))


def o4_real_data_gaps():
    """G13 on the dirty September drop exits 1; with --ok-exit 0 that blocks, with 0,1 it is accepted."""
    root = fresh([(R1, ["reports/m.json"])])
    shutil.copytree(REPO / "examples/capabilities/G13/fixtures/september", root / "data")
    cmd = [PY, str(CSV), "reconcile", "data/contract.json", "--out", "reports/m.json"]
    (root / "reports").mkdir()
    a = record(root, R1, ["reports/m.json"], cmd)[0]
    complete_order(root)
    v1, rep1 = verify(root)
    b = record(root, R1, ["reports/m.json"], cmd, ok="0,1")[0]
    v2, rep2 = verify(root)
    m = json.loads((root / "reports/m.json").read_text())
    ok = a == 1 and v1 == 1 and state(rep1, R1) == "failed" and b == 0 and v2 == 0 and \
        m.get("status") == "reconciled_with_gaps"
    return ok, "strict %s/%s %s, gaps-accepted %s/%s, status %s" % (a, v1, state(rep1, R1), b, v2, m.get("status"))


def o5_stale_output():
    """An output edited after its record is stale, names the file and the command; a re-run restores GO."""
    root = fresh([(R1, ["r/a.json"])])
    record(root, R1, ["r/a.json"], writer("r/a.json", "v1"))
    complete_order(root)
    v0 = verify(root)[0]
    (root / "r/a.json").write_text("v1 edited")
    v1, rep = verify(root)
    c = [x for x in rep.get("contributions", []) if x.get("role") == R1]
    named = bool(c) and c[0].get("changed") == ["r/a.json"] and "re-run" in (c[0].get("action") or "")
    record(root, R1, ["r/a.json"], writer("r/a.json", "v2"), worker="cy")
    v2, rep2 = verify(root)
    ok = v0 == 0 and v1 == 1 and state(rep, R1) == "stale" and named and v2 == 0
    return ok, "before %s after-edit %s %s named %s rerun %s" % (v0, v1, state(rep, R1), named, v2)


def o6_stale_tool():
    """Changing the specialist's script after the run makes the contribution stale."""
    root = fresh([(R1, ["r/a.json"])])
    (root / "tools").mkdir()
    (root / "tools/spec.py").write_text("import pathlib\npathlib.Path('r').mkdir(exist_ok=True)\n"
                                        "pathlib.Path('r/a.json').write_text('{}')\n")
    record(root, R1, ["r/a.json"], [PY, "tools/spec.py"])
    complete_order(root)
    v0 = verify(root)[0]
    with open(root / "tools/spec.py", "a") as f:
        f.write("# changed after review\n")
    v1, rep = verify(root)
    ok = v0 == 0 and v1 == 1 and state(rep, R1) == "stale"
    return ok, "before %s after-tool-change %s %s" % (v0, v1, state(rep, R1))


def o7_tamper():
    """An edited or removed record breaks the chain: verify NO_GO and record refuses to append."""
    root = fresh([(R1, ["r/a.json"])])
    record(root, R1, ["r/a.json"], writer("r/a.json", "x", rc=1))
    record(root, R2, ["r/b.json"], writer("r/b.json", "y"))
    complete_order(root)
    p = root / ".delivery/contributions.jsonl"
    lines = p.read_bytes().split(b"\n")
    r0 = json.loads(lines[0]); r0["exit"], r0["ok"], r0["reason"] = 0, True, None
    lines[0] = json.dumps(r0, sort_keys=True, separators=(",", ":")).encode()
    p.write_bytes(b"\n".join(lines))
    before = p.read_bytes()
    v1, rep = verify(root)
    a = record(root, R1, ["r/a.json"], writer("r/a.json", "z"))[0]
    after = p.read_bytes()
    q = fresh([(R2, ["r/b.json"])])
    record(q, R1, ["r/a.json"], writer("r/a.json", "x"))
    record(q, R2, ["r/b.json"], writer("r/b.json", "y"))
    complete_order(q)
    pq = q / ".delivery/contributions.jsonl"
    ql = pq.read_bytes().split(b"\n")
    pq.write_bytes(b"\n".join(ql[1:]))
    v2, rep2 = verify(q)
    ok = v1 == 1 and state(rep, R1) != "evidenced" and a == 3 and before == after and v2 == 1
    return ok, "edited %s/%s record %s unchanged %s; removed %s" % (v1, state(rep, R1), a, before == after, v2)


def o8_torn_tail():
    """A cut-short final append is ignored and the next record still chains."""
    root = fresh([(R1, ["r/a.json"]), (R2, ["r/b.json"])])
    record(root, R1, ["r/a.json"], writer("r/a.json", "x"))
    with open(root / ".delivery/contributions.jsonl", "ab") as f:
        f.write(b'{"seq":1,"prev":"ab')
    complete_order(root)
    v1, rep1 = verify(root)
    a = record(root, R2, ["r/b.json"], writer("r/b.json", "y"))[0]
    v2, rep2 = verify(root)
    recs, chain = ledger(root)
    ok = v1 == 1 and state(rep1, R1) == "evidenced" and a == 0 and v2 == 0 and chain and len(recs) == 2
    return ok, "with tail %s, append %s, after %s chain %s n=%d" % (v1, a, v2, chain, len(recs))


def o9_killed_recorder():
    """A recorder killed while its command runs leaves no record; another worker re-runs to GO."""
    root = fresh([(R1, ["r/a.json"])])
    cmd = [PY, str(TOOL), "record", ".", "--role", R1, "--worker", "ana", "--outputs", "r/a.json", "--", PY, "-c",
           "import time,pathlib;pathlib.Path('r').mkdir(exist_ok=True);pathlib.Path('r/a.json').write_text('half');"
           "time.sleep(30)"]
    p = subprocess.Popen(cmd, cwd=str(root), env=ENV, start_new_session=True, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    for _ in range(200):
        if (root / "r/a.json").exists():
            break
        time.sleep(0.05)
    os.killpg(p.pid, signal.SIGKILL)
    p.wait()
    recs0, _ = ledger(root)
    complete_order(root)
    v1, rep = verify(root)
    a = record(root, R1, ["r/a.json"], writer("r/a.json", "full"), worker="ben")[0]
    v2, rep2 = verify(root)
    c = [x for x in rep2.get("contributions", []) if x.get("role") == R1]
    ok = len(recs0) == 0 and v1 == 1 and state(rep, R1) == "unevidenced" and a == 0 and v2 == 0 and \
        bool(c) and c[0].get("worker") == "ben"
    return ok, "records after kill %d, verify %s, resume %s/%s" % (len(recs0), v1, a, v2)


def o10_concurrent():
    """Eight recorders at once: eight records, seq 0..7, chain intact, nothing lost."""
    root = fresh([(R1, ["r/a0.json"])])
    with ThreadPoolExecutor(8) as ex:
        rcs = list(ex.map(lambda i: record(root, R1, ["r/a%d.json" % i], writer("r/a%d.json" % i, str(i)))[0],
                          range(8)))
    recs, chain = ledger(root)
    seqs = sorted(r.get("seq") for r in recs)
    files = sorted(k for r in recs for k in (r.get("outputs") or {}))
    ok = rcs == [0] * 8 and chain and seqs == list(range(8)) and files == sorted("r/a%d.json" % i for i in range(8))
    return ok, "rcs %s chain %s seqs %s" % (set(rcs), chain, seqs)


def o11_invalid():
    """Bad input is refused with exit 2 and leaves nothing behind; a credential is never written."""
    root = fresh([(R1, ["r/a.json"])])
    tok = "ghp_" + "A" * 36
    rcs = [record(root, "not/a-role", ["r/a.json"], writer("r/a.json", "x"))[0],
           record(root, "../etc", ["r/a.json"], writer("r/a.json", "x"))[0],
           record(root, R1, ["../out.json"], writer("../out.json", "x"))[0],
           record(root, R1, [".delivery/x"], writer(".delivery/x", "x"))[0],
           record(root, R1, ["r/a.json"], writer("r/a.json", tok))[0]]
    left = not (root / "r").exists() and not (root.parent / "out.json").exists() and \
        not (root / ".delivery/contributions.jsonl").exists()
    leak = any(tok in p.read_text(errors="ignore") for p in root.rglob("*") if p.is_file())
    (root / "dup.json").write_text(json.dumps({"schema": "solaris.delivery-claims/1", "contributions": [
        {"role": R1, "outputs": ["a"]}, {"role": R1, "outputs": ["b"]}]}))
    d = run(root, "verify", ".", "--claims", "dup.json")[0]
    ok = rcs == [2] * 5 and left and not leak and d == 2
    return ok, "rcs %s clean %s leak %s dup %s" % (rcs, left, leak, d)


def o12_handoff_incomplete():
    """Every specialist evidenced but the work order stopped before delivery, or crashed after it without a
    resume: NO_GO naming the handoff."""
    root = fresh([(R1, ["r/a.json"])])
    record(root, R1, ["r/a.json"], writer("r/a.json", "x"))
    s = handoff(root, "run", "order.json", "--worker", "ana", "--stop-after", "brief")
    v1, rep1 = verify(root)
    c = handoff(root, "run", "order.json", "--worker", "ben", "--fail-at", "deliver")
    v2, rep2 = verify(root)
    ok = s == 3 and v1 == 1 and "handoff" in rep1.get("blockers", []) and c == 75 and v2 == 1 and \
        "handoff" in rep2.get("blockers", [])
    return ok, "stopped %s -> %s; crashed after delivery %s -> %s" % (s, v1, c, v2)


def o13_symlink_output():
    """An output that is a symlink is not evidence."""
    root = fresh([(R1, ["r/a.json"])])
    outside = Path(tempfile.mkdtemp(prefix="g39o-out-"))
    MADE.append(outside)
    (outside / "real.json").write_text("{}")
    (root / "r").mkdir()
    os.symlink(str(outside / "real.json"), str(root / "r/a.json"))
    a = record(root, R1, ["r/a.json"], [PY, "-c", "pass"])[0]
    complete_order(root)
    v, rep = verify(root)
    shutil.rmtree(outside)
    ok = a == 1 and v == 1 and state(rep, R1) in ("failed", "stale")
    return ok, "record %s verify %s %s" % (a, v, state(rep, R1))


def o14_drill():
    """The full synthetic delivery with real G02/G03/G04/G05/G13/G19 tools passes end to end."""
    p = subprocess.run([PY, str(HERE / "drill.py"), "--tool", str(TOOL)], capture_output=True, text=True, env=ENV,
                       timeout=600)
    return p.returncode == 0 and "DRILL PASSED" in p.stdout, p.stdout.strip().splitlines()[-1] if p.stdout else p.stderr[-200:]


def cleanup():
    while MADE:
        shutil.rmtree(MADE.pop(), ignore_errors=True)


CHECKS = [o1_clean, o2_exit_truth, o3_unevidenced, o4_real_data_gaps, o5_stale_output, o6_stale_tool, o7_tamper,
          o8_torn_tail, o9_killed_recorder, o10_concurrent, o11_invalid, o12_handoff_incomplete,
          o13_symlink_output, o14_drill]


def main():
    global TOOL
    ap = argparse.ArgumentParser()
    ap.add_argument("--tool", default=str(TOOL))
    ap.add_argument("--only")
    ns = ap.parse_args()
    TOOL = Path(ns.tool).resolve()
    only = set(ns.only.split(",")) if ns.only else None
    passed = total = 0
    for c in CHECKS:
        key = c.__name__.split("_")[0]
        if only and key not in only:
            continue
        total += 1
        try:
            ok, note = c()
        except Exception as e:  # a crash in the candidate's effects is a failed check, not an oracle pass
            ok, note = False, "error %s: %s" % (type(e).__name__, str(e)[:160])
        passed += bool(ok)
        print("%s %-26s %s" % ("PASS" if ok else "FAIL", c.__name__, note))
    cleanup()
    print("%s %d/%d" % ("ACCEPTED" if passed == total else "REJECTED", passed, total))
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
