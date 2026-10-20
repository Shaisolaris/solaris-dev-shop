#!/usr/bin/env python3
"""M05 r2 probe (Grok self-validation, not independent review). In-process checks of waiver-governed closure in
quality_os (G05), written for this pass from the root finding ("treat waiver-governed closure and expiry consistently
in both functions") and ASSURANCE.md ("a valid waiver closes a waived finding at any revision until it expires").
Usage: PY m05r2_probe.py REPO OUT.json"""
import inspect, json, sys
from datetime import datetime, timezone
from pathlib import Path
REPO = Path(sys.argv[1]).resolve(); OUT = sys.argv[2]
sys.path.insert(0, str(REPO / "employees/quality-security/assurance")); import quality_os as q
ROWS = []
def row(rid, desc, ok, detail):
    ROWS.append({"id": rid, "desc": desc, "pass": bool(ok), "detail": detail})
    print("%s %s %s %s" % (rid, "PASS" if ok else "FAIL", desc, json.dumps(detail, default=str)[:300]))
BEFORE = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc); AFTER = datetime(2027, 2, 1, 0, 0, tzinfo=timezone.utc)
R1, R2 = "1" * 40, "2" * 40
def fnd(**o):
    f = q.create_finding(defect_kind="security", severity="S1", title="Session token in URL", evidence=["probe: token visible in referrer"],
                         reporter_role="qa-engineer", finding_id="fnd-m05r2"); [setattr(f, k, v) for k, v in o.items()]; return f
def wvr(**o):
    d = dict(waiver_id="wvr-m05r2", finding_id="fnd-m05r2", requested_by_role="security-auditor", approved_by_role="human-owner",
             human_authority=True, justification="Accepted until the January patch train", expires_at="2027-01-15T00:00:00+00:00", status="active")
    d.update(o); return q.Waiver(**d)
CI = inspect.signature(q.closure_is_current).parameters; RO = inspect.signature(q.reopen_finding).parameters
TAKES = "waiver" in CI and "as_of" in CI and "waiver" in RO and "as_of" in RO
def current(f, rev, w=None, as_of=None):
    return q.closure_is_current(f, rev, waiver=w, as_of=as_of) if TAKES else q.closure_is_current(f, rev)
def reopen(f, w=None, as_of=None, reason="waiver lapsed; fix not shipped"):
    kw = dict(reason=reason, current_revision=R2, reopened_by_role="release-manager")
    if TAKES: kw.update(waiver=w, as_of=as_of)
    return q.reopen_finding(f, **kw)
w = wvr(); closed, codes = q.close_finding(fnd(status="waived"), closer_role="release-manager", independent_evidence=[], waiver=w, as_of=BEFORE)
row("V0", "setup: a valid waiver closes the waived S1 finding (status closed, waiver id recorded, no revision)",
    codes == [] and closed.status == "closed" and closed.waiver_id == "wvr-m05r2" and closed.closed_at_revision == "", {"codes": codes, "waiver_id": closed.waiver_id})
a, b = current(closed, R1, w, BEFORE), current(closed, R2, w, BEFORE); ro = reopen(closed, w, BEFORE)
row("V1", "root finding: while the waiver is valid the closure is current at any revision and reopen_finding refuses (WAIVER_GOVERNS)",
    a == (True, []) and b == (True, []) and ro[1] == ["WAIVER_GOVERNS"] and ro[0].status == "closed", {"cur": [a, b], "reopen": ro[1]})
c = current(closed, R2, w, AFTER); ro2 = reopen(closed, w, AFTER)
row("V2", "after the waiver expires the closure is not current, and reopen_finding reopens it (status open, waiver id cleared)",
    c[0] is False and ro2[1] == [] and ro2[0].status == "open" and not ro2[0].waiver_id, {"cur_after_expiry": c, "reopen": [ro2[1], ro2[0].status, ro2[0].waiver_id], "api_takes_waiver_and_as_of": TAKES})
for st in ("rejected", "expired"):
    wr = wvr(status=st); c2 = current(closed, R2, wr, BEFORE); r2 = reopen(closed, wr, BEFORE)
    row("V3-" + st, "waiver record now %s: closure not current and reopen allowed" % st, c2[0] is False and r2[1] == [] and r2[0].status == "open",
        {"cur": c2, "reopen": r2[1]})
other = wvr(waiver_id="wvr-other"); c3 = current(closed, R2, other, BEFORE); r3 = reopen(closed, other, BEFORE)
row("V4", "a different waiver record (another id) neither keeps the closure current nor reopens it by itself", c3[0] is False and r3[1] != [] and r3[0].status == "closed",
    {"cur": c3, "reopen": r3[1]})
if TAKES:
    c4 = q.closure_is_current(closed, R2); r4 = q.reopen_finding(closed, reason="no waiver record given", current_revision=R2, reopened_by_role="release-manager")
    row("V5", "no waiver record supplied: not reported current (expiry cannot be checked) and not reopened (the waiver may still govern)",
        c4[0] is False and r4[1] != [] and r4[0].status == "closed", {"cur": c4, "reopen": r4[1]})
else:
    row("V5", "no waiver record supplied: not reported current and not reopened (API has no waiver parameter)", False, {"api_takes_waiver_and_as_of": False, "cur_without_record": q.closure_is_current(closed, R2)})
# regressions on non-waiver closures
nc, ncodes = q.close_finding(fnd(), closer_role="code-reviewer", independent_evidence=["re-tested at r1: token gone"], subject_revision=R1, verified_revision=R1)
s1, s2 = current(nc, R1), current(nc, R2); rr = reopen(nc)
row("V6", "non-waiver closure: current at its revision, STALE_CLOSURE at another, reopen works", ncodes == [] and s1 == (True, []) and s2 == (False, ["STALE_CLOSURE"]) and rr[1] == [] and rr[0].status == "open",
    {"cur": [s1, s2], "reopen": rr[1]})
ub = fnd(status="closed"); ub.closed_at_revision = ""; ub.waiver_id = ""
row("V7", "closed without revision or waiver: UNBOUND_CLOSURE", current(ub, R1) == (False, ["UNBOUND_CLOSURE"]), {"cur": current(ub, R1)})
bad, bc = q.close_finding(fnd(status="waived"), closer_role="release-manager", independent_evidence=[], waiver=wvr(finding_id="fnd-other"), as_of=BEFORE)
row("V8", "control: closing with a waiver for another finding is refused", bc and bad.status == "waived", {"codes": bc})
doc = (REPO / "employees/quality-security/assurance/ASSURANCE.md").read_text()
row("V9", "ASSURANCE.md says how closure_is_current and reopen_finding treat an expired waiver", "expired" in doc[doc.find("closure_is_current"):doc.find("closure_is_current") + 1600] and "reopen" in doc,
    {"mentions": [s for s in ("expired", "expires", "WAIVER_EXPIRED") if s in doc]})
json.dump({"python": sys.version.split()[0], "api_takes_waiver_and_as_of": TAKES, "rows": ROWS}, open(OUT, "w"), indent=1, default=str)
print("M05R2 PROBE %d/%d" % (sum(r["pass"] for r in ROWS), len(ROWS)))
