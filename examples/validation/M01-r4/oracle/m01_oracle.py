#!/usr/bin/env python3
"""M01 fresh black-box oracle for the G01 fixture runner (Grok self-validation).

Drives `quality_os.py run` and `quality_os.py suite` through the CLI only, on
fixtures generated in temporary directories. Written from ASSURANCE.md's fixture
contract, not from the builder's tests.

  python3 m01_oracle.py ENGINE [--python INTERP] [--json OUT] [--only core|gap]

core checks (c*): the contract G01 claims. Expected to hold on the candidate.
gap checks  (x*): adversarial cases. "HOLDS" means the contract-consistent
                  outcome; "GAP" means a false pass or a crash was observed.
Exit status: 0 if every core check holds, else 1. Gap checks never change it.
"""
import argparse, json, os, subprocess, sys, tempfile
from pathlib import Path

RECEIPT = {"gate": "security", "role": "security-auditor", "summary": "STRIDE review",
           "artifacts": ["reports/threat-model.md"], "blocking_open": 0}
MISS = {"risk_level": "elevated", "dimensions": ["security"], "completed_gates": [], "evidence": {}}
DONE = {"risk_level": "elevated", "dimensions": ["security"], "completed_gates": ["security"],
        "evidence": {"security": RECEIPT}}
NOGATE = dict(MISS, risk_level="informational")
FINDING = {"finding_id": "f-9", "defect_kind": "security", "severity": "S1", "title": "IDOR",
           "evidence": ["probe: other tenant record returned"], "accountable_role": "security-auditor",
           "reporter_role": "qa-engineer", "status": "open", "verifier_role": "code-reviewer"}
BAD_LEGAL = "I am your attorney; file this lawsuit now."
INV = ["INVALID_PACKET"]


class Engine:
    def __init__(self, engine, python):
        self.engine, self.python = engine, python

    def cli(self, args, cwd=None):
        env = {"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1", "HOME": cwd or "/tmp"}
        p = subprocess.run([self.python, self.engine, *args], capture_output=True, text=True,
                           cwd=cwd, env=env)
        out = {"rc": p.returncode, "traceback": "Traceback" in p.stderr}
        try:
            out["json"] = json.loads(p.stdout)
        except ValueError:
            out["json"] = None
            out["stderr_tail"] = p.stderr.strip().splitlines()[-1:] if p.stderr.strip() else []
        return out

    def run(self, data=None, raw=None):
        with tempfile.TemporaryDirectory() as t:
            f = Path(t, "fx.json")
            if raw is not None:
                f.write_bytes(raw if isinstance(raw, bytes) else raw.encode())
            else:
                f.write_text(json.dumps(data), encoding="utf-8")
            return self.cli(["run", str(f)], cwd=t)

    def suite(self, files, setup=None, args=None):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t, "fx")
            root.mkdir()
            for name, data in files.items():
                p = root / name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(data if isinstance(data, bytes) else json.dumps(data).encode())
            if setup:
                setup(Path(t), root)
            return self.cli(args if args is not None else ["suite", str(root)], cwd=t)


def summary(o):
    j = o["json"] or {}
    s = {"rc": o["rc"], "traceback": o["traceback"]}
    for k in ("ok", "gate_codes", "total", "passed", "error"):
        if k in j:
            s[k] = j[k]
    if o["json"] is None:
        s["no_json"] = True
        s["stderr_tail"] = o.get("stderr_tail")
    return s


def is_invalid(o):
    j = o["json"]
    return o["rc"] == 1 and not o["traceback"] and j is not None and j.get("ok") is False \
        and j.get("gate_codes") == INV


def is_pass(o):
    return o["rc"] == 0 and o["json"] is not None and o["json"].get("ok") is True


def is_clean_fail(o):
    j = o["json"]
    return o["rc"] == 1 and not o["traceback"] and j is not None and j.get("ok") is False


CHECKS = []


def check(cid, group, desc):
    def deco(fn):
        CHECKS.append((cid, group, desc, fn))
        return fn
    return deco


# ------------------------------------------------------------------ core
@check("c01", "core", "unknown fixture_kind values are INVALID_PACKET")
def c01(e):
    obs = [e.run({"fixture_kind": v, "finding": FINDING}) for v in
           ("Closure", " closure", "closure ", None, 3, {"k": 1}, "packets")]
    return all(map(is_invalid, obs)), [summary(o) for o in obs]

