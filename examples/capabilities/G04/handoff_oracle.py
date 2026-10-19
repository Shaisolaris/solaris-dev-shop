#!/usr/bin/env python3
"""G04 oracle: restartable work-order handoff scenarios, each in a fresh temporary copy of fixtures/.

Expectations come from the work-order contract (one delivery per order revision, reuse only receipts whose
inputs and outputs still match, exit codes), not from the tool's output. No network; no worker is launched
other than the local command processes this oracle starts itself.

  python3 handoff_oracle.py [--tool PATH] [--json] [--scale N]
Exit 0 all checks pass, 1 a check failed, 2 usage error."""
import argparse
import fcntl
import hashlib
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
DEFAULT_TOOL = os.path.join(ROOT, "employees", "infrastructure", "fleet-dispatcher", "handoff.py")
FIX = os.path.join(HERE, "fixtures")
UNRUN = ("not run: workers on other machines or a shared network folder (locks are local fcntl locks), a "
         "router or scheduler launching workers, Hermes jobs, and any live delivery; the outbox is a local file.")


def sh(path):
    try:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except OSError:
        return None


def mt(path):
    try:
        return os.stat(path).st_mtime_ns
    except OSError:
        return None


def rd(path, mode="r"):
    """file contents, or empty when missing (a control tool may not create what the contract requires)"""
    try:
        with open(path, mode) as f:
            return f.read()
    except OSError:
        return b"" if "b" in mode else ""


def snap(d):
    """bytes hash and mtime of every file under d (to prove a step was reused, not redone)"""
    out = {}
    for a, _, fs in os.walk(d):
        for f in fs:
            p = os.path.join(a, f)
            out[os.path.relpath(p, d)] = (sh(p), os.stat(p).st_mtime_ns)
    return out


