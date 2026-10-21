#!/usr/bin/env python3
"""G42 cross-goal checks for the day 7 candidates (G37, G38, G39, G40, G41) on the newest repair heads.

Nothing in the checkout is written; every tool runs on this tree or on temporary copies. No network,
no socket, no browser.

  x1  G39 drill on this stack: the delivery drill composes G04 handoff, G02 activation, G13, G19, G03 and
      G05 tools; this stack carries G02 r4, G04 r3, G05 r3 and G19 h1, so the drill must still pass with
      the repaired tools (not only with the copies G39 was built on).
  x2  G38 provenance on the integrated tree: with G38's own fixtures excluded, every license declaration
      the stack brings agrees and the result is consistent.
  x3  security-auditor contract after the G19 + G38 union: it parses, every script it lists exists in the
      role folder and compiles, and G40 skill-copy of the role finds only the shared standards it already
      documents as outside the folder (no listed script missing).
  x4  legal-advisor receives G37 and G38 output: its contract names both test files (which exist), the G37
      report says it is not legal advice and the G38 report says it is not a legal opinion.

Exit 0 when every check holds, 1 when a check produced a finding (listed as FINDING lines).
"""
import json
import os
import py_compile
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
PY = sys.executable
DRILL = os.path.join(ROOT, "examples/capabilities/G39/drill.py")
G38 = os.path.join(ROOT, "employees/quality-security/security-auditor/provenance_check.py")
G40 = os.path.join(ROOT, "employees/quality-security/qa-engineer/host_portability.py")
G37 = os.path.join(ROOT, "employees/legal-compliance/compliance-auditor/privacy_inventory.py")
SEC = os.path.join(ROOT, "employees/quality-security/security-auditor")
LEGAL = os.path.join(ROOT, "employees/legal-compliance/legal-advisor/capability.contract.json")
G37PKG = os.path.join(ROOT, "examples/capabilities/G37/fixtures/september/package.json")
SHARED_OUTSIDE = {"../QUALITY-SECURITY-STANDARD.md", "../assurance/ASSURANCE.md", "../assurance/quality_os.py"}
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
ENV.pop("G20_CHROME", None)


def run(argv, cwd=ROOT):
    r = subprocess.run([PY] + argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=ENV, cwd=cwd, timeout=900)
    out = r.stdout.decode("utf-8", "replace")
    try:
        doc = json.loads(out)
    except ValueError:
        doc = None
    return r.returncode, doc, out + r.stderr.decode("utf-8", "replace")


def x1(findings, lines):
    rc, _, out = run([DRILL])
    last = out.rstrip().splitlines()[-1] if out.strip() else ""
    bad = [l for l in out.splitlines() if l.startswith("FAIL")]
    if rc != 0 or last != "DRILL PASSED" or bad:
        findings.append("x1 G39 drill does not pass on G02 r4 / G04 r3 / G05 r3 / G19 h1: exit %d, %s"
                        % (rc, "; ".join(bad[:3]) or last))
    else:
        steps = len([l for l in out.splitlines() if l.startswith("ok ")])
        lines.append("x1 G39 drill passes on G02 r4, G04 r3, G05 r3 and G19 h1 (%d steps ok)" % steps)


def x2(findings, lines):
    rc, doc, out = run([G38, "check", ".", "--exclude", "examples/capabilities/G38/fixtures", "--json"])
    if rc != 0 or not doc or doc.get("result") != "consistent" or doc.get("findings"):
        findings.append("x2 G38 provenance on the integrated tree: exit %d, result %s, findings %s"
                        % (rc, (doc or {}).get("result"), [f.get("code") for f in (doc or {}).get("findings", [])][:5]))
    else:
        lines.append("x2 G38 provenance on the integrated tree: %s, %d declarations all %s"
                     % (doc["result"], doc["declarations"], "/".join(doc["declared_values"])))


def x3(findings, lines):
    try:
        with open(os.path.join(SEC, "capability.contract.json"), encoding="utf-8") as handle:
            contract = json.load(handle)
    except ValueError as e:
        findings.append("x3 security-auditor contract does not parse: %s" % e)
        return
    scripts = contract.get("dependencies", {}).get("scripts", [])
    missing = [s for s in scripts if not os.path.isfile(os.path.join(SEC, s))]
    broken = []
    with tempfile.TemporaryDirectory() as d:
        for s in scripts:
            if s in missing:
                continue
            try:
                py_compile.compile(os.path.join(SEC, s), cfile=os.path.join(d, s + "c"), doraise=True)
            except py_compile.PyCompileError:
                broken.append(s)
    rc, doc, out = run([G40, "skill-copy", ".", "quality-security/security-auditor", "--json"])
    outside = {m.get("ref") for m in (doc or {}).get("missing", [])}
    if missing or broken or sorted(scripts) != ["boundary_probe.py", "provenance_check.py"]:
        findings.append("x3 security-auditor scripts %s: missing %s, not compiling %s" % (scripts, missing, broken))
    elif doc is None or not outside <= SHARED_OUTSIDE:
        findings.append("x3 G40 skill-copy of security-auditor misses more than the shared standards: %s"
                        % sorted(outside - SHARED_OUTSIDE))
    else:
        lines.append("x3 security-auditor lists %s, both present and compiling; G40 skill-copy misses only %d shared standards"
                     % (" and ".join(scripts), len(outside)))


def x4(findings, lines):
    with open(LEGAL, encoding="utf-8") as handle:
        text = handle.read()
    named = [t for t in ("tests/test_g37_capability.py", "tests/test_g38_capability.py") if t in text]
    exist = [t for t in named if os.path.isfile(os.path.join(ROOT, t))]
    rc37, doc37, _ = run([G37, "review", G37PKG, "--json"])
    rc38, doc38, _ = run([G38, "check", ".", "--exclude", "examples/capabilities/G38/fixtures", "--json"])
    ok37 = bool((doc37 or {}).get("not_legal_advice"))
    ok38 = "not a legal opinion" in ((doc38 or {}).get("statement") or "")
    if len(exist) != 2:
        findings.append("x4 legal-advisor contract names %s of the G37 and G38 tests (present: %s)" % (named, exist))
    if not ok37:
        findings.append("x4 G37 report has no not_legal_advice statement (exit %d)" % rc37)
    if not ok38:
        findings.append("x4 G38 report does not say it is not a legal opinion (exit %d)" % rc38)
    if len(exist) == 2 and ok37 and ok38:
        lines.append("x4 legal-advisor names the G37 and G38 tests; G37 not legal advice, G38 not a legal opinion")


def main():
    findings, lines = [], []
    for fn in (x1, x2, x3, x4):
        fn(findings, lines)
    for l in lines:
        print(l)
    for f in findings:
        print("FINDING " + f)
    print("CROSS-CHECKS %s (%d finding%s)" % ("CLEAN" if not findings else "FINDINGS", len(findings), "" if len(findings) == 1 else "s"))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