@check("c02", "core", "unknown legacy kind values are INVALID_PACKET")
def c02(e):
    obs = [e.run({"kind": v, "defect": {"defect_kind": "security"}}) for v in ("Defect", "planted", "")]
    return all(map(is_invalid, obs)), [summary(o) for o in obs]

@check("c03", "core", "fixture_kind takes precedence over kind; invalid fixture_kind is not rescued by a valid kind")
def c03(e):
    a = e.run({"fixture_kind": "closre", "kind": "closure", "finding": FINDING})
    b = e.run({"fixture_kind": "closure", "kind": "nonsense", "finding": FINDING,
               "closer_role": "security-auditor"})
    return is_invalid(a) and is_pass(b), [summary(a), summary(b)]

@check("c04", "core", "non-object expectations are INVALID_PACKET")
def c04(e):
    obs = [e.run({"packet": DONE, "expectations": v}) for v in ([], "pass", None, 1)]
    return all(map(is_invalid, obs)), [summary(o) for o in obs]

@check("c05", "core", "unknown expectation keys are INVALID_PACKET (wrapped and unwrapped)")
def c05(e):
    obs = [e.run({"packet": DONE, "expectations": {"outcome": "pass", k: 1}}) for k in
           ("Outcome", "decision", "gate_code", "accountableRole", "")]
    obs.append(e.run(dict(DONE, expectations={"outcome": "pass", "status": "pass"})))
    return all(map(is_invalid, obs)), [summary(o) for o in obs]

@check("c06", "core", "outcome outside {pass, fail_gate} is INVALID_PACKET")
def c06(e):
    obs = [e.run({"packet": NOGATE, "expectations": {"outcome": v}}) for v in
           ("FAIL_GATE", "Pass", "", None, True, "pass ")]
    return all(map(is_invalid, obs)), [summary(o) for o in obs]

@check("c07", "core", "gate_codes not an array of strings is INVALID_PACKET")
def c07(e):
    obs = [e.run({"packet": MISS, "expectations": {"outcome": "fail_gate", "gate_codes": v}}) for v in
           ("MISSING_SPECIALIST_GATE", [1], [None], {"a": 1}, ["MISSING_SPECIALIST_GATE", 2])]
    return all(map(is_invalid, obs)), [summary(o) for o in obs]

@check("c08", "core", "accountable_role not a nonblank string is INVALID_PACKET")
def c08(e):
    obs = [e.run({"packet": DONE, "expectations": {"accountable_role": v}}) for v in
           ("", "\t\n", 0, [], None)]
    return all(map(is_invalid, obs)), [summary(o) for o in obs]

@check("c09", "core", "unreadable or non-object fixture files are INVALID_PACKET without traceback")
def c09(e):
    obs = [e.run(raw=r) for r in ("", "{", "{'a': 1}", b"\xff\xfe\x00", "[]", "\"x\"", "7", "NaN")]
    return all(map(is_invalid, obs)), [summary(o) for o in obs]

@check("c10", "core", "valid fixtures keep their outcome")
def c10(e):
    good = [
        DONE, {"packet": DONE}, {"fixture_kind": "packet", "packet": DONE},
        {"packet": MISS, "expectations": {"outcome": "fail_gate", "gate_codes": ["MISSING_SPECIALIST_GATE"]}},
        {"fixture_kind": "planted_defect", "defect": {"defect_kind": "security", "severity": "S1"},
         "expectations": {"accountable_role": "security-auditor"}},
        {"fixture_kind": "closure", "finding": FINDING, "closer_role": "security-auditor"},
        {"fixture_kind": "self_approval", "finding": FINDING},
        {"fixture_kind": "legal_boundary", "text": BAD_LEGAL,
         "expectations": {"outcome": "fail_gate"}},
    ]
    bad = [
        {"packet": MISS, "expectations": {"outcome": "pass"}},
        {"packet": NOGATE, "expectations": {"outcome": "fail_gate"}},
        {"packet": MISS, "expectations": {"outcome": "fail_gate", "gate_codes": ["SOME_OTHER_GATE"]}},
        {"fixture_kind": "planted_defect", "defect": {"defect_kind": "security"},
         "expectations": {"accountable_role": "code-reviewer"}},
        {"fixture_kind": "legal", "text": BAD_LEGAL, "expectations": {"outcome": "pass"}},
        MISS,
    ]
    og = [e.run(d) for d in good]
    ob = [e.run(d) for d in bad]
    return all(map(is_pass, og)) and all(map(is_clean_fail, ob)), \
        {"should_pass": [summary(o) for o in og], "should_fail": [summary(o) for o in ob]}