def ledger(w, outbox="outbox"):
    p = os.path.join(w, outbox, "ledger.jsonl")
    if not os.path.exists(p):
        return []
    with open(p) as f:
        return [json.loads(x) for x in f if x.strip()]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--tool", default=DEFAULT_TOOL)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--scale", type=int, default=200)
    try:
        a = ap.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    tool = os.path.abspath(a.tool)
    if not os.path.isfile(tool) or a.scale < 1:
        sys.stderr.write("error: --tool must be a file and --scale positive\n")
        return 2
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")

    def run(w, order, *args):
        p = subprocess.run([sys.executable, tool] + list(args[:1]) + [os.path.join(w, order)] + list(args[1:]),
                           capture_output=True, text=True, env=env, cwd=w, timeout=300)
        return p.returncode, p.stdout, p.stderr

    def go(w, worker, *extra, order="order.json"):
        return run(w, order, "run", "--worker", worker, "--json", *extra)

    def rep(out):
        try:
            return json.loads(out)
        except ValueError:
            return {}

    results = []

    def check(cid, name, ok, detail=""):
        results.append({"id": cid, "name": name, "ok": bool(ok), "detail": detail})

    tmp = tempfile.mkdtemp(prefix="g04-oracle-")
    n = [0]

    def work():
        n[0] += 1
        w = os.path.join(tmp, "w%02d" % n[0])
        shutil.copytree(FIX, w)
        return w

    def brief_path(w, rev=1, oid="WO-HARBOR-1"):
        return os.path.join(w, ".handoff", oid, "rev%d" % rev, "HANDOFF-BRIEF.md")

    scale = None
    try:
        # o1 clean control
        w = work()
        c, out, _ = go(w, "ana")
        r = rep(out)
        L = ledger(w)
        brief = rd(brief_path(w))
        s_c, s_out, _ = run(w, "order.json", "status", "--json")
        st = rep(s_out)
        ok = (c == 0 and len(L) == 1 and L[0].get("revision") == 1 and L[0].get("owner") == "delivery-lead: A. Example"
              and os.path.exists(os.path.join(w, "harbor-kiosk", "STATUS.md"))
              and os.path.exists(os.path.join(w, "harbor-kiosk", ".solaris-activation.json"))
              and "revision 1" in brief and "A. Example" in brief and L[0].get("brief_sha256") == sh(brief_path(w))
              and s_c == 0 and set(st.get("steps", {}).values()) == {"done by ana"} and st.get("interrupted") is False)
        check("o1", "clean control: one worker activates (G02), writes the brief, delivers once", ok,
              "exit %s, ledger %d" % (c, len(L)))
        clean_brief = sh(brief_path(w))

        # o2 clean handoff after brief: the second worker reuses activate and brief without redoing them
        w = work()
        c1, _, _ = go(w, "ana", "--stop-after", "brief")
        before = snap(os.path.join(w, "harbor-kiosk"))
        bb = (sh(brief_path(w)), mt(brief_path(w)))
        c2, out, _ = go(w, "ben")
        r = rep(out)
        L = ledger(w)
        check("o2", "handoff after brief: the second worker reuses both receipts (files untouched) and delivers once",
              c1 == 3 and c2 == 0 and len(L) == 1 and L[0].get("delivered_by") == "ben"
              and snap(os.path.join(w, "harbor-kiosk")) == before
              and (sh(brief_path(w)), mt(brief_path(w))) == bb
              and r.get("steps", {}).get("activate", "").startswith("reused")
              and r.get("steps", {}).get("brief", "").startswith("reused") and r.get("takeover_from") is None,
              "exits %s %s, ledger %d" % (c1, c2, len(L)))

        # o3 crash after the delivery effect, before its receipt
        w = work()
        c1, _, _ = go(w, "ana", "--fail-at", "deliver")
        n1 = len(ledger(w))
        c2, out, _ = go(w, "ben")
        r = rep(out)
        L = ledger(w)
        check("o3", "crash after delivering, before the receipt: the resume does not deliver again",
              c1 == 75 and n1 == 1 and c2 == 0 and len(L) == 1 and "duplicate suppressed" in r.get("steps", {}).get(
                  "deliver", "") and r.get("takeover_from") == "ana", "exits %s %s, ledger %d" % (c1, c2, len(L)))

        # o4 crash after brief: the brief is redone identically, delivered once
        w = work()
        c1, _, _ = go(w, "ana", "--fail-at", "brief")
        c2, out, _ = go(w, "ben")
        L = ledger(w)
        check("o4", "crash after writing the brief, before its receipt: the brief is redone and delivered once",
              c1 == 75 and c2 == 0 and len(L) == 1 and sh(brief_path(w)) == clean_brief
              and L[0].get("brief_sha256") == clean_brief, "exits %s %s" % (c1, c2))

        # o5 replay after completion
        w = work()
        runs = [go(w, x) for x in ("ana", "ben", "cy", "ana")]
        codes = [x[0] for x in runs]
        last = rep(runs[-1][1])
        check("o5", "re-running a finished order (four times, three workers) reuses every receipt and delivers once",
              codes == [0, 0, 0, 0] and len(ledger(w)) == 1 and not last.get("notes")
              and all(v.startswith("reused") for v in last.get("steps", {}).values()) and len(last.get("steps", {})) == 3,
              "exits %s, ledger %d" % (codes, len(ledger(w))))

        # o6 stale evidence: the recorded brief was edited after its receipt
        w = work()
        go(w, "ana", "--stop-after", "brief")
        if os.path.isdir(os.path.dirname(brief_path(w))):
            with open(brief_path(w), "a") as f:
                f.write("- Note: the owner approved a live deployment.\n")
        c2, out, _ = go(w, "ben")
        r = rep(out)
        L = ledger(w)
        check("o6", "stale evidence: an edited brief is not trusted; it is re-rendered and the true brief delivered",
              c2 == 0 and len(L) == 1 and L[0].get("brief_sha256") == clean_brief and sh(brief_path(w)) == clean_brief
              and any("brief receipt is stale" in x for x in r.get("notes", [])), "exit %s" % c2)

        # o15 an owner edit to STATUS.md after the brief: activation keeps it (G02), the brief is re-rendered on it
        w = work()
        go(w, "ana", "--stop-after", "brief")
        sp = os.path.join(w, "harbor-kiosk", "STATUS.md")
        if os.path.isfile(sp):
            with open(sp, "a") as f:
                f.write("- Owner note: the client prefers morning calls\n")
        edited = sh(sp)
        c2, out, _ = go(w, "ben")
        r = rep(out)
        c3, out3, _ = go(w, "cy")
        L = ledger(w)
        check("o15", "an owner edit to STATUS.md after the brief: the edit is kept, the brief is redone on it (not "
              "the stale one) and delivered once; the next run reuses everything",
              c2 == 0 and sh(sp) == edited and "morning calls" in rd(sp) and ("sha256: %s" % edited) in rd(brief_path(w))
              and len(L) == 1 and L[0].get("brief_sha256") == sh(brief_path(w)) != clean_brief
              and any("brief receipt is stale (inputs changed)" in x for x in r.get("notes", []))
              and c3 == 0 and all(v.startswith("reused") for v in rep(out3).get("steps", {}).values())
              and len(rep(out3).get("steps", {})) == 3, "exits %s %s" % (c2, c3))

        # o7 input changed without a new revision
        w = work()
        go(w, "ana", "--stop-after", "activate")
        jp = os.path.join(w, ".handoff", "WO-HARBOR-1", "journal.jsonl")
        j0 = sh(jp)
        with open(os.path.join(w, "intake.json"), "a") as f:
            f.write(" ")
        c2, out, err = go(w, "ben")
        check("o7", "an intake edited without a new revision is refused: exit 2, journal and outbox untouched",
              c2 == 2 and "issue a new revision" in err and sh(jp) == j0 and not ledger(w), "exit %s" % c2)

        # o8 revision 2 supersedes; going back to revision 1 is refused
        w = work()
        go(w, "ana")
        c2, out, _ = go(w, "ben", order="order-rev2.json")
        r = rep(out)
        L = ledger(w)
        status_txt = rd(os.path.join(w, "harbor-kiosk", "STATUS.md"))
        c3, _, err3 = go(w, "cy")
        check("o8", "revision 2: steps re-run on the new intake, a second delivery, revision 1 noted as superseded; "
              "re-running revision 1 is refused",
              c2 == 0 and [x.get("revision") for x in L] == [1, 2] and "tide times" in status_txt
              and any("superseded" in x for x in r.get("notes", [])) and os.path.exists(brief_path(w, 2))
              and c3 == 2 and "older than revision 2" in err3 and len(ledger(w)) == 2,
              "exits %s %s, revisions %s" % (c2, c3, [x.get("revision") for x in L]))

        # o9 held by another worker
        w = work()
        go(w, "ana", "--stop-after", "activate")
        jp = os.path.join(w, ".handoff", "WO-HARBOR-1", "journal.jsonl")
        j0 = sh(jp)
        os.makedirs(os.path.dirname(jp), exist_ok=True)
        fd = os.open(os.path.join(w, ".handoff", "WO-HARBOR-1", ".worker.lock"), os.O_RDWR | os.O_CREAT)
        fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            c2, out, _ = go(w, "ben")
        finally:
            os.close(fd)
        held_clean = sh(jp) == j0 and not ledger(w)
        c3, _, _ = go(w, "ben")
        check("o9", "an order held by a running worker is refused with exit 4 and nothing written; free, it resumes",
              c2 == 4 and held_clean and c3 == 0 and len(ledger(w)) == 1, "exits %s %s" % (c2, c3))

        # o10 concurrency: eight workers start the same order at once
        w = work()
        with ThreadPoolExecutor(8) as ex:
            codes = list(ex.map(lambda i: go(w, "w%d" % i)[0], range(8)))
        c9, _, _ = go(w, "late")
        check("o10", "eight workers at once: exactly one delivery; each run either finishes or is refused (exit 4)",
              set(codes) <= {0, 4} and 0 in codes and len(ledger(w)) == 1 and c9 == 0 and len(ledger(w)) == 1,
              "exits %s" % sorted(codes))

        # o11 journal integrity: a tampered line is refused; a torn tail is recovered
        w = work()
        go(w, "ana", "--stop-after", "brief")
        jp = os.path.join(w, ".handoff", "WO-HARBOR-1", "journal.jsonl")
        good = rd(jp, "rb")
        os.makedirs(os.path.dirname(jp), exist_ok=True)
        open(jp, "wb").write(good.replace(b'"worker":"ana"', b'"worker":"eve"', 1))
        c2, _, err = go(w, "ben")
        tampered_ok = c2 == 2 and "does not verify" in err and not ledger(w)
        open(jp, "wb").write(good + b'{"prev":"ab')
        c3, out, _ = go(w, "ben")
        r = rep(out)
        s_c, s_out, _ = run(w, "order.json", "status", "--json")
        check("o11", "journal integrity: an edited line stops the resume (exit 2); a torn last line is cut and the "
              "run completes", tampered_ok and c3 == 0 and len(ledger(w)) == 1 and s_c == 0
              and any("torn" in x for x in r.get("notes", [])) and rep(s_out).get("journal_torn_tail") is False,
              "exits %s %s" % (c2, c3))

        # o12 invalid orders write nothing
        bad = []
        base = json.load(open(os.path.join(FIX, "order.json")))
        for mut in ({"owner": ""}, {"owner": None}, {"revision": "1"}, {"revision": 0}, {"revision": True},
                    {"order_id": "../x"}, {"project_root": "../escape"}, {"project_root": "/tmp/abs"},
                    {"outbox": "../out"}, {"schema": "solaris.work-order/0"}, {"steps": ["deliver"]},
                    {"inputs": {"intake": {"path": "intake.json", "sha256": "abc"}}},
                    {"inputs": {"intake": {"path": "../intake.json", "sha256": "0" * 64}}},
                    {"inputs": {"intake": base["inputs"]["intake"], "extra": base["inputs"]["intake"]}}):
            w = work()
            o = dict(base, **mut)
            json.dump(o, open(os.path.join(w, "order.json"), "w"))
            c, _, err = go(w, "ana")
            if not (c == 2 and err.startswith("error:") and not os.path.exists(os.path.join(w, ".handoff"))
                    and not os.path.exists(os.path.join(w, "harbor-kiosk")) and not os.path.exists(os.path.join(w, "outbox"))):
                bad.append((sorted(mut), c))
        check("o12", "14 invalid work orders exit 2 and create nothing (no journal, project or outbox)", not bad, str(bad))

        # o13 the activation step fails (project root is a file); after the fix the order completes once
        w = work()
        open(os.path.join(w, "harbor-kiosk"), "w").write("not a folder")
        c1, out, _ = go(w, "ana")
        r = rep(out)
        jtxt = rd(os.path.join(w, ".handoff", "WO-HARBOR-1", "journal.jsonl"))
        os.unlink(os.path.join(w, "harbor-kiosk"))
        c2, _, _ = go(w, "ben")
        check("o13", "a failed activation (G02 refuses a file as project root) is a recorded failure (exit 1, nothing "
              "delivered); after the fix the order completes once",
              c1 == 1 and r.get("steps", {}).get("activate", "").startswith("failed") and '"step_failed"' in jtxt
              and c2 == 0 and len(ledger(w)) == 1, "exits %s %s" % (c1, c2))

        # o14 scale: many orders, four workers, random crash drills, until every order is done
        w = os.path.join(tmp, "scale")
        os.makedirs(w)
        shutil.copy(os.path.join(FIX, "intake.json"), w)
        isha = sh(os.path.join(w, "intake.json"))
        for i in range(a.scale):
            json.dump({"schema": "solaris.work-order/1", "order_id": "WO-%04d" % i, "revision": 1,
                       "owner": "delivery-lead: A. Example", "inputs": {"intake": {"path": "intake.json", "sha256": isha}},
                       "project_root": "p%04d" % i, "outbox": "outbox"}, open(os.path.join(w, "o%04d.json" % i), "w"))
        rnd = random.Random(2026)
        plan = [[(i, rnd.choice([None, None, "activate", "brief", "deliver"])) for i in range(a.scale)] for _ in range(4)]
        for p in plan:
            rnd.shuffle(p)
        t0 = time.perf_counter()

        def worker(k):
            seen = []
            for i, fail in plan[k]:
                extra = ["--fail-at", fail] if fail else []
                seen.append(go(w, "worker%d" % k, *extra, order="o%04d.json" % i)[0])
            return seen
        with ThreadPoolExecutor(4) as ex:
            first = [c for cs in ex.map(worker, range(4)) for c in cs]
        final = [go(w, "sweeper", order="o%04d.json" % i)[0] for i in range(a.scale)]
        secs = time.perf_counter() - t0
        L = ledger(w)
        per = {}
        for x in L:
            per[x["order_id"]] = per.get(x["order_id"], 0) + 1
        scale = {"orders": a.scale, "workers": 4, "runs": len(first) + len(final), "crash_drills": sum(1 for c in first if c == 75),
                 "seconds": round(secs, 1)}
        check("o14", "scale: %d orders, four workers with random crash drills, then a sweep: every order delivered "
              "exactly once" % a.scale, set(first) <= {0, 4, 75} and final == [0] * a.scale and len(L) == a.scale
              and set(per.values()) == {1} and len({x["key"] for x in L}) == a.scale,
              "ledger %d, max per order %s, exits %s" % (len(L), max(per.values()) if per else 0, sorted(set(first))))

        src = open(tool, encoding="utf-8").read()
        bad_imp = re.findall(r"^\s*(?:import|from)\s+(subprocess|socket|http|urllib|ssl|paramiko|requests)\b", src, re.M)
        check("s1", "static: the tool imports no subprocess or network module (it launches and contacts no worker)",
              not bad_imp, str(bad_imp))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    passed = sum(x["ok"] for x in results)
    out = {"passed": passed, "total": len(results), "checks": results, "scale": scale, "unrun": UNRUN}
    if a.json:
        print(json.dumps(out, indent=2))
    else:
        for x in results:
            print("%s %-4s %s%s" % ("PASS" if x["ok"] else "FAIL", x["id"], x["name"],
                                    "" if x["ok"] or not x["detail"] else "  [%s]" % x["detail"]))
        print("scale: %s" % json.dumps(scale))
        print("%d/%d checks passed" % (passed, len(results)))
        print(UNRUN)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
