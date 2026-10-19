#!/usr/bin/env python3
"""M14 r2 negative-transaction oracle (Grok self-validation, not independent review; black box). Expectations come from
cash-revenue-reconciliation.md ("Negative transactions are challenged"): per invoice, refunds applied above payments
applied -> over_refunded (paid, refunded, excess); credit notes above the invoice amount -> over_credited (invoice amount,
credit notes, excess); equal amounts not challenged; totals over every included row known by as_of, period end ignored;
exit 1 when any exception. Books are generated here.
v2 (disclosed): N19 added after the v1 teeth run left r2_reason_renamed alive: the doc's exact reason values. Usage: PY m14r2_negative.py REPO OUT.json [--tool TOOL.py]"""
import json, random, shutil, sys, tempfile
from decimal import Decimal as D
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); from m14r2_common import *
REPO = Path(sys.argv[1]).resolve(); OUT = sys.argv[2]
TOOL = Path(sys.argv[sys.argv.index("--tool") + 1]).resolve() if "--tool" in sys.argv else REPO / "employees/leadership/cfo/cash_revenue_reconcile.py"
TOP = Path(tempfile.mkdtemp(prefix="m14r2n-", dir="/tmp")); ROWS = []; K = [0]
def c2(x): return str(D(x).quantize(D("0.01")))
def row(rid, ok, det, obs=False): ROWS.append({"id": rid, "kind": "OBS" if obs else "core", "result": "OBS" if obs else ("PASS" if ok else "FAIL"), "detail": det})
def expect(I, P, C):
    """Clean, included rows only (callers pass only rows the doc says are included)."""
    orf, ocr = [], []
    for i in I:
        paid = sum((D(p["amount"]) for p in P if p["invoice_id"] == i["invoice_id"]), D(0))
        ref = sum((D(c["amount"]) for c in C if c["invoice_id"] == i["invoice_id"] and c["kind"] == "refund"), D(0))
        cn = sum((D(c["amount"]) for c in C if c["invoice_id"] == i["invoice_id"] and c["kind"] == "credit_note"), D(0))
        if ref > paid: orf.append({"id": i["invoice_id"], "currency": i["currency"], "paid": c2(paid), "refunded": c2(ref), "excess": c2(ref - paid)})
        if cn > D(i["amount"]): ocr.append({"id": i["invoice_id"], "currency": i["currency"], "invoice_amount": c2(i["amount"]), "credit_notes": c2(cn), "excess": c2(cn - D(i["amount"]))})
    return sorted(orf, key=lambda x: x["id"]), sorted(ocr, key=lambda x: x["id"])
def go(I, P, C):
    K[0] += 1; rc, rep, cp = run(TOOL, write(TOP / ("b%03d" % K[0]), I, P, C)); ex = (rep or {}).get("exceptions", {})
    return rc, sorted(ex.get("over_refunded", []) or [], key=lambda x: x.get("id", "")), sorted(ex.get("over_credited", []) or [], key=lambda x: x.get("id", "")), rep
def case(rid, I, P, C, want_rc=None, exp=None, note=None):
    rc, o1, o2, rep = go(I, P, C); e1, e2 = exp if exp else expect(I, P, C)
    w = want_rc if want_rc is not None else (1 if (e1 or e2) else 0)
    row(rid, rc == w and o1 == e1 and o2 == e2, {"rc": rc, "want_rc": w, "over_refunded": o1, "want_refunded": e1, "over_credited": o2, "want_credited": e2, "note": note}); return rep
case("N01_over_refund_only", [inv("A", "100.00")], [pay("p1", "A", "100.00")], [cr("r1", "A", "refund", "150.00")])
case("N02_over_credit_unpaid", [inv("B", "100.00")], [], [cr("n1", "B", "credit_note", "130.00")])
case("N03_equal_amounts_not_challenged", [inv("A", "100.00"), inv("B", "100.00")], [pay("p1", "A", "100.00")], [cr("r1", "A", "refund", "100.00"), cr("n1", "B", "credit_note", "100.00")])
case("N04_separate_not_combined", [inv("A", "100.00"), inv("B", "100.00")], [pay("p1", "A", "100.00")],
     [cr("n0", "B", "credit_note", "80.00"), cr("r1", "A", "refund", "60.00"), cr("n1", "A", "credit_note", "60.00")], note="refund+credit 120 > paid 100 on A, and an ordinary credit note on unpaid B: neither is challenged")