@check("c11", "core", "suite: missing dir, empty dir, only _-files, only non-.json files all fail with error")
def c11(e):
    obs = [
        e.suite({}, args=["suite", "/nonexistent-m01-dir"]),
        e.suite({}),
        e.suite({"_a.json": DONE, "sub/_b.json": DONE}),
        e.suite({"a.txt": DONE, "b.json.bak": DONE}),
        e.suite({}, args=["suite"]),
    ]
    ok = all(o["rc"] == 1 and o["json"] and o["json"].get("ok") is False and o["json"].get("total") == 0
             and o["json"].get("error") for o in obs)
    return ok, [summary(o) for o in obs]

@check("c12", "core", "suite: one bad fixture among good fails the suite with correct counts; nested dirs are counted")
def c12(e):
    a = e.suite({"p.json": DONE, "deep/n.json": {"packet": MISS, "expectations": {"outcome": "fail_gate"}},
                 "deep/er/c.json": {"fixture_kind": "closure", "finding": FINDING}})
    b = e.suite({"p.json": DONE, "q.json": {"fixture_kind": "closre", "finding": FINDING},
                 "r.json": {"packet": MISS, "expectations": {"outcome": "pass"}}})
    ja, jb = a["json"] or {}, b["json"] or {}
    ok = (a["rc"], ja.get("ok"), ja.get("total"), ja.get("passed")) == (0, True, 3, 3) and \
         (b["rc"], jb.get("ok"), jb.get("total"), jb.get("passed")) == (1, False, 3, 1)
    return ok, [summary(a), summary(b)]

# ------------------------------------------------------------------ gaps
@check("x01", "gap", "misspelled fixture_kind KEY on a closure self-approval fixture is not a pass")
def x01(e):
    obs = [e.run({k: "closure", "finding": FINDING, "closer_role": "security-auditor", "expect_blocked": False})
           for k in ("fixture-kind", "Fixture_Kind", "fixturekind", "fixture_knid", "fixtureKind")]
    return not any(map(is_pass, obs)), [summary(o) for o in obs]

@check("x02", "gap", "misspelled packet WRAPPER key holding a blocked packet is not a pass")
def x02(e):
    obs = [e.run({k: MISS, "expectations": {"outcome": "pass"}}) for k in ("pakcet", "Packet", "packets")]
    return not any(map(is_pass, obs)), [summary(o) for o in obs]

@check("x03", "gap", "misspelled expectations KEY is not silently dropped")
def x03(e):
    obs = [e.run({"packet": DONE, k: {"outcome": "fail_gate"}}) for k in ("expectation", "Expectations", "expected")]
    # DONE passes on its own; a fixture whose stated expectation is fail_gate must not pass.
    return not any(map(is_pass, obs)), [summary(o) for o in obs]

@check("x04", "gap", "misspelled legal text key on a legal fixture is not a vacuous pass")
def x04(e):
    obs = [e.run({"fixture_kind": "legal", k: BAD_LEGAL}) for k in ("txt", "Text", "legal-text")]
    return not any(map(is_pass, obs)), [summary(o) for o in obs]

@check("x05", "gap", "accountable_role expectation is enforced when the result has no findings")
def x05(e):
    obs = [e.run({"packet": DONE, "expectations": {"outcome": "pass", "accountable_role": "nobody"}}),
           e.run({"fixture_kind": "legal", "text": BAD_LEGAL,
                  "expectations": {"outcome": "fail_gate", "accountable_role": "nobody"}})]
    return not any(map(is_pass, obs)), [summary(o) for o in obs]

@check("x06", "gap", "gate_codes expectation is not silently ignored when outcome is pass or absent")
def x06(e):
    obs = [e.run({"packet": DONE, "expectations": {"outcome": "pass", "gate_codes": ["MISSING_SPECIALIST_GATE"]}}),
           e.run({"packet": DONE, "expectations": {"gate_codes": ["MISSING_SPECIALIST_GATE"]}})]
    return not any(map(is_pass, obs)), [summary(o) for o in obs]

@check("x07", "gap", "fail_gate gate_codes: every listed gate must fire; empty list is not a wildcard")
def x07(e):
    obs = [e.run({"packet": MISS, "expectations": {"outcome": "fail_gate",
                                                    "gate_codes": ["MISSING_SPECIALIST_GATE", "SOME_OTHER_GATE"]}}),
           e.run({"packet": MISS, "expectations": {"outcome": "fail_gate", "gate_codes": []}})]
    return not any(map(is_pass, obs)), [summary(o) for o in obs]

