#!/usr/bin/env python3
"""G36 cross-goal checks for the day 6 candidates (G31, G32, G33, G34, G35).

Nothing in the checkout is written; inputs are copies of the candidates' own fixtures in a temporary
folder. No network, no socket, no browser.

  x1  G31 -> G17 capacity: the G17 result G31's fixture stores equals a fresh run of the integrated G17
      tool on the same package, G31 commits a date from it, and a G17 package changed after the result
      was stored makes G31 refuse the date (blocked) instead of using the old result.
  x2  G35 -> G14 finance tie-out: the recognized revenue G35 reports per currency equals the G14 tool run
      separately on the same finance package, and the G14 result word is carried unchanged.
  x3  G13 parser shared by G33 and G35: one csv_reconcile.py in the tree, both tools point at it, and the
      G13 status G35 reports for its spend export equals the G13 tool run on the same contract.
  x4  Read-only statements from real runs: G31 says read_only, G35 says nothing was published, scheduled,
      bought or sent, and every G32 draft has status draft and send "not performed".

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
G31 = os.path.join(ROOT, "employees/product-project/business-analyst/scope_acceptance.py")
G17 = os.path.join(ROOT, "employees/leadership/coo/resource_decision.py")
G35 = os.path.join(ROOT, "employees/marketing/paid-ads-manager/campaign_ledger.py")
G14 = os.path.join(ROOT, "employees/leadership/cfo/cash_revenue_reconcile.py")
G13 = os.path.join(ROOT, "employees/data/data-engineer/csv_reconcile.py")
G33 = os.path.join(ROOT, "employees/product-project/product-manager/evidence_decision.py")
G32 = os.path.join(ROOT, "employees/sales-outreach/customer-success/followthrough.py")
FX31 = os.path.join(ROOT, "examples/capabilities/G31/fixtures")
FX35 = os.path.join(ROOT, "examples/capabilities/G35/fixtures/september")
FX32 = os.path.join(ROOT, "examples/capabilities/G32/fixtures")
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")


def run(argv):
    r = subprocess.run([PY] + argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=ENV, timeout=300)
    try:
        doc = json.loads(r.stdout.decode("utf-8"))
    except ValueError:
        doc = None
    return r.returncode, doc, (r.stdout + r.stderr).decode("utf-8", "replace")


def x1(findings, lines):
    tmp = tempfile.mkdtemp(prefix="g36x1-")
    try:
        fx = os.path.join(tmp, "fx")
        shutil.copytree(FX31, fx)
        pkg = json.load(open(os.path.join(fx, "portal.json")))
        cap = pkg.get("capacity") or {}
        g17pkg, stored = os.path.join(fx, cap.get("package", "")), os.path.join(fx, cap.get("result", ""))
        rc17, fresh, out17 = run([G17, "evaluate", g17pkg, "--json"])
        if fresh is None or fresh != json.load(open(stored)):
            findings.append("x1 the G17 result G31 stores is not what the integrated G17 gives for its package (G17 exit %d)" % rc17)
            return
        rc, rep, out = run([G31, "check", os.path.join(fx, "portal.json"), "--json"])
        if rc != 0 or (rep or {}).get("status") != "ready" or not (rep or {}).get("capacity_finish"):
            findings.append("x1 G31 does not commit a date from current G17 evidence: exit %d, %s" % (rc, out[-200:]))
            return
        doc = json.load(open(g17pkg))  # capacity changes after the result was stored: one week later start
        y, m, d = doc["calendar"]["start"].split("-")
        import datetime as dt
        doc["calendar"]["start"] = (dt.date(int(y), int(m), int(d)) + dt.timedelta(days=7)).isoformat()
        json.dump(doc, open(g17pkg, "w"))
        rc2, rep2, out2 = run([G31, "check", os.path.join(fx, "portal.json"), "--json"])
        text = json.dumps(rep2 or {})
        if rc2 != 1 or (rep2 or {}).get("status") == "ready" or "does not match a rerun" not in text:
            findings.append("x1 G31 still relies on a stored G17 result after its package changed: exit %d, status %s"
                            % (rc2, (rep2 or {}).get("status")))
        else:
            lines.append("x1 G31 date %s rests on the current G17 result; a changed G17 package blocks it" % rep["capacity_finish"])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def x2(findings, lines):
    rc35, rep35, out35 = run([G35, "reconcile", os.path.join(FX35, "campaign.json"), "--json"])
    rc14, rep14, out14 = run([G14, "reconcile", os.path.join(FX35, "finance", "package.json"), "--json"])
    tie = (rep35 or {}).get("finance_tie_out")
    if not tie or rep14 is None:
        findings.append("x2 chain did not run: G35 exit %d, G14 exit %d" % (rc35, rc14))
        return
    bad = []
    for cur, v in sorted((rep14.get("currencies") or {}).items()):
        got = (tie["currencies"].get(cur) or {}).get("recognized_revenue")
        if got != v.get("recognized_revenue"):
            bad.append("%s G35 %s G14 %s" % (cur, got, v.get("recognized_revenue")))
    if tie.get("result") != rep14.get("result"):
        bad.append("result G35 %s G14 %s" % (tie.get("result"), rep14.get("result")))
    if bad:
        findings.append("x2 G35 finance tie-out differs from G14: " + "; ".join(bad))
    else:
        lines.append("x2 G35 recognized revenue equals G14 (%s), result %s"
                     % (", ".join("%s %s" % (c, v["recognized_revenue"]) for c, v in sorted(rep14["currencies"].items())), rep14["result"]))


def x3(findings, lines):
    copies = []
    for d, sub, files in os.walk(ROOT):
        sub[:] = [s for s in sub if s not in (".git", "__pycache__")]
        if "csv_reconcile.py" in files:
            copies.append(os.path.relpath(os.path.join(d, "csv_reconcile.py"), ROOT))
    refs = []
    for tool in (G33, G35):
        src = open(tool, encoding="utf-8").read()
        refs.append('"data" / "data-engineer" / "csv_reconcile.py"' in src)
    rc13, rep13, _ = run([G13, "reconcile", os.path.join(FX35, "spend-contract.json"), "--json"])
    rc35, rep35, _ = run([G35, "reconcile", os.path.join(FX35, "campaign.json"), "--json"])
    s35 = (((rep35 or {}).get("inputs") or {}).get("spend_export") or {}).get("g13_status")
    s13 = (rep13 or {}).get("status")
    if copies != ["employees/data/data-engineer/csv_reconcile.py"] or not all(refs):
        findings.append("x3 G13 parser copies %s; G33/G35 point at it: %s" % (copies, refs))
    elif s13 is None or s35 != s13:
        findings.append("x3 G35 reports G13 status %s for the spend export, the G13 tool says %s" % (s35, s13))
    else:
        lines.append("x3 one csv_reconcile.py, loaded by G33 and G35; spend export status %s in both" % s13)


def x4(findings, lines):
    rc31, rep31, _ = run([G31, "check", os.path.join(FX31, "portal.json"), "--json"])
    rc35, rep35, _ = run([G35, "reconcile", os.path.join(FX35, "campaign.json"), "--json"])
    tmp = tempfile.mkdtemp(prefix="g36x4-")
    try:
        rc32, _, out32 = run([G32, "run", os.path.join(tmp, "st"), "--account", os.path.join(FX32, "account.json"),
                              "--events", os.path.join(FX32, "events.jsonl"), "--now", "2026-10-08T12:00:00-07:00",
                              "--worker", "w1", "--json"])
        dd = os.path.join(tmp, "st", "drafts")
        drafts = sorted(os.listdir(dd)) if os.path.isdir(dd) else []
        unsent = [f for f in drafts if str(json.load(open(os.path.join(dd, f), encoding="utf-8")).get("send", "")).startswith("not performed")
                  and json.load(open(os.path.join(dd, f), encoding="utf-8")).get("status") == "draft"]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    ok31 = (rep31 or {}).get("read_only") is True
    ok35 = "nothing was published, scheduled, bought or sent" in ((rep35 or {}).get("read_only") or "")
    ok32 = rc32 == 0 and drafts and len(unsent) == len(drafts)
    if not ok31:
        findings.append("x4 G31 report is not marked read_only (exit %d)" % rc31)
    if not ok35:
        findings.append("x4 G35 report does not state that nothing was published or spent (exit %d)" % rc35)
    if not ok32:
        findings.append("x4 G32 drafts without the no-send statement: %d of %d (exit %d)" % (len(drafts) - len(unsent), len(drafts), rc32))
    if ok31 and ok35 and ok32:
        lines.append("x4 G31 read_only, G35 nothing published or spent, all %d G32 drafts unsent" % len(drafts))


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
