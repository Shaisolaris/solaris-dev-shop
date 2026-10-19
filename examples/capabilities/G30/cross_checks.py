#!/usr/bin/env python3
"""G30 cross-goal checks for the day 5 candidates (G20, G21, G22, G23, G24, G25).

Nothing in the checkout is written; inputs are copies of the candidates' own fixtures in a temporary
folder. No network, no socket, no browser (owner rule: G20 is checked by its own JavaScriptCore oracle
only, never in a browser).

  x1  G22 -> G14 -> G17 figure agreement: the books G22 exports for September, reconciled by G14 and fed
      to G17 as "from_g14", must give the monthly inflow G14's own net cash implies (x 365/12 / days).
  x2  G22 open exceptions -> G14 -> G17: when G22 ingest leaves exceptions open (here a refund.succeeded
      for 40.00 it could not apply, and an out-of-stock order), the exported books must not reach a G17
      decision as if they were clean: export refuses, G14 does not reconcile, or G17 reports
      blocked_evidence. A stream without those two events is the control and must go through.
  x3  Scope statements: G23 and G25 reports must say they are synthetic and offline (evidence_scope,
      claim_scope), so the matrix never carries a live-system claim from them.

Exit 0 when every check holds, 1 when a check produced a finding (listed as FINDING lines).
"""
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import tempfile
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
PY = sys.executable
G22 = os.path.join(ROOT, "employees/specialized/payments-specialist/payment_ledger.py")
G14 = os.path.join(ROOT, "employees/leadership/cfo/cash_revenue_reconcile.py")
G17 = os.path.join(ROOT, "employees/leadership/coo/resource_decision.py")
G23 = os.path.join(ROOT, "employees/specialized/wordpress-master/wp_trace_diag.py")
G25 = os.path.join(ROOT, "employees/engineering/iot-engineer/device_protocol.py")
FX22 = os.path.join(ROOT, "examples/capabilities/G22/fixtures")
FX17 = os.path.join(ROOT, "examples/capabilities/G17/fixtures")
FX23 = os.path.join(ROOT, "examples/capabilities/G23/fixtures")
FX25 = os.path.join(ROOT, "examples/capabilities/G25/fixtures")
OPEN_EVENTS = ("evt_007", "evt_008")
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")


def run(argv):
    r = subprocess.run([PY] + argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=ENV, timeout=300)
    try:
        doc = json.loads(r.stdout.decode("utf-8"))
    except ValueError:
        doc = None
    return r.returncode, doc, (r.stdout + r.stderr).decode("utf-8", "replace")


def chain(tmp, drop=()):
    """G22 ingest -> report -> export-g14 -> G14 reconcile -> G17 evaluate. Returns a dict of results."""
    stream = os.path.join(tmp, "stream.jsonl")
    with open(os.path.join(FX22, "september.jsonl")) as src, open(stream, "w") as dst:
        for line in src:
            if json.loads(json.loads(line)["body"]).get("id") not in drop:
                dst.write(line)
    db = os.path.join(tmp, "ledger.db")
    res = {}
    res["init"] = run([G22, "init", "--db", db, "--catalog", os.path.join(FX22, "catalog.json")])[0]
    res["ingest"] = run([G22, "ingest", "--db", db, "--secret-file", os.path.join(FX22, "test-secret.txt"),
                         "--events", stream, "--now", "1790000200"])[0]
    res["report"] = run([G22, "report", "--db", db, "--json"])[1] or {}
    fx = os.path.join(tmp, "fx")
    shutil.copytree(FX17, fx)
    res["export"] = run([G22, "export-g14", "--db", db, "--out", os.path.join(fx, "g22books"),
                         "--period-start", "2026-09-01T00:00:00Z", "--period-end", "2026-10-01T00:00:00Z"])[0]
    res["g14_rc"], res["g14"], _ = run([G14, "reconcile", os.path.join(fx, "g22books", "package.json"), "--json"])
    p = os.path.join(fx, "studio.json")
    with open(p) as fh:
        doc = json.load(fh)
    inflow = doc["assumptions"]["inflow"]
    inflow["from_g14"] = {"package": "g22books/package.json", "measure": "monthly_net_cash"}
    inflow["low"] = 1  # the synthetic store books tens of dollars, not the studio's retainers
    with open(p, "w") as fh:
        json.dump(doc, fh)
    res["g17_rc"], res["g17"], res["g17_out"] = run([G17, "evaluate", p, "--json"])
    res["currency"] = doc.get("currency", "USD")
    return res


