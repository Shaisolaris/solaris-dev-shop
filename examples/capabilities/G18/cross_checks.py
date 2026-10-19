#!/usr/bin/env python3
"""G18 cross-goal checks for the day 3 candidates (G10, G11, G13, G14; G03 is carried by G11).

Each check feeds one candidate's real output or input convention to another and compares the two
tools, never a stored answer. All inputs are synthetic copies of the candidates' own fixtures in a
temporary folder; nothing in the checkout is written and no socket is opened.

  x1  G10 -> G11 layer agreement: every G10 fixture, re-timed into the G11 regression impact,
      gives the G11 decision that netdiag's own verdict implies (non-application layer during the
      impact: do_not_rollback; otherwise rollback).
  x2  G10 -> G11 unusable evidence: a supplied G10 trace that netdiag refuses, or that has no
      capture time, must appear in the G11 decision trace (or stop the decision); a rollback whose
      trace never mentions the supplied network evidence is a finding.
  x3  G13 / G14 shared conventions: a row loaded exactly at as_of, and the amount spellings both
      contracts document ("1,250.50", "+10", "1e1", "1,0"), are treated the same by both tools.
      Sub-cent amounts are a documented difference (G14 books cash in cents) and only noted.

Exit 0 when every check holds, 1 when a check produced a finding (listed as FINDING lines).
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
PY = sys.executable
ND = os.path.join(ROOT, "employees/infrastructure/network-engineer/netdiag.py")
IS = os.path.join(ROOT, "employees/infrastructure/site-reliability-engineer/incident_slo.py")
G13 = os.path.join(ROOT, "employees/data/data-engineer/csv_reconcile.py")
G14 = os.path.join(ROOT, "employees/leadership/cfo/cash_revenue_reconcile.py")
FX10 = os.path.join(ROOT, "examples/capabilities/G10/fixtures")
FX11 = os.path.join(ROOT, "examples/capabilities/G11/fixtures/02-deploy-regression.json")
NON_APP = ("dns", "route", "tls")
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")


def run(argv):
    r = subprocess.run([PY] + argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=ENV, timeout=300)
    try:
        doc = json.loads(r.stdout.decode("utf-8"))
    except ValueError:
        doc = None
    return r.returncode, doc, r.stderr.decode("utf-8", "replace")


def bundle_with(tmp, trace):
    os.makedirs(os.path.join(tmp, "traces"), exist_ok=True)
    with open(os.path.join(tmp, "traces", "t.json"), "w") as fh:
        json.dump(trace, fh)
    with open(FX11) as fh:
        b = json.load(fh)
    b["diagnoses"] = ["traces/t.json"]
    with open(os.path.join(tmp, "b.json"), "w") as fh:
        json.dump(b, fh)
    return os.path.join(tmp, "traces", "t.json"), os.path.join(tmp, "b.json")


def x1(findings, lines):
    n = 0
    for name in sorted(os.listdir(FX10)):
        if not name.endswith(".json"):
            continue
        with open(os.path.join(FX10, name)) as fh:
            trace = json.load(fh)
        trace["captured_at"] = "2026-10-18T09:30:00Z"
        tmp = tempfile.mkdtemp(prefix="g18x1-")
        try:
            tpath, bpath = bundle_with(tmp, trace)
            nrc, nd, _ = run([ND, "diagnose", tpath, "--json"])
            irc, rep, err = run([IS, "report", bpath, "--json"])
        finally:
            shutil.rmtree(tmp)
        if nd is None or rep is None or irc != 0:
            findings.append("x1 %s: no readable result (netdiag rc=%s, incident rc=%s %s)" % (name, nrc, irc, err.strip()[-120:]))
            continue
        want = "do_not_rollback" if (nd.get("verdict") in ("localized", "probable") and nd.get("layer") in NON_APP
                                     and "application" not in nd.get("candidates", [])) else "rollback"
        got = rep["decision"]["decision"]
        seen = [d for d in rep.get("diagnoses", []) if d.get("status") == "ok"]
        same = bool(seen) and seen[0].get("verdict") == nd.get("verdict") and seen[0].get("layer") == nd.get("layer")
        if got != want or not same:
            findings.append("x1 %s: netdiag %s/%s implies %s, G11 decided %s%s" % (
                name, nd.get("verdict"), nd.get("layer"), want, got, "" if same else " (G11 read a different verdict)"))
        n += 1
    lines.append("x1 G10 -> G11 layer agreement: %d fixtures compared" % n)


def x2(findings, lines):
    with open(os.path.join(FX10, "02-dns-nxdomain.json")) as fh:
        src = json.load(fh)
    for label, value in (("refused capture time", "18/10/2026 09:30"), ("no capture time", None)):
        trace = dict(src, captured_at=value)
        tmp = tempfile.mkdtemp(prefix="g18x2-")
        try:
            _, bpath = bundle_with(tmp, trace)
            irc, rep, err = run([IS, "report", bpath, "--json"])
        finally:
            shutil.rmtree(tmp)
        if rep is None:
            lines.append("x2 %s: G11 refused the bundle (rc=%s), the evidence is not silently dropped" % (label, irc))
            continue
        dec = rep["decision"]
        mentioned = any("diagnos" in (t.get("check", "") + t.get("observed", "")).lower() or "trace" in t.get("observed", "")
                        for t in dec.get("trace", []))
        if dec["decision"] == "rollback" and not mentioned:
            findings.append("x2 %s: G11 recommends %s (exit %s) and its decision trace never mentions the supplied G10 trace "
                            "(status %s)" % (label, dec["decision"], irc, [d.get("status") for d in rep.get("diagnoses", [])]))
        else:
            lines.append("x2 %s: decision %s, trace mentions the evidence: %s" % (label, dec["decision"], mentioned))
    lines.append("x2 G10 -> G11 unusable supplied evidence: 2 cases")


def _g13_orders(contract):
    rc, rep, _ = run([G13, "reconcile", contract, "--json"])
    return None if rep is None else rep["metrics"]["orders"]["groups"][0]["value"]


def _g13(tmp, loaded, amount):
    shutil.copytree(os.path.join(ROOT, "examples/capabilities/G13/fixtures/clean"), tmp + "/g13")
    with open(tmp + "/g13/contract.json") as fh:
        asof = json.load(fh)["as_of"]
    before = _g13_orders(tmp + "/g13/contract.json")
    with open(tmp + "/g13/orders.csv", "a") as fh:
        fh.write('X9,K1,"%s",USD,paid,2026-09-20T10:00:00Z,%s,2026-09-20T10:00:00Z\n' % (amount, loaded or asof))
    after = _g13_orders(tmp + "/g13/contract.json")
    if before is None or after is None:
        return "refused"
    return "included" if after == before + 1 else ("left out" if after == before else "orders %s -> %s" % (before, after))


def _g14(tmp, loaded, amount):
    shutil.copytree(os.path.join(ROOT, "examples/capabilities/G14/fixtures/clean"), tmp + "/g14")
    with open(tmp + "/g14/package.json") as fh:
        pkg = json.load(fh)
    asof = pkg["as_of"]
    pkg["payments"]["thousands_separator"] = ","  # the same convention the G13 contract declares
    with open(tmp + "/g14/package.json", "w") as fh:
        json.dump(pkg, fh)
    with open(tmp + "/g14/payments.csv", "a") as fh:
        fh.write('P9,I1,USD,"%s",2026-09-20T09:00:00Z,%s\n' % (amount, loaded or asof))
    rc, rep, _ = run([G14, "reconcile", tmp + "/g14/package.json", "--json"])
    if rep is None:
        return "refused"
    ex = rep.get("exceptions", {})
    if any(r.get("id") == "P9" or r.get("line") == 4 for r in ex.get("rejected", [])):
        return "left out"
    if any("P9" in json.dumps(r) for r in ex.get("late", [])):
        return "late"
    return "included"


def x3(findings, lines):
    cases = [("loaded exactly at as_of", None, "30.00", True), ("thousands separator", "2026-09-21T00:00:00Z", "1,250.50", True),
             ("leading plus", "2026-09-21T00:00:00Z", "+10", True), ("exponent", "2026-09-21T00:00:00Z", "1e1", True),
             ("comma decimal", "2026-09-21T00:00:00Z", "1,0", True), ("sub-cent", "2026-09-21T00:00:00Z", "10.005", False)]
    for label, loaded, amount, must_agree in cases:
        tmp = tempfile.mkdtemp(prefix="g18x3-")
        try:
            a, b = _g13(tmp, loaded, amount), _g14(tmp, loaded, amount)
        finally:
            shutil.rmtree(tmp)
        if a != b and must_agree:
            findings.append("x3 %s (%r): G13 %s, G14 %s" % (label, amount, a, b))
        else:
            lines.append("x3 %s (%r): G13 %s, G14 %s%s" % (label, amount, a, b, "" if a == b else " (documented difference)"))


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