case("N05_refund_before_payment_after_period_end", [inv("A", "100.00")], [pay("p1", "A", "100.00", at="2026-08-03T00:00:00Z")], [cr("r1", "A", "refund", "100.00", at="2026-07-20T00:00:00Z")])
case("N06_refund_after_period_end_counts", [inv("A", "100.00")], [pay("p1", "A", "100.00")], [cr("r1", "A", "refund", "70.00"), cr("r2", "A", "refund", "40.00", at="2026-08-04T00:00:00Z")])
case("N07_cents_many_rows", [inv("A", "99.99")], [pay("p%d" % k, "A", "33.33") for k in range(3)], [cr("r1", "A", "refund", "50.00"), cr("r2", "A", "refund", "50.00")])
case("N08_per_invoice_no_netting", [inv("A", "100.00"), inv("B", "100.00")], [pay("p1", "A", "100.00"), pay("p2", "B", "100.00")], [cr("r1", "A", "refund", "150.00")])
# N09: a late refund (loaded after as_of) is excluded, so not over; a late payment leaves its refund over (documented limit)
rc, o1, o2, rep = go([inv("A", "100.00"), inv("B", "100.00")], [pay("p1", "A", "100.00"), pay("p2", "B", "100.00", loaded="2026-08-07T00:00:00Z")],
                     [cr("r1", "A", "refund", "150.00", loaded="2026-08-07T00:00:00Z"), cr("r2", "B", "refund", "100.00")])
want = [{"id": "B", "currency": "USD", "paid": "0.00", "refunded": "100.00", "excess": "100.00"}]
row("N09_late_rows_excluded_from_totals", rc == 1 and o1 == want and o2 == [] and len((rep or {}).get("exceptions", {}).get("late", [])) == 2, {"rc": rc, "over_refunded": o1, "want": want, "late": len((rep or {}).get("exceptions", {}).get("late", []))})
# N10: a refund in another currency stays unapplied (currency_mismatch) and is not counted against the invoice
rc, o1, o2, rep = go([inv("A", "100.00")], [pay("p1", "A", "100.00")], [cr("r1", "A", "refund", "60.00"), cr("r2", "A", "refund", "60.00", cur="EUR")])
un = [u.get("reason") for u in (rep or {}).get("exceptions", {}).get("unapplied", [])]
row("N10_currency_mismatch_refund_not_counted", rc == 1 and o1 == [] and "currency_mismatch" in un, {"rc": rc, "over_refunded": o1, "unapplied_reasons": un})
# N11: a refund id with two versions is excluded (both), so not counted; N12: an exact repeat counts once
rc, o1, o2, rep = go([inv("A", "100.00")], [pay("p1", "A", "100.00")], [cr("r1", "A", "refund", "150.00"), cr("r1", "A", "refund", "90.00")])
row("N11_conflicting_refund_excluded", rc == 1 and o1 == [] and len((rep or {}).get("exceptions", {}).get("conflicting_versions", [])) >= 1, {"rc": rc, "over_refunded": o1})
case("N12_exact_repeat_counts_once", [inv("A", "100.00")], [pay("p1", "A", "100.00")], [cr("r1", "A", "refund", "100.00"), cr("r1", "A", "refund", "100.00")], exp=([], []))
# N13: refund on a void invoice is unapplied (invoice_void), never over_refunded; credit note on a void invoice not over_credited
rc, o1, o2, rep = go([inv("V", "100.00", status="void")], [], [cr("r1", "V", "refund", "50.00"), cr("n1", "V", "credit_note", "500.00")])
row("N13_void_invoice_not_challenged", rc == 1 and o1 == [] and o2 == [], {"rc": rc, "over_refunded": o1, "over_credited": o2, "unapplied": [u.get("reason") for u in (rep or {}).get("exceptions", {}).get("unapplied", [])], "unlinked": [u.get("reason") for u in (rep or {}).get("exceptions", {}).get("unlinked_credits", [])]})
# N14: both on one invoice, plus the arithmetic still booked (controls close)
rep = case("N14_both_on_one_invoice", [inv("A", "100.00")], [pay("p1", "A", "100.00")], [cr("r1", "A", "refund", "120.00"), cr("n1", "A", "credit_note", "110.00")])
row("O15_controls_and_revenue_as_booked", True, {"controls": (rep or {}).get("controls"), "currencies": (rep or {}).get("currencies")}, obs=True)
# N16: property test, 40 random clean books (several invoices, payments, refunds, credit notes, dates on both sides of period end)
rng = random.Random(1419); fails = []
for k in range(40):
    I, P, C = [], [], []
    for j in range(rng.randint(1, 5)):
        iid = "I%d" % j; amt = D(rng.randint(1000, 50000)) / 100; I.append(inv(iid, c2(amt)))
        for q in range(rng.randint(0, 3)): P.append(pay("P%d_%d" % (j, q), iid, c2(D(rng.randint(100, 30000)) / 100), at=rng.choice(["2026-07-12T00:00:00Z", "2026-08-02T00:00:00Z"])))
        for q in range(rng.randint(0, 2)): C.append(cr("R%d_%d" % (j, q), iid, "refund", c2(D(rng.randint(100, 30000)) / 100), at=rng.choice(["2026-07-20T00:00:00Z", "2026-08-03T00:00:00Z"])))
        for q in range(rng.randint(0, 2)): C.append(cr("N%d_%d" % (j, q), iid, "credit_note", c2(D(rng.randint(100, 40000)) / 100), at=rng.choice(["2026-07-21T00:00:00Z", "2026-08-04T00:00:00Z"])))
        if rng.random() < 0.2 and P: x = rng.choice([p for p in P if p["invoice_id"] == iid] or [None]); x and C.append(cr("E%d" % j, iid, "refund", x["amount"]))
    rc, o1, o2, rep = go(I, P, C); e1, e2 = expect(I, P, C); w = 1 if (e1 or e2) else 0
    if not (o1 == e1 and o2 == e2 and rc == w): fails.append({"case": k, "rc": rc, "want_rc": w, "got": [o1, o2], "want": [e1, e2]})
