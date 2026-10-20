#!/usr/bin/env python3
"""G05 oracle: assurance evidence that survives (or is invalidated by) changed source.

Expectations come from fixtures/revisions.json (which files change between r1 and r2 and which folders each
gate reviewed), checked against the real fixture files, never from the engine's output. The engine is loaded
from --tool and called in-process; the digest and run commands are called as processes. Nothing named in a
receipt is opened or executed; no network.

  python3 binding_oracle.py [--tool PATH] [--json] [--scale N]
Exit 0 all checks pass, 1 a check failed, 2 usage error."""
import argparse
import builtins
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
DEFAULT_TOOL = os.path.join(ROOT, "employees", "quality-security", "assurance", "quality_os.py")
FIX = os.path.join(HERE, "fixtures")
UNRUN = ("not run: whether a reviewer really examined the named revision (receipts are declarations), git "
         "itself (revisions are compared as declared ids), and any release or external action.")


def files_under(folder, scopes):
    out = {}
    for scope in scopes:
        for dirpath, dirs, names in os.walk(os.path.join(folder, scope)):
            dirs.sort()
            for n in sorted(names):
                p = os.path.join(dirpath, n)
                out[os.path.relpath(p, folder).replace(os.sep, "/")] = hashlib.sha256(open(p, "rb").read()).hexdigest()
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--tool", default=DEFAULT_TOOL)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--scale", type=int, default=5000)
    try:
        a = ap.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    tool = os.path.abspath(a.tool)
    if not os.path.isfile(tool) or a.scale < 100:
        sys.stderr.write("error: --tool must be a file and --scale at least 100\n")
        return 2
    spec = importlib.util.spec_from_file_location("g05_engine_under_test", tool)
    q = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = q
    spec.loader.exec_module(q)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    decl = json.load(open(os.path.join(FIX, "revisions.json")))
    R1, R2 = decl["r1"]["revision"], decl["r2"]["revision"]
    P1, P2 = os.path.join(FIX, decl["r1"]["folder"]), os.path.join(FIX, decl["r2"]["folder"])
    scopes = decl["gate_scopes"]
    changed = sorted(decl["changed_r1_to_r2"])
    all1, all2 = files_under(P1, ["."]), files_under(P2, ["."])
    all1 = {k[2:] if k.startswith("./") else k: v for k, v in all1.items()}
    all2 = {k[2:] if k.startswith("./") else k: v for k, v in all2.items()}
    results = []

    def check(cid, name, fn):
        try:
            ok, detail = fn()
        except Exception as e:  # a missing API or a crash is a failed check, not an oracle crash
            ok, detail = False, "%s: %s" % (e.__class__.__name__, str(e)[:160])
        results.append({"id": cid, "name": name, "ok": bool(ok), "detail": detail})

    def fixture_sane():
        actual = sorted(k for k in all1 if all1[k] != all2.get(k))
        return actual == changed and set(all1) == set(all2), "declared %s, actual %s" % (changed, actual)

    def receipt(gate, reviewed=None, role=None):
        r = {"gate": gate, "role": role or {"security": "security-auditor", "functional": "qa-engineer",
                                            "ux": "ux-reviewer"}.get(gate, "qa-engineer"),
             "summary": "%s review" % gate, "artifacts": ["reports/%s.md" % gate], "blocking_open": 0}
        if reviewed is not None:
            r["reviewed"] = reviewed
        return r

    def packet(subject, reviewed_by_gate, gates=("functional", "security", "ux")):
        p = {"risk_level": "standard", "dimensions": ["security"], "completed_gates": list(gates),
             "evidence": {g: receipt(g, reviewed_by_gate.get(g)) for g in gates}}
        if subject is not None:
            p["subject"] = subject
        return p

    def scoped(folder, gate):
        return files_under(folder, scopes[gate])

    def gates_state(res):
        return {g: d.get("state") for g, d in res.evidence.get("revision_binding", {}).get("gates", {}).items()}

    expect_stale = sorted(g for g in scopes if any(c.split("/")[0] in scopes[g] for c in changed))
    expect_carry = sorted(g for g in scopes if g not in expect_stale)

    check("o0", "fixture sanity: the declared r1-to-r2 change is exactly what differs on disk", fixture_sane)

    def o1():
        res = q.evaluate_artifact_packet(packet({"revision": R1, "digests": all1},
                                                {g: {"revision": R1, "digests": scoped(P1, g)} for g in scopes}))
        return res.ok and res.gate_codes == [] and set(gates_state(res).values()) == {"current"}, \
            "%s %s %s" % (res.status, res.gate_codes, gates_state(res))
    check("o1", "clean control: receipts reviewed at r1 against subject r1 pass, every gate current", o1)

    def o2():
        res = q.evaluate_artifact_packet(packet({"revision": R2, "digests": all2},
                                                {g: {"revision": R1, "digests": scoped(P1, g)} for g in scopes}))
        st = gates_state(res)
        diag = res.evidence["revision_binding"]["gates"]
        ok = (not res.ok and res.gate_codes == ["STALE_GATE_EVIDENCE"]
              and sorted(g for g, s in st.items() if s == "stale") == expect_stale
              and sorted(g for g, s in st.items() if s == "carried_forward") == expect_carry
              and all(diag[g].get("changed") == [c for c in changed if c.split("/")[0] in scopes[g]] for g in expect_stale)
              and all(R2 in diag[g].get("action", "") and g in diag[g].get("action", "") for g in expect_stale)
              and sum("is stale" in m for m in res.messages) == len(expect_stale))
        return ok, "%s %s %s" % (res.status, res.gate_codes, st)
    check("o2", "changed content: receipts whose reviewed files changed are stale (naming the files and the "
          "re-run); the gate whose files did not change carries forward", o2)

    def o3():
        r = []
        res = q.evaluate_artifact_packet(packet({"revision": R2}, {g: {"revision": R2} for g in scopes}))
        r.append(res.ok)
        res = q.evaluate_artifact_packet(packet({"revision": R2}, {g: {"revision": R2[:12]} for g in scopes}))
        r.append(res.ok)
        res = q.evaluate_artifact_packet(packet({"revision": R2, "digests": all2},
                                                {"ux": {"revision": R1, "digests": scoped(P1, "ux")}}, gates=("ux",)))
        r.append(res.ok and gates_state(res) == {"ux": "carried_forward"})
        return all(r), str(r)
    check("o3", "a valid reviewed revision stays acceptable: exact id, abbreviated id, and an earlier revision "
          "whose reviewed files are unchanged", o3)

    def o4():
        res = q.evaluate_artifact_packet(packet({"revision": R2, "digests": all2},
                                                {g: ({"revision": R2, "digests": scoped(P2, g)} if g in expect_stale
                                                     else {"revision": R1, "digests": scoped(P1, g)}) for g in scopes}))
        return res.ok, "%s %s" % (res.status, res.gate_codes)
    check("o4", "recovery: re-running only the stale gates on r2 makes the packet pass", o4)

    def o5():
        r = []
        res = q.evaluate_artifact_packet(packet({"revision": R2}, {"functional": {"revision": R2}}))
        r.append(not res.ok and "UNBOUND_GATE_EVIDENCE" in res.gate_codes
                 and gates_state(res) == {"functional": "current", "security": "unbound", "ux": "unbound"})
        res = q.evaluate_artifact_packet(packet({"digests": all2}, {g: {"revision": R2} for g in scopes}))
        r.append(not res.ok and res.gate_codes == ["UNBOUND_GATE_EVIDENCE"])
        res = q.evaluate_artifact_packet(packet({"digests": {"src/auth.py": all2["src/auth.py"]}},
                                                {g: {"digests": scoped(P2, g)} for g in scopes}))
        r.append(not res.ok and res.gate_codes == ["UNBOUND_GATE_EVIDENCE"]
                 and all(d.get("not_in_subject") for d in res.evidence["revision_binding"]["gates"].values()))
        return all(r), str(r)
    check("o5", "unbound: once a subject is named, a receipt with no reviewed binding, or nothing comparable, "
          "is refused with an action", o5)

    def o6():
        res = q.evaluate_artifact_packet(packet(None, {"security": {"revision": R1}, "functional": {"revision": R2}},
                                                gates=("functional", "security")))
        a = not res.ok and res.gate_codes == ["REVISION_CONFLICT"]
        res = q.evaluate_artifact_packet(packet(None, {"security": {"revision": R2[:9]}, "functional": {"revision": R2}},
                                                gates=("functional", "security")))
        return a and res.ok, "conflict %s, same %s" % (a, res.ok)
    check("o6", "no subject: receipts naming different revisions conflict; the same revision (short and full) passes", o6)

    def o7():
        legacy = packet(None, {})
        res = q.evaluate_artifact_packet(legacy)
        a = res.ok and res.gate_codes == [] and "revision_binding" not in res.evidence
        bad = packet(None, {})
        bad["evidence"]["security"]["blocking_open"] = 2
        res2 = q.evaluate_artifact_packet(bad)
        miss = packet(None, {}, gates=("functional",))
        miss["risk_level"] = "elevated"
        res3 = q.evaluate_artifact_packet(miss)
        return (a and res2.gate_codes == ["OPEN_BLOCKING_FINDINGS"] and "MISSING_SPECIALIST_GATE" in res3.gate_codes,
                "%s %s %s" % (res.gate_codes, res2.gate_codes, res3.gate_codes))
    check("o7", "packets without any revision binding behave as before (pass, blocking count, missing gate)", o7)

    def o8():
        subjects = [12345, "", "HEAD", "4F1C2A9E", "abc", "sha256:" + "0" * 63, {}, {"rev": R1},
                    {"revision": R1, "extra": 1}, {"digests": {}}, {"digests": {"../x": "0" * 64}},
                    {"digests": {"/abs": "0" * 64}}, {"digests": {"a": "nothex"}}, {"digests": ["a"]},
                    {"digests": {"a\\b": "0" * 64}}, {"digests": {("p%d" % i): "0" * 64 for i in range(10001)}}]
        fails = []
        t0 = time.perf_counter()
        for s in subjects:
            sub = s if isinstance(s, dict) else {"revision": s}
            res = q.evaluate_artifact_packet(packet(sub, {}))
            if res.ok or res.gate_codes != ["INVALID_PACKET"] or len(" ".join(res.messages)) > 400:
                fails.append(("subject", str(s)[:30], res.gate_codes))
            res = q.evaluate_artifact_packet(packet({"revision": R2}, {"security": sub}))
            if res.ok or "INVALID_GATE_EVIDENCE" not in res.gate_codes or len(" ".join(res.messages)) > 600:
                fails.append(("reviewed", str(s)[:30], res.gate_codes))
        secs = time.perf_counter() - t0
        return not fails and secs < 5, "%d failures, %.2fs: %s" % (len(fails), secs, fails[:3])
    check("o8", "16 malformed subject and reviewed bindings fail boundedly (INVALID_PACKET / "
          "INVALID_GATE_EVIDENCE, short messages, no crash)", o8)

    def finding():
        return q.create_finding(defect_kind="security", severity="S1", title="Password compare is not constant time",
                                evidence=["review of src/auth.py at %s" % R1], reporter_role="qa-engineer",
                                finding_id="fnd-g05-1")

    def o9():
        f = finding()
        c = q.can_close_finding
        r = [c(f, closer_role="code-reviewer", independent_evidence=["re-review"], subject_revision=R2,
               verified_revision=R1) == (False, ["STALE_CLOSURE_EVIDENCE"]),
             c(f, closer_role="code-reviewer", independent_evidence=["re-review"], subject_revision=R2)
             == (False, ["MISSING_VERIFIED_REVISION"]),
             c(f, closer_role="code-reviewer", independent_evidence=["re-review"], subject_revision="HEAD",
               verified_revision=R2) == (False, ["INVALID_REVISION"]),
             c(f, closer_role="code-reviewer", independent_evidence=["re-review"]) == (True, [])]
        closed, codes = q.close_finding(f, closer_role="code-reviewer", independent_evidence=["verified at r2"],
                                        subject_revision=R2, verified_revision=R2)
        r.append(codes == [] and closed.status == "closed" and closed.closed_at_revision == R2)
        r.append(c(f, closer_role="security-auditor", independent_evidence=["x"], subject_revision=R2,
                   verified_revision=R2) == (False, ["SELF_APPROVAL_FORBIDDEN"]))
        return all(r), str(r)
    check("o9", "closure binding: a closure verified at another revision is stale, an unnamed one is refused, "
          "a matching one records its revision; unbound closure and self-approval rules unchanged", o9)

    def o10():
        f = finding()
        closed, _ = q.close_finding(f, closer_role="code-reviewer", independent_evidence=["verified fix at r1"],
                                    subject_revision=R1, verified_revision=R1)
        r = [q.closure_is_current(closed, R1) == (True, []), q.closure_is_current(closed, R2) == (False, ["STALE_CLOSURE"])]
        old = q.Finding(**dict(closed.to_dict(), closed_at_revision=""))
        r.append(q.closure_is_current(old, R2) == (False, ["UNBOUND_CLOSURE"]))
        reo, codes = q.reopen_finding(closed, reason="auth.py changed at r2; fix must be re-verified",
                                      current_revision=R2, reopened_by_role="code-reviewer")
        r.append(codes == [] and reo.status == "open" and reo.closed_by_role == "" and reo.closed_at_revision == ""
                 and any(R2 in e and "reopened" in e for e in reo.evidence))
        r.append(q.can_close_finding(reo, closer_role="code-reviewer", independent_evidence=["verified fix at r1"],
                                     subject_revision=R2, verified_revision=R2) == (False, ["NON_INDEPENDENT_CLOSURE_EVIDENCE"]))
        again, codes = q.close_finding(reo, closer_role="code-reviewer", independent_evidence=["verified fix at r2"],
                                       subject_revision=R2, verified_revision=R2)
        r.append(codes == [] and q.closure_is_current(again, R2) == (True, []))
        r.append(q.reopen_finding(f, reason="not closed yet, cannot reopen", current_revision=R2,
                                  reopened_by_role="qa")[1] == ["NOT_CLOSED"])
        r.append(q.reopen_finding(closed, reason="short", current_revision=R2, reopened_by_role="qa")[1]
                 == ["REOPEN_REASON_REQUIRED"])
        return all(r), str(r)
    check("o10", "reopened finding: a closure from r1 is stale at r2, reopens with a note, cannot be re-closed on "
          "the old evidence, and closes at r2 on new evidence", o10)

    def o11():
        f = finding()
        f.status = "waived"
        later = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        w = q.Waiver("wvr-g05", f.finding_id, "security-auditor", "human-owner", True,
                     "accepted until the kiosk launch review", later, "active")
        expired = q.Waiver("wvr-g05x", f.finding_id, "security-auditor", "human-owner", True,
                           "accepted until the kiosk launch review", "2000-01-01T00:00:00Z", "active")
        c = q.can_close_finding
        r = [c(f, closer_role="delivery-lead", independent_evidence=[], waiver=w, subject_revision=R2,
               verified_revision=R1) == (True, []),
             c(f, closer_role="delivery-lead", independent_evidence=[], waiver=w, subject_revision=R2) == (True, []),
             c(f, closer_role="delivery-lead", independent_evidence=[], waiver=expired, subject_revision=R2,
               verified_revision=R2) == (False, ["WAIVER_EXPIRED"]),
             c(f, closer_role="delivery-lead", independent_evidence=[], subject_revision=R2) == (False, ["WAIVER_REQUIRED"]),
             q.reopen_finding(f, reason="waived findings are not reopened", current_revision=R2,
                              reopened_by_role="qa")[1] == ["NOT_CLOSED"]]
        return all(r), str(r)
    check("o11", "waiver semantics preserved: a valid waiver closes regardless of revision; expired or missing "
          "waivers still refuse; a waived finding is not reopened", o11)

    tmp = tempfile.mkdtemp(prefix="g05-oracle-")
    try:
        def cli(*args):
            p = subprocess.run([sys.executable, tool] + list(args), capture_output=True, text=True, env=env, timeout=120)
            return p.returncode, p.stdout, p.stderr

        def o12():
            c, out, _ = cli("digest", P2, "src", "ui", "--revision", R2)
            d = json.loads(out) if c == 0 else {}
            want = files_under(P2, ["src", "ui"])
            r = [c == 0 and d.get("digests") == want and d.get("revision") == R2 and list(d["digests"]) == sorted(want)]
            res = q.evaluate_artifact_packet(packet({"revision": R2, "digests": all2},
                                                    {"functional": d}, gates=("functional",)))
            r.append(res.ok)
            w = os.path.join(tmp, "proj")
            shutil.copytree(P2, w)
            os.symlink(os.path.join(P1, "src"), os.path.join(w, "outside"))
            r.append(cli("digest", w, "outside")[0] == 2)
            r.append(cli("digest", w, "../proj/src")[0] == 2)
            r.append(cli("digest", w, "missing.txt")[0] == 2)
            r.append(cli("digest", w, "src", "--revision", "HEAD")[0] == 2)
            os.makedirs(os.path.join(w, "empty"))
            r.append(cli("digest", w, "empty")[0] == 2)
            return all(r), str(r)
        check("o12", "digest command: actual file hashes in sorted order usable as a binding; symlinks, escapes, "
              "missing files, bad revisions and empty folders exit 2", o12)

        def o13():
            fx = {"fixture_kind": "closure", "finding": dict(finding().to_dict()), "closer_role": "code-reviewer",
                  "independent_evidence": ["verified fix"], "subject_revision": R2, "verified_revision": R1,
                  # expect_blocked False with outcome fail_gate: the form the G01 fixture-runner contract accepts
                  # (gate_codes are only checked with outcome fail_gate); the closure must still be blocked with
                  # STALE_CLOSURE_EVIDENCE, or the fixture fails.
                  "expect_blocked": False, "expectations": {"outcome": "fail_gate",
                                                            "gate_codes": ["STALE_CLOSURE_EVIDENCE"]}}
            del fx["finding"]["created_at"]
            p1 = os.path.join(tmp, "stale-closure.json")
            json.dump(fx, open(p1, "w"))
            c1, out1, _ = cli("run", p1)
            fx2 = dict(fx, verified_revision=R2, expect_blocked=False, expectations={})
            p2 = os.path.join(tmp, "current-closure.json")
            json.dump(fx2, open(p2, "w"))
            c2, _, _ = cli("run", p2)
            fx3 = dict(fx, verified_revision=7)
            p3 = os.path.join(tmp, "bad-closure.json")
            json.dump(fx3, open(p3, "w"))
            c3, out3, _ = cli("run", p3)
            return (c1 == 0 and "STALE_CLOSURE_EVIDENCE" in out1 and c2 == 0 and c3 == 1 and "INVALID_PACKET" in out3,
                    "exits %s %s %s" % (c1, c2, c3))
        check("o13", "run command: closure fixtures carry subject and verified revisions; a mistyped one is "
              "INVALID_PACKET", o13)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    scale = {}

    def o14():
        n = a.scale
        base = {"pkg%03d/f%05d.txt" % (i % 250, i): hashlib.sha256(b"r1-%d" % i).hexdigest() for i in range(n)}
        gates = sorted(q.ACCOUNTABLE_GATES)
        keys = list(base)
        width = n // len(gates)
        per = {g: {k: base[k] for k in keys[i * width:i * width + min(400, width - 1)]} for i, g in enumerate(gates)}
        # 36 changes inside the first three gates' reviewed files, one in a file no gate reviewed
        chg = sorted([k for g in gates[:3] for k in list(per[g])[::max(1, len(per[g]) // 12)][:12]]
                     + [keys[width - 1]])
        new = dict(base, **{k: hashlib.sha256(b"r2-" + k.encode()).hexdigest() for k in chg})
        want = sorted(g for g in gates if set(per[g]) & set(chg))
        p = {"risk_level": "standard", "dimensions": [], "completed_gates": gates,
             "subject": {"revision": R2, "digests": new},
             "evidence": {g: receipt(g, {"revision": R1, "digests": per[g]}) for g in gates}}
        t0 = time.perf_counter()
        res = q.evaluate_artifact_packet(p)
        secs = time.perf_counter() - t0
        st = gates_state(res)
        got = sorted(g for g, s in st.items() if s == "stale")
        scale.update({"subject_files": n, "gates": len(gates), "changed": len(chg), "stale_expected": len(want),
                      "seconds": round(secs, 3)})
        return (got == want and all(s == "carried_forward" for g, s in st.items() if g not in want) and secs < 5,
                "stale %s want %s in %.3fs" % (got, want, secs))
    check("o14", "scale: %d-file subject, 11 gates of up to 400 reviewed files, 37 changed (one unreviewed): "
          "exactly the 3 gates whose reviewed files changed are stale, the rest carry forward" % a.scale, o14)

    def s1():
        real_open = builtins.open
        opened = []

        def guard(*args, **kw):
            opened.append(str(args[0]) if args else "?")
            raise AssertionError("packet evaluation opened a file")
        pk = packet({"revision": R2, "digests": all2}, {g: {"revision": R1, "digests": scoped(P1, g)} for g in scopes})
        builtins.open = guard
        try:
            res = q.evaluate_artifact_packet(pk)
        finally:
            builtins.open = real_open
        return not opened and res is not None, "opened %s" % opened[:2]
    check("s1", "packet evaluation opens no file (digest paths and artifacts are declared text)", s1)

    passed = sum(x["ok"] for x in results)
    out = {"passed": passed, "total": len(results), "checks": results, "scale": scale, "unrun": UNRUN}
    if a.json:
        print(json.dumps(out, indent=2))
    else:
        for x in results:
            print("%s %-4s %s%s" % ("PASS" if x["ok"] else "FAIL", x["id"], x["name"],
                                    "" if x["ok"] else "  [%s]" % x["detail"]))
        print("scale: %s" % json.dumps(scale))
        print("%d/%d checks passed" % (passed, len(results)))
        print(UNRUN)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