@check("x08", "gap", "legal fixture with no expectations is not an unconditional pass")
def x08(e):
    a = e.run({"fixture_kind": "legal", "text": BAD_LEGAL})
    b = e.run({"fixture_kind": "legal", "text": "General information about filing deadlines. Not legal advice."})
    return not (is_pass(a) and is_pass(b)), [summary(a), summary(b)]

@check("x09", "gap", "malformed field types fail as INVALID_PACKET, not a traceback")
def x09(e):
    obs = [e.run({"fixture_kind": "legal", "text": "x", "freshness_days": "abc"}),
           e.run({"fixture_kind": "legal", "text": "x", "freshness_days": None}),
           e.run({"fixture_kind": "planted_defect", "defect": "security"}),
           e.run({"fixture_kind": "planted_defect", "defect": ["security"]}),
           e.run({"fixture_kind": "legal", "text": ["x"]})]
    return all(map(is_invalid, obs)), [summary(o) for o in obs]

@check("x10", "gap", "deeply nested JSON fails as INVALID_PACKET, not a traceback")
def x10(e):
    o = e.run(raw="[" * 200000 + "]" * 200000)
    return is_invalid(o), [summary(o)]

@check("x11", "gap", "one crashing fixture does not destroy the whole suite report")
def x11(e):
    o = e.suite({"p.json": DONE, "z.json": {"fixture_kind": "planted_defect", "defect": "security"}})
    j = o["json"]
    return o["rc"] == 1 and j is not None and j.get("total") == 2 and not o["traceback"], [summary(o)]

@check("x12", "gap", "duplicate fixture_kind key does not silently change the fixture kind")
def x12(e):
    raw = '{"fixture_kind": "closure", "finding": %s, "closer_role": "security-auditor", ' \
          '"expect_blocked": false, "fixture_kind": "packet"}' % json.dumps(FINDING)
    o = e.run(raw=raw)
    return not is_pass(o), [summary(o)]

@check("x13", "gap", "suite does not silently skip .JSON / .Json fixture files")
def x13(e):
    o = e.suite({"a.json": DONE, "B.JSON": {"packet": MISS, "expectations": {"outcome": "pass"}},
                 "C.Json": {"fixture_kind": "closre"}})
    j = o["json"] or {}
    return not (o["rc"] == 0 and j.get("ok") is True), [summary(o)]

@check("x14", "gap", "suite behaviour on a symlinked fixture subdirectory (reported, not scored as gap)")
def x14(e):
    def mk(t, root):
        ext = t / "external"
        ext.mkdir()
        (ext / "bad.json").write_text(json.dumps({"packet": MISS, "expectations": {"outcome": "pass"}}))
        os.symlink(ext, root / "linked")
    o = e.suite({"a.json": DONE}, setup=mk)
    j = o["json"] or {}
    # Either following the link (total 2, fails) or not (total 1, passes) is recorded;
    # the check only requires a clean JSON result. Cross-interpreter differences are the finding.
    return o["json"] is not None and not o["traceback"], [summary(o)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("engine")
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--json")
    ap.add_argument("--only", choices=("core", "gap"))
    a = ap.parse_args()
    e = Engine(a.engine, a.python)
    res, core_ok = [], True
    for cid, group, desc, fn in CHECKS:
        if a.only and group != a.only:
            continue
        try:
            held, obs = fn(e)
        except Exception as exc:  # oracle error is a failed check, never a pass
            held, obs = False, {"oracle_error": repr(exc)}
        res.append({"id": cid, "group": group, "desc": desc, "holds": held, "observed": obs})
        if group == "core" and not held:
            core_ok = False
        tag = "HOLDS" if held else ("FAIL" if group == "core" else "GAP")
        print(f"{cid} {tag:5} {desc}")
    print("core:", sum(r["holds"] for r in res if r["group"] == "core"), "/",
          sum(1 for r in res if r["group"] == "core"),
          " gaps open:", sum(not r["holds"] for r in res if r["group"] == "gap"), "/",
          sum(1 for r in res if r["group"] == "gap"))
    if a.json:
        Path(a.json).write_text(json.dumps({"engine": a.engine, "python": a.python, "results": res}, indent=1))
    sys.exit(0 if core_ok else 1)


if __name__ == "__main__":
    main()
