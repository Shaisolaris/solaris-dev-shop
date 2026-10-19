#!/usr/bin/env python3
"""G24 cross-goal checks for the day 4 candidates (G15, G16, G17, G19; G17 carries G13 and G14).

Nothing in the checkout is written; inputs are copies of the candidates' own fixtures in a temporary
folder and no socket is opened.

  x1  G14 -> G17 figure agreement: the monthly inflow G17 takes "from_g14" must equal what the G14
      tool itself reports for the same books, run separately (net cash x 365/12 / days in the
      period).
  x2  G14 -> G17 refusal: books that G14 does not reconcile cleanly must not feed a G17 decision:
      G17 refuses the package (exit 2) or reports blocked_evidence (exit 1), never a decision.
  x3  G13 -> G15 shared parser: G15 says its CSV parsing and row rejects come from G13; the module it
      loads must be the integrated G13 file, not a private copy.

Exit 0 when every check holds, 1 when a check produced a finding (listed as FINDING lines).
"""
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
PY = sys.executable
G14 = os.path.join(ROOT, "employees/leadership/cfo/cash_revenue_reconcile.py")
G17 = os.path.join(ROOT, "employees/leadership/coo/resource_decision.py")
G15 = os.path.join(ROOT, "employees/data/data-scientist/experiment_readout.py")
G13 = os.path.join(ROOT, "employees/data/data-engineer/csv_reconcile.py")
FX17 = os.path.join(ROOT, "examples/capabilities/G17/fixtures")
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")


def run(argv):
    r = subprocess.run([PY] + argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=ENV, timeout=300)
    try:
        doc = json.loads(r.stdout.decode("utf-8"))
    except ValueError:
        doc = None
    return r.returncode, doc, (r.stdout + r.stderr).decode("utf-8", "replace")


def _t(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def g14_expect(pkg, currency, measure):
    rc, rep, out = run([G14, "reconcile", pkg, "--json"])
    if rep is None:
        return rc, None
    cur = rep["currencies"][currency]
    if measure == "closing_ar_owed":
        return rc, Fraction(cur["closing"]["ar_owed"])
    days = Fraction(int((_t(rep["period"]["end"]) - _t(rep["period"]["start"])).total_seconds()), 86400)
    return rc, Fraction(cur["net_cash"]) * Fraction(365, 12) / days


def setup(tmp, measure="monthly_net_cash", books="books-sept"):
    shutil.copytree(FX17, os.path.join(tmp, "fx"))
    p = os.path.join(tmp, "fx", "studio.json")
    with open(p) as fh:
        doc = json.load(fh)
    a = doc["assumptions"]["inflow"]
    a["from_g14"] = {"package": books + "/package.json", "measure": measure}
    with open(p, "w") as fh:
        json.dump(doc, fh)
    return p, doc.get("currency", "USD")


def x1(findings, lines):
    for measure in ("monthly_net_cash",):
        tmp = tempfile.mkdtemp(prefix="g24x1-")
        try:
            p, cur = setup(tmp, measure)
            rc14, want = g14_expect(os.path.join(tmp, "fx", "books-sept", "package.json"), cur, measure)
            rc17, rep, out = run([G17, "evaluate", p, "--json"])
        finally:
            shutil.rmtree(tmp)
        if rep is None or want is None:
            findings.append("x1 %s: no readable result (G14 rc=%s, G17 rc=%s %s)" % (measure, rc14, rc17, out.strip()[-120:]))
            continue
        got = rep["assumptions"]["inflow"]
        hi = Fraction(str(got["high"]))
        if abs(hi - want) > Fraction(1, 100):
            findings.append("x1 %s: G17 uses %s, G14 reports %s" % (measure, got["high"], float(want)))
        else:
            lines.append("x1 %s: G17 %s equals G14 %.2f" % (measure, got["high"], float(want)))


def x2(findings, lines):
    tmp = tempfile.mkdtemp(prefix="g24x2-")
    try:
        p, cur = setup(tmp, books="books-unreconciled")
        rc14, _, _ = run([G14, "reconcile", os.path.join(tmp, "fx", "books-unreconciled", "package.json")])
        rc17, rep, out = run([G17, "evaluate", p, "--json"])
    finally:
        shutil.rmtree(tmp)
    if rc14 == 0:
        findings.append("x2 G14 reconciles books-unreconciled cleanly; the fixture no longer tests refusal")
    elif not (rc17 == 2 or (rc17 == 1 and (rep or {}).get("status") == "blocked_evidence")):
        findings.append("x2 G14 exit %s books fed a G17 decision (G17 exit %s, status %s)" % (rc14, rc17, (rep or {}).get("status")))
    else:
        lines.append("x2 G14 exit %s books kept out of a G17 decision: G17 exit %s, status %s" % (rc14, rc17, (rep or {}).get("status", "refused")))


def x3(findings, lines):
    with open(G15) as fh:
        src = fh.read()
    refs = sorted(set(re.findall(r"[\"']([A-Za-z0-9_/.-]*csv_reconcile\.py)[\"']", src)))
    copies = [os.path.relpath(os.path.join(d, f), ROOT) for d, _, fs in os.walk(os.path.join(ROOT, "employees"))
              for f in fs if f == "csv_reconcile.py"]
    if copies != ["employees/data/data-engineer/csv_reconcile.py"] or not refs:
        findings.append("x3 G15 parser source: references %s, copies %s" % (refs, copies))
    else:
        lines.append("x3 G15 loads the G13 parser by %s; one copy in the tree" % refs[0])


def main():
    findings, lines = [], []
    for fn in (x1, x2, x3):
        fn(findings, lines)
    for l in lines:
        print(l)
    for f in findings:
        print("FINDING " + f)
    print("CROSS-CHECKS %s (%d finding%s)" % ("CLEAN" if not findings else "FINDINGS", len(findings), "" if len(findings) == 1 else "s"))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