row("N16_random_books_property", not fails, {"cases": 40, "fails": fails[:2]})
# OBS: a payment dated after as_of but loaded before it; a refund before any payment with none arriving (documented limit)
rc, o1, o2, rep = go([inv("A", "100.00")], [pay("p1", "A", "100.00", at="2026-08-10T00:00:00Z")], [cr("r1", "A", "refund", "100.00")])
row("O17_payment_dated_after_as_of_loaded_before", True, {"rc": rc, "over_refunded": o1}, obs=True)
rc, o1, o2, rep = go([inv("A", "100.00", deliv="")], [], [cr("n1", "A", "credit_note", "100.01", at="2026-07-02T12:00:00Z")])
row("O18_undelivered_over_credit_by_a_cent", True, {"rc": rc, "over_credited": o2}, obs=True)
# N19 (v2): exact reason values as the doc lists them, and every emitted reason is a backticked doc name
doc = (REPO / "employees/leadership/cfo/cash-revenue-reconciliation.md").read_text()
rc, o1, o2, rep = go([inv("A", "100.00"), inv("C", "100.00", issued="2026-07-20T00:00:00Z", deliv="2026-07-21T00:00:00Z")],
                     [pay("p1", "ZZ", "10.00"), pay("p2", "", "10.00"), pay("p3", "A", "10.00", cur="EUR")], [cr("n1", "C", "credit_note", "5.00", at="2026-07-10T00:00:00Z")])
ex = (rep or {}).get("exceptions", {}); ur = sorted(u.get("reason") for u in ex.get("unapplied", [])); cr_ = sorted(u.get("reason") for u in ex.get("unlinked_credits", []))
want_u = sorted(["unknown_invoice", "no_invoice_reference", "currency_mismatch"]); want_c = ["credit_note_before_invoice"]
row("N19_exact_reason_values", rc == 1 and ur == want_u and cr_ == want_c and all(("`%s`" % r) in doc for r in ur + cr_), {"rc": rc, "unapplied": ur, "want_unapplied": want_u, "unlinked": cr_, "want_unlinked": want_c})
shutil.rmtree(TOP, ignore_errors=True)
json.dump(ROWS, open(OUT, "w"), indent=1, sort_keys=True)
for x in ROWS: print(x["id"], x["result"], json.dumps(x["detail"], sort_keys=True)[:260])
c = [x for x in ROWS if x["kind"] == "core"]; print("M14R2 NEGATIVE %d/%d core PASS" % (sum(x["result"] == "PASS" for x in c), len(c)))