def g14_monthly(rep, currency):
    t = lambda s: dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    days = Fraction(int((t(rep["period"]["end"]) - t(rep["period"]["start"])).total_seconds()), 86400)
    return Fraction(rep["currencies"][currency]["net_cash"]) * Fraction(365, 12) / days


def x1(findings, lines):
    tmp = tempfile.mkdtemp(prefix="g30x1-")
    try:
        r = chain(tmp, drop=OPEN_EVENTS)
        if r["export"] != 0 or r["g14_rc"] != 0 or r["g14"] is None or r["g17"] is None:
            findings.append("x1 chain did not run: export %s, G14 %s, G17 %s: %s"
                            % (r["export"], r["g14_rc"], r["g17_rc"], r["g17_out"][-200:]))
            return
        want = g14_monthly(r["g14"], r["currency"])
        got = Fraction(str(r["g17"]["assumptions"]["inflow"]["value"]))
        if abs(got - want) > Fraction(1, 10 ** 5):
            findings.append("x1 G17 uses %s for G22 books, G14 implies %s" % (got, float(want)))
        else:
            lines.append("x1 G22 books -> G14 net cash %s -> G17 inflow %s/month (agrees)"
                         % (r["g14"]["currencies"][r["currency"]]["net_cash"], r["g17"]["assumptions"]["inflow"]["value"]))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def x2(findings, lines):
    net = {}
    for drop, label in ((OPEN_EVENTS, "control"), ((), "september")):
        tmp = tempfile.mkdtemp(prefix="g30x2-")
        try:
            r = chain(tmp, drop=drop)
            open_ids = [o.get("id") for o in r["report"].get("open", [])]
            unapplied = r["report"].get("money", {}).get("unapplied_refunds")
            stopped = (r["export"] != 0 or r["g14_rc"] != 0 or r["g17_rc"] == 2
                       or (r["g17"] or {}).get("status") == "blocked_evidence")
            net[label] = ((r["g14"] or {}).get("currencies", {}).get(r["currency"], {}) or {}).get("net_cash")
            if label == "control":
                if open_ids or stopped:
                    findings.append("x2 control stream (no open exceptions) did not go through: open %s, export %s, G14 %s, G17 %s"
                                    % (open_ids, r["export"], r["g14_rc"], r["g17_rc"]))
                continue
            if not open_ids:
                findings.append("x2 setup: the september stream left no open exception in G22")
            elif not stopped:
                findings.append("x2 G22 has open exceptions %s (unapplied refunds %s) but export-g14 exit %d, G14 exit %d and "
                                "G17 decides (exit %d, status %s) on net cash %s (stream without them: %s)"
                                % (",".join(open_ids), unapplied, r["export"], r["g14_rc"], r["g17_rc"],
                                   (r["g17"] or {}).get("status"), net[label], net.get("control")))
            else:
                lines.append("x2 G22 open exceptions %s kept out of a G17 decision" % ",".join(open_ids))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


def x3(findings, lines):
    rc23, rep23, out23 = run([G23, "diagnose", os.path.join(FX23, "02-plugin-conflict.json"), "--json"])
    rc25, rep25, out25 = run([G25, "ingest", "--commands", os.path.join(FX25, "commands.jsonl"),
                              "--events", os.path.join(FX25, "faulty-events.jsonl"), "--json"])
    s23 = (rep23 or {}).get("evidence_scope") or ""
    s25 = (rep25 or {}).get("claim_scope") or ""
    ok23 = "synthetic" in s23 and "no php, wordpress" in s23.lower()
    ok25 = "synthetic" in s25 and "not hardware" in s25
    if not ok23:
        findings.append("x3 G23 report scope does not disclaim a live site: %r (exit %d)" % (s23[:120], rc23))
    if not ok25:
        findings.append("x3 G25 report scope does not disclaim hardware: %r (exit %d)" % (s25[:120], rc25))
    if ok23 and ok25:
        lines.append("x3 G23 evidence_scope and G25 claim_scope both state synthetic, offline evidence")


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
