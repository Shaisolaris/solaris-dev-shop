#!/usr/bin/env python3
"""M14 oracle (Grok self-validation, written by Grok, black box). Expectations come from
cash-revenue-reconciliation.md and the G14 README, never from the tool's output. Books are generated here and
valued by an independent as-of journal (Decimal). Usage: PY m14_oracle.py REPO [--tool TOOL.py] OUT.json.
Core rows (K*) score; OBS rows record only.
v2 harness fixes (disclosed): K06 accepts any reason naming the missing reference (doc wording is "no reference",
the tool says no_invoice_reference); K07b expectation corrected by hand (900 + 15 paid - 120 refunded on 900 billed
leaves AR 105.00 owed, not a customer credit). Expectations still come from the docs only.
v3 (disclosed): K15 to K19 added after the v2 teeth run showed oracle blind spots (void, missing value, excluded
invoice, period end boundary, bank cash out and one-sided ledger currency); K20 records doc-silent refusals."""
import csv, io, json, random, shutil, subprocess, sys, tempfile
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
from pathlib import Path
REPO = Path(sys.argv[1]).resolve(); a = sys.argv[2:]
TOOL = REPO / "employees/leadership/cfo/cash_revenue_reconcile.py"
if a and a[0] == "--tool": TOOL = Path(a[1]).resolve(); a = a[2:]
OUT = a[0]; PY = sys.executable; ENV = {"PATH": "/usr/bin:/bin", "HOME": "/tmp", "PYTHONDONTWRITEBYTECODE": "1", "LC_ALL": "C"}
TOP = Path(tempfile.mkdtemp(prefix="m14top-", dir="/tmp")).resolve(); rows = []
def row(rid, ok, detail, obs=False):
    rows.append({"id": rid, "kind": "OBS" if obs else "core", "result": "OBS" if obs else ("PASS" if ok else "FAIL"), "detail": detail})
S = datetime(2026, 7, 1, tzinfo=timezone.utc); E = datetime(2026, 8, 1, tzinfo=timezone.utc); ASOF = datetime(2026, 8, 6, tzinfo=timezone.utc)
def iso(t): return t.strftime("%Y-%m-%dT%H:%M:%SZ") if t else ""
def c2(x): return str(D(x).quantize(D("0.01")))
IH = ["invoice_id", "customer_id", "currency", "amount", "issued_at", "delivered_at", "status", "loaded_at"]
PH = ["payment_id", "invoice_id", "currency", "amount", "received_at", "loaded_at"]
CH = ["credit_id", "invoice_id", "kind", "currency", "amount", "issued_at", "loaded_at"]
def write(d, inv, pay, cr, bank=None, extra=None):
    d.mkdir(parents=True, exist_ok=True)
    for name, h, rs in (("invoices.csv", IH, inv), ("payments.csv", PH, pay), ("credits.csv", CH, cr)):
        b = io.StringIO(); w = csv.writer(b, lineterminator="\n"); w.writerow(h); [w.writerow([r.get(k, "") for k in h]) for r in rs]; (d / name).write_text(b.getvalue())
    pk = {"schema": "solaris.cash-revenue/1", "timezone": "UTC", "period": {"start": iso(S), "end": iso(E)}, "as_of": iso(ASOF),
          "invoices": {"file": "invoices.csv"}, "payments": {"file": "payments.csv"}, "credits": {"file": "credits.csv"}}
    if bank is not None:
        b = io.StringIO(); w = csv.writer(b, lineterminator="\n"); w.writerow(["currency", "cash_in", "cash_out"]); [w.writerow(x) for x in bank]; (d / "bank.csv").write_text(b.getvalue()); pk["bank"] = {"file": "bank.csv"}
    if extra: pk.update(extra)
    (d / "package.json").write_text(json.dumps(pk)); return d / "package.json"
def run(p, *extra):
    cp = subprocess.run([PY, str(TOOL), "reconcile", str(p), "--json"] + list(extra), cwd=p.parent, env=ENV, capture_output=True, text=True, timeout=300)
    try: rep = json.loads(cp.stdout)
    except Exception: rep = None
    return cp.returncode, rep, cp
def T(s): return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc) if s else None
def journal(inv, pay, cr):
    """Independent as-of journal for clean books (all rows loaded, valid, linked, same currency)."""
    I = {r["invoice_id"]: r for r in inv}; cur = sorted({r["currency"].upper() for r in inv} | {r["currency"].upper() for r in pay})
    out = {c: {} for c in cur}
    def bal(c, t):
        ar = deferred = unbilled = unapplied = D(0)
        for i in I.values():
            if i["currency"].upper() != c or i["status"] != "issued": continue
            amt = D(i["amount"]); iss = T(i["issued_at"]) < t; dl = T(i["delivered_at"]); dlv = dl is not None and dl < t
            cn = [x for x in cr if x["invoice_id"] == i["invoice_id"] and x["kind"] == "credit_note" and T(x["issued_at"]) < t]
            pre = sum((D(x["amount"]) for x in cn if dl is None or T(x["issued_at"]) < dl), D(0))
            if iss:
                ar += amt - sum((D(x["amount"]) for x in cn), D(0))
                if not dlv: deferred += amt - pre
            elif dlv: unbilled += amt - pre
        for p in pay:
            if p["currency"].upper() != c or T(p["received_at"]) >= t: continue
            if p["invoice_id"] in I and I[p["invoice_id"]]["currency"].upper() == c and I[p["invoice_id"]]["status"] == "issued": ar -= D(p["amount"])
            else: unapplied += D(p["amount"])
        for x in cr:
            if x["kind"] == "refund" and x["currency"].upper() == c and T(x["issued_at"]) < t: ar += D(x["amount"])
        return {"ar_net": c2(ar), "deferred": c2(deferred), "unbilled": c2(unbilled), "unapplied": c2(unapplied)}
    for c in cur:
        o = out[c]; inper = lambda s: s is not None and S <= s < E
        o["billed"] = c2(sum((D(i["amount"]) for i in I.values() if i["currency"].upper() == c and i["status"] == "issued" and inper(T(i["issued_at"]))), D(0)))
        o["credit_notes"] = c2(sum((D(x["amount"]) for x in cr if x["kind"] == "credit_note" and x["currency"].upper() == c and inper(T(x["issued_at"]))), D(0)))
        rev = D(0)
        for i in I.values():
            if i["currency"].upper() != c or i["status"] != "issued": continue
            dl = T(i["delivered_at"]); cn = [x for x in cr if x["invoice_id"] == i["invoice_id"] and x["kind"] == "credit_note"]
            if inper(dl): rev += D(i["amount"]) - sum((D(x["amount"]) for x in cn if T(x["issued_at"]) < dl), D(0))
            rev -= sum((D(x["amount"]) for x in cn if dl is not None and T(x["issued_at"]) >= dl and inper(T(x["issued_at"]))), D(0))
        o["recognized_revenue"] = c2(rev)
        o["cash_received"] = c2(sum((D(p["amount"]) for p in pay if p["currency"].upper() == c and inper(T(p["received_at"]))), D(0)))
        o["refunds_paid"] = c2(sum((D(x["amount"]) for x in cr if x["kind"] == "refund" and x["currency"].upper() == c and inper(T(x["issued_at"]))), D(0)))
        o["net_cash"] = c2(D(o["cash_received"]) - D(o["refunds_paid"])); o["opening"] = bal(c, S); o["closing"] = bal(c, E)
    return out
def compare(rep, exp):
    diffs = []
    for c, e in exp.items():
        g = ((rep or {}).get("currencies") or {}).get(c)
        if g is None: diffs.append((c, "missing")); continue
        for k, v in e.items():
            if isinstance(v, dict):
                for kk, vv in v.items():
                    if (g.get(k) or {}).get(kk) != vv: diffs.append((c, k, kk, (g.get(k) or {}).get(kk), vv))
            elif g.get(k) != v: diffs.append((c, k, g.get(k), v))
    extra = sorted(set(((rep or {}).get("currencies") or {})) - set(exp))
    if extra: diffs.append(("extra currencies", extra))
    return diffs
def book(seed, n=60, curs=("USD", "EUR", "JPY")):
    r = random.Random(seed); inv, pay, cr = [], [], []; k = 0
    for i in range(n):
        c = r.choice(curs); amt = D(r.randint(1, 900) * 100 if c == "JPY" else r.randint(1000, 200000)) / (1 if c == "JPY" else 100)
        iss = S + timedelta(days=r.randint(-25, 33), hours=r.randint(0, 23)); iss = min(iss, ASOF - timedelta(days=1, hours=2))
        mode = r.random(); dl = None if mode < 0.12 else (iss - timedelta(days=r.randint(1, 4)) if mode < 0.25 else iss + timedelta(days=r.randint(0, 20), hours=1))
        if dl and dl >= ASOF: dl = None
        iid = "N%03d" % i; inv.append({"invoice_id": iid, "customer_id": "k%d" % r.randint(1, 15), "currency": c, "amount": str(amt), "issued_at": iso(iss), "delivered_at": iso(dl), "status": "issued", "loaded_at": iso(iss + timedelta(hours=1))})
        left = amt
        if r.random() < 0.3:
            cn = (left * D(r.randint(5, 30)) / 100).quantize(D("1") if c == "JPY" else D("0.01")); t = iss + timedelta(days=r.randint(0, 12), hours=2)
            if cn > 0 and t < ASOF - timedelta(hours=2): cr.append({"credit_id": "C%03d" % i, "invoice_id": iid, "kind": "credit_note", "currency": c, "amount": str(cn), "issued_at": iso(t), "loaded_at": iso(t + timedelta(hours=1))}); left -= cn
        paid = D(0)
        for j in range(r.randint(0, 2)):
            if left <= 0: break
            pa = left if r.random() < 0.6 else (left / 2).quantize(D("1") if c == "JPY" else D("0.01")); t = iss + timedelta(days=r.randint(0, 35), hours=3)
            if pa <= 0 or t >= ASOF - timedelta(hours=2): continue
            pay.append({"payment_id": "P%03d%d" % (i, j), "invoice_id": iid, "currency": c, "amount": str(pa), "received_at": iso(t), "loaded_at": iso(t + timedelta(hours=1))}); left -= pa; paid += pa
        if paid > 0 and r.random() < 0.2:
            rf = (paid / 4).quantize(D("1") if c == "JPY" else D("0.01")); t = S + timedelta(days=r.randint(0, 34), hours=5)
            if rf > 0 and t < ASOF - timedelta(hours=2): cr.append({"credit_id": "R%03d" % i, "invoice_id": iid, "kind": "refund", "currency": c, "amount": str(rf), "issued_at": iso(t), "loaded_at": iso(t + timedelta(hours=1))})
    return inv, pay, cr
def bank_for(exp): return [[c, e["cash_received"], e["refunds_paid"]] for c, e in sorted(exp.items())]
def k01():  # clean control: delivered, paid in full, bank matches -> exit 0, exact values
    inv = [{"invoice_id": "A1", "customer_id": "x", "currency": "CHF", "amount": "1200.40", "issued_at": "2026-07-03T09:00:00Z", "delivered_at": "2026-07-03T10:00:00Z", "status": "issued", "loaded_at": "2026-07-03T11:00:00Z"},
           {"invoice_id": "A2", "customer_id": "y", "currency": "CHF", "amount": "99.60", "issued_at": "2026-07-09T09:00:00Z", "delivered_at": "2026-07-10T10:00:00Z", "status": "issued", "loaded_at": "2026-07-09T11:00:00Z"}]
    pay = [{"payment_id": "B1", "invoice_id": "A1", "currency": "CHF", "amount": "1200.40", "received_at": "2026-07-20T09:00:00Z", "loaded_at": "2026-07-20T10:00:00Z"},
           {"payment_id": "B2", "invoice_id": "A2", "currency": "CHF", "amount": "99.60", "received_at": "2026-07-21T09:00:00Z", "loaded_at": "2026-07-21T10:00:00Z"}]
    exp = journal(inv, pay, []); p = write(TOP / "k01", inv, pay, [], bank_for(exp)); rc, rep, _ = run(p); df = compare(rep, exp)
    row("K01_clean_control_exit0_exact", rc == 0 and not df and exp["CHF"]["recognized_revenue"] == "1300.00", {"rc": rc, "diffs": df})
    return inv, pay
def k02():  # three seeded books, three currencies incl. zero-decimal JPY, against the journal; bank matches -> exit 0
    res = {}
    for seed in (11, 12, 13):
        inv, pay, cr = book(seed); exp = journal(inv, pay, cr); p = write(TOP / ("k02-%d" % seed), inv, pay, cr, bank_for(exp)); rc, rep, cp = run(p)
        ex = {k: len(v) for k, v in ((rep or {}).get("exceptions") or {}).items() if v}
        res[seed] = {"rc": rc, "diffs": compare(rep, exp)[:6], "exceptions": ex, "stderr": cp.stderr[-200:]}
    # exceptions allowed only for undelivered invoices (generated) ; rc 1 then
    ok = all(not v["diffs"] and set(v["exceptions"]) <= {"undelivered"} and v["rc"] == (1 if v["exceptions"] else 0) for v in res.values())
    row("K02_seeded_books_equal_journal", ok, res)
def k03():  # settlement timing: payment received before the period settles opening AR; one received after the period end (before as_of) is not period cash
    inv = [{"invoice_id": "S1", "customer_id": "x", "currency": "USD", "amount": "500.00", "issued_at": "2026-06-20T09:00:00Z", "delivered_at": "2026-06-21T09:00:00Z", "status": "issued", "loaded_at": "2026-06-20T10:00:00Z"},
           {"invoice_id": "S2", "customer_id": "y", "currency": "USD", "amount": "800.00", "issued_at": "2026-07-25T09:00:00Z", "delivered_at": "2026-07-26T09:00:00Z", "status": "issued", "loaded_at": "2026-07-25T10:00:00Z"}]
    pay = [{"payment_id": "Q1", "invoice_id": "S1", "currency": "USD", "amount": "200.00", "received_at": "2026-06-30T23:59:59Z", "loaded_at": "2026-07-01T01:00:00Z"},
           {"payment_id": "Q2", "invoice_id": "S1", "currency": "USD", "amount": "300.00", "received_at": "2026-07-01T00:00:00Z", "loaded_at": "2026-07-01T01:00:00Z"},
           {"payment_id": "Q3", "invoice_id": "S2", "currency": "USD", "amount": "800.00", "received_at": "2026-08-01T00:00:00Z", "loaded_at": "2026-08-01T02:00:00Z"}]
    exp = journal(inv, pay, []); p = write(TOP / "k03", inv, pay, [], [["USD", "300.00", "0.00"]]); rc, rep, _ = run(p); df = compare(rep, exp)
    want = {"open": "300.00", "cash": "300.00", "close": "800.00"}
    got = {"open": exp["USD"]["opening"]["ar_net"], "cash": exp["USD"]["cash_received"], "close": exp["USD"]["closing"]["ar_net"]}
    row("K03_settlement_timing_period_edges", rc == 0 and not df and got == want, {"rc": rc, "diffs": df, "journal": got})
def k04():  # negative and duplicate transactions
    inv = [{"invoice_id": "D1", "customer_id": "x", "currency": "USD", "amount": "400.00", "issued_at": "2026-07-02T09:00:00Z", "delivered_at": "2026-07-02T10:00:00Z", "status": "issued", "loaded_at": "2026-07-02T11:00:00Z"}]
    base = {"invoice_id": "D1", "currency": "USD", "received_at": "2026-07-05T09:00:00Z", "loaded_at": "2026-07-05T10:00:00Z"}
    pay = [dict(base, payment_id="N1", amount="-50.00"), dict(base, payment_id="E1", amount="100.00"), dict(base, payment_id="E1", amount="100.00", loaded_at="2026-07-06T10:00:00Z"),
           dict(base, payment_id="V1", amount="60.00"), dict(base, payment_id="V1", amount="70.00"), dict(base, payment_id="T1", amount="100.00"), dict(base, payment_id="T2", amount="100.00")]
    cr = [{"credit_id": "Z1", "invoice_id": "D1", "kind": "credit_note", "currency": "USD", "amount": "0.00", "issued_at": "2026-07-06T09:00:00Z", "loaded_at": "2026-07-06T10:00:00Z"}]
    p = write(TOP / "k04", inv, pay, cr); rc, rep, _ = run(p); u = (rep or {}).get("currencies", {}).get("USD", {}); ex = (rep or {}).get("exceptions", {})
    rej = sorted(x.get("id") or str(x.get("line")) for x in ex.get("rejected", [])); conf = [x.get("id") for x in ex.get("conflicting_versions", [])]
    ok = rc == 1 and u.get("cash_received") == "300.00" and u.get("closing", {}).get("ar_net") == "100.00" and len(ex.get("rejected", [])) == 2 and conf == ["V1"] and (rep or {}).get("counts", {}).get("exact_duplicates_collapsed") == 1
    row("K04_negative_and_duplicate_transactions", ok, {"rc": rc, "cash": u.get("cash_received"), "closing_ar": u.get("closing", {}).get("ar_net"), "rejected": ex.get("rejected"), "conflicting": conf, "counts": (rep or {}).get("counts")})
def k05():  # mixed currencies: same amounts in two currencies stay apart; currency mismatch stays unapplied in its own currency; lower-case code
    inv = [{"invoice_id": "M%d" % k, "customer_id": "x", "currency": c, "amount": "250.00", "issued_at": "2026-07-04T09:00:00Z", "delivered_at": "2026-07-04T10:00:00Z", "status": "issued", "loaded_at": "2026-07-04T11:00:00Z"} for k, c in ((1, "usd"), (2, "EUR"), (3, "GBP"))]
    pay = [{"payment_id": "MP1", "invoice_id": "M1", "currency": "USD", "amount": "250.00", "received_at": "2026-07-08T09:00:00Z", "loaded_at": "2026-07-08T10:00:00Z"},
           {"payment_id": "MP2", "invoice_id": "M2", "currency": "USD", "amount": "250.00", "received_at": "2026-07-08T09:00:00Z", "loaded_at": "2026-07-08T10:00:00Z"}]
    p = write(TOP / "k05", inv, pay, []); rc, rep, _ = run(p); cu = (rep or {}).get("currencies", {})
    un = [(x.get("id"), x.get("currency"), x.get("reason")) for x in (rep or {}).get("exceptions", {}).get("unapplied", [])]
    ok = rc == 1 and sorted(cu) == ["EUR", "GBP", "USD"] and cu["USD"]["cash_received"] == "500.00" and cu["USD"]["closing"]["unapplied"] == "250.00" and cu["EUR"]["closing"]["ar_net"] == "250.00" \
        and cu["EUR"]["cash_received"] == "0.00" and cu["USD"]["recognized_revenue"] == "250.00" and un == [("MP2", "USD", "currency_mismatch")]
    row("K05_mixed_currencies_not_combined", ok, {"rc": rc, "currencies": sorted(cu), "usd": {k: cu.get("USD", {}).get(k) for k in ("cash_received", "recognized_revenue")}, "unapplied": un})
def k06():  # missing documents: no reference, unknown invoice, credit note on unknown invoice, credit note before its invoice, no delivery, no loaded_at
    inv = [{"invoice_id": "X1", "customer_id": "x", "currency": "USD", "amount": "300.00", "issued_at": "2026-07-10T09:00:00Z", "delivered_at": "", "status": "issued", "loaded_at": "2026-07-10T10:00:00Z"},
           {"invoice_id": "X2", "customer_id": "x", "currency": "USD", "amount": "100.00", "issued_at": "2026-07-10T09:00:00Z", "delivered_at": "2026-07-10T09:30:00Z", "status": "issued", "loaded_at": ""}]
    pay = [{"payment_id": "XP1", "invoice_id": "", "currency": "USD", "amount": "40.00", "received_at": "2026-07-11T09:00:00Z", "loaded_at": "2026-07-11T10:00:00Z"},
           {"payment_id": "XP2", "invoice_id": "NOPE", "currency": "USD", "amount": "60.00", "received_at": "2026-07-11T09:00:00Z", "loaded_at": "2026-07-11T10:00:00Z"}]
    cr = [{"credit_id": "XC1", "invoice_id": "NOPE", "kind": "credit_note", "currency": "USD", "amount": "10.00", "issued_at": "2026-07-12T09:00:00Z", "loaded_at": "2026-07-12T10:00:00Z"},
          {"credit_id": "XC2", "invoice_id": "X1", "kind": "credit_note", "currency": "USD", "amount": "10.00", "issued_at": "2026-07-09T09:00:00Z", "loaded_at": "2026-07-12T10:00:00Z"}]
    p = write(TOP / "k06", inv, pay, cr); rc, rep, _ = run(p); ex = (rep or {}).get("exceptions", {}); u = (rep or {}).get("currencies", {}).get("USD", {})
    un = sorted((x.get("id"), x.get("reason")) for x in ex.get("unapplied", [])); ul = sorted(x.get("id") for x in ex.get("unlinked_credits", []))
    nl = [x.get("id") for x in ex.get("no_loaded_at", [])]; ud = [x.get("id") for x in ex.get("undelivered", [])]
    ok = rc == 1 and [i for i, _ in un] == ["XP1", "XP2"] and "reference" in un[0][1] and "unknown" in un[1][1] and ul == ["XC1", "XC2"] and nl == ["X2"] and ud == ["X1"] and \
        u.get("recognized_revenue") == "0.00" and u.get("closing", {}).get("unapplied") == "100.00" and u.get("closing", {}).get("deferred") == "300.00"
    row("K06_missing_documents_explicit", ok, {"rc": rc, "unapplied": un, "unlinked": ul, "no_loaded_at": nl, "undelivered": ud, "usd": {k: u.get(k) for k in ("recognized_revenue", "closing")}})
def k07():  # late rows and refunds: late payment excluded and named; bank including it shows a control difference; refund moves cash and AR only
    inv = [{"invoice_id": "L1", "customer_id": "x", "currency": "EUR", "amount": "900.00", "issued_at": "2026-07-01T09:00:00Z", "delivered_at": "2026-07-02T09:00:00Z", "status": "issued", "loaded_at": "2026-07-01T10:00:00Z"}]
    pay = [{"payment_id": "LP1", "invoice_id": "L1", "currency": "EUR", "amount": "900.00", "received_at": "2026-07-05T09:00:00Z", "loaded_at": "2026-07-05T10:00:00Z"},
           {"payment_id": "LP2", "invoice_id": "L1", "currency": "EUR", "amount": "15.00", "received_at": "2026-07-30T09:00:00Z", "loaded_at": "2026-08-07T10:00:00Z"}]
    cr = [{"credit_id": "LR1", "invoice_id": "L1", "kind": "refund", "currency": "EUR", "amount": "120.00", "issued_at": "2026-07-20T09:00:00Z", "loaded_at": "2026-07-20T10:00:00Z"}]
    p = write(TOP / "k07", inv, pay, cr, [["EUR", "915.00", "120.00"]]); rc, rep, _ = run(p); u = (rep or {}).get("currencies", {}).get("EUR", {}); ex = (rep or {}).get("exceptions", {})
    ctl = (rep or {}).get("controls", {}).get("EUR", {})
    ok = rc == 1 and [x.get("id") for x in ex.get("late", [])] == ["LP2"] and u.get("cash_received") == "900.00" and u.get("refunds_paid") == "120.00" and u.get("net_cash") == "780.00" \
        and u.get("recognized_revenue") == "900.00" and u.get("closing", {}).get("ar_net") == "120.00" and ctl.get("ok") is False and ctl.get("difference_in") in ("15.00", "-15.00")
    row("K07_late_and_refund", ok, {"rc": rc, "late": ex.get("late"), "eur": {k: u.get(k) for k in ("cash_received", "refunds_paid", "net_cash", "recognized_revenue", "closing")}, "control": ctl})
    p2 = write(TOP / "k07b", inv, pay, cr, [["EUR", "915.00", "120.00"]], extra={"as_of": "2026-08-08T00:00:00Z"}); rc2, rep2, _ = run(p2)
    u2 = (rep2 or {}).get("currencies", {}).get("EUR", {})
    row("K07b_later_cutoff_takes_late_row", rc2 == 0 and u2.get("cash_received") == "915.00" and u2.get("closing", {}).get("ar_net") == "105.00" and u2.get("closing", {}).get("customer_credit") == "0.00", {"rc": rc2, "eur_closing": u2.get("closing"), "cash": u2.get("cash_received")})
def k08():  # credit note after vs before delivery, overpayment to customer credit, delivery before issue = unbilled
    inv = [{"invoice_id": "R1", "customer_id": "x", "currency": "USD", "amount": "1000.00", "issued_at": "2026-07-02T09:00:00Z", "delivered_at": "2026-07-03T09:00:00Z", "status": "issued", "loaded_at": "2026-07-02T10:00:00Z"},
           {"invoice_id": "R2", "customer_id": "y", "currency": "USD", "amount": "600.00", "issued_at": "2026-07-02T09:00:00Z", "delivered_at": "2026-08-03T09:00:00Z", "status": "issued", "loaded_at": "2026-07-02T10:00:00Z"},
           {"invoice_id": "R3", "customer_id": "z", "currency": "USD", "amount": "350.00", "issued_at": "2026-08-02T09:00:00Z", "delivered_at": "2026-07-28T09:00:00Z", "status": "issued", "loaded_at": "2026-08-02T10:00:00Z"}]
    pay = [{"payment_id": "RP1", "invoice_id": "R1", "currency": "USD", "amount": "950.00", "received_at": "2026-07-15T09:00:00Z", "loaded_at": "2026-07-15T10:00:00Z"}]
    cr = [{"credit_id": "RC1", "invoice_id": "R1", "kind": "credit_note", "currency": "USD", "amount": "100.00", "issued_at": "2026-07-10T09:00:00Z", "loaded_at": "2026-07-10T10:00:00Z"},
          {"credit_id": "RC2", "invoice_id": "R2", "kind": "credit_note", "currency": "USD", "amount": "60.00", "issued_at": "2026-07-12T09:00:00Z", "loaded_at": "2026-07-12T10:00:00Z"}]
    p = write(TOP / "k08", inv, pay, cr); rc, rep, _ = run(p); u = (rep or {}).get("currencies", {}).get("USD", {}); cl = u.get("closing", {})
    want = {"recognized_revenue": "1250.00", "credit_notes": "160.00", "billed": "1600.00", "closing": {"ar_net": "490.00", "ar_owed": "540.00", "customer_credit": "50.00", "deferred": "540.00", "unbilled": "350.00", "unapplied": "0.00"}}
    got = {k: u.get(k) for k in ("recognized_revenue", "credit_notes", "billed")}; got["closing"] = cl
    chk = all(x.get("ok") for x in u.get("checks", {}).values()) if u.get("checks") else False
    row("K08_credit_note_timing_overpay_unbilled", rc in (0, 1) and got == want and chk, {"rc": rc, "got": got, "want": want, "checks_ok": chk})
def k09():  # repeated import stable: every row re-delivered (later loaded_at) and shuffled gives the same figures; rerun byte-identical
    inv, pay, cr = book(21, n=40, curs=("USD", "EUR")); exp = journal(inv, pay, cr); p = write(TOP / "k09a", inv, pay, cr, bank_for(exp)); rc, rep, out1 = run(p)
    r = random.Random(5)
    def dbl(rs):
        x = rs + [dict(y, loaded_at=iso(T(y["loaded_at"]) + timedelta(minutes=30))) for y in rs]; r.shuffle(x); return x
    p2 = write(TOP / "k09b", dbl(inv), dbl(pay), dbl(cr), bank_for(exp)); rc2, rep2, _ = run(p2)
    _, _, out1b = run(p)
    same = rep is not None and rep2 is not None and rep.get("currencies") == rep2.get("currencies") and rep.get("exceptions", {}).get("undelivered") is not None and \
        sorted(x.get("id") for x in rep["exceptions"]["undelivered"]) == sorted(x.get("id") for x in rep2["exceptions"]["undelivered"])
    row("K09_redelivered_shuffled_stable", rc == rc2 and same and not compare(rep2, exp) and out1.stdout == out1b.stdout, {"rcs": [rc, rc2], "same_figures": same, "rerun_identical": out1.stdout == out1b.stdout})
def k10():  # invalid packages exit 2, previous --out kept, then recovery
    inv, pay = k01.cache; d = TOP / "k10"; p = write(d, inv, pay, []); o = d / "r.json"
    rc0 = subprocess.run([PY, str(TOOL), "reconcile", str(p), "--json", "--out", str(o)], cwd=d, env=ENV, capture_output=True).returncode; keep = o.read_bytes() if o.exists() else None
    res = {}
    def bad(name, mut):
        pk = json.loads(p.read_text()); mut(pk); q = d / ("bad-%s.json" % name); q.write_text(json.dumps(pk)) if isinstance(pk, dict) else q.write_text(pk)
        res[name] = subprocess.run([PY, str(TOOL), "reconcile", str(q), "--json", "--out", str(o)], cwd=d, env=ENV, capture_output=True).returncode
    bad("wrong_schema", lambda k: k.update(schema="x/1")); bad("end_before_start", lambda k: k["period"].update(end="2026-06-01T00:00:00Z"))
    bad("missing_file", lambda k: k["payments"].update(file="nope.csv")); bad("bad_timezone", lambda k: k.update(timezone="Mars/Olympus"))
    bad("file_outside", lambda k: k["payments"].update(file="../../etc/hosts")); bad("unknown_field", lambda k: k.update(fx_rate=1.1))
    kept = o.exists() and o.read_bytes() == keep
    rc9 = subprocess.run([PY, str(TOOL), "reconcile", str(p), "--json"], cwd=d, env=ENV, capture_output=True).returncode
    row("K10_invalid_exit2_keeps_out_recovers", rc0 == 0 and all(v == 2 for v in res.values()) and kept and rc9 == 0, dict(res, first=rc0, kept=kept, recover=rc9))
def k11():  # amount formats: three decimals rejected, sub-cent rejected, thousands written "1,250.50" only when declared; zero-decimal JPY works
    inv = [{"invoice_id": "F1", "customer_id": "x", "currency": "USD", "amount": "10.005", "issued_at": "2026-07-02T09:00:00Z", "delivered_at": "2026-07-02T10:00:00Z", "status": "issued", "loaded_at": "2026-07-02T11:00:00Z"},
           {"invoice_id": "F2", "customer_id": "x", "currency": "JPY", "amount": "15000", "issued_at": "2026-07-02T09:00:00Z", "delivered_at": "2026-07-02T10:00:00Z", "status": "issued", "loaded_at": "2026-07-02T11:00:00Z"},
           {"invoice_id": "F3", "customer_id": "x", "currency": "USD", "amount": "abc", "issued_at": "2026-07-02T09:00:00Z", "delivered_at": "2026-07-02T10:00:00Z", "status": "issued", "loaded_at": "2026-07-02T11:00:00Z"}]
    p = write(TOP / "k11", inv, [], []); rc, rep, _ = run(p); rj = sorted(str(x.get("id") or x.get("line")) for x in (rep or {}).get("exceptions", {}).get("rejected", []))
    j = (rep or {}).get("currencies", {}).get("JPY", {})
    row("K11_amount_formats", rc == 1 and len(rj) == 2 and j.get("recognized_revenue") in ("15000", "15000.00") and (rep or {}).get("currencies", {}).get("USD", {}).get("billed", "0.00") == "0.00", {"rc": rc, "rejected": (rep or {}).get("exceptions", {}).get("rejected"), "jpy_rev": j.get("recognized_revenue")})
def k12():  # bank control per currency: a currency only on the bank side, and a control-only difference gives exit 1
    inv, pay = k01.cache; exp = journal(inv, pay, []); p = write(TOP / "k12", inv, pay, [], bank_for(exp) + [["SEK", "10.00", "0.00"]]); rc, rep, _ = run(p)
    p2 = write(TOP / "k12b", inv, pay, [], [["CHF", "1300.01", "0.00"]]); rc2, rep2, _ = run(p2)
    row("K12_bank_control", rc == 1 and rc2 == 1 and (rep2 or {}).get("controls", {}).get("CHF", {}).get("ok") is False and "SEK" in json.dumps((rep or {}).get("controls", {})) and "SEK" not in (rep or {}).get("currencies", {}),
        {"rc_one_sided": rc, "controls_one_sided": (rep or {}).get("controls"), "rc_diff": rc2, "chf": (rep2 or {}).get("controls", {}).get("CHF")})
def k13():  # reads only: package folder unchanged, no bytecode left from the G13 import (run without PYTHONDONTWRITEBYTECODE)
    inv, pay = k01.cache; d = TOP / "k13"; p = write(d, inv, pay, []); before = {x.name: x.read_bytes() for x in d.iterdir()}
    env = dict(ENV); env.pop("PYTHONDONTWRITEBYTECODE"); pc0 = sorted(str(x) for x in REPO.rglob("__pycache__"))
    rc = subprocess.run([PY, str(TOOL), "reconcile", str(p)], cwd=d, env=env, capture_output=True).returncode
    after = {x.name: x.read_bytes() for x in d.iterdir()}; pc1 = sorted(str(x) for x in REPO.rglob("__pycache__"))
    row("K13_reads_only_no_bytecode", rc == 0 and before == after and pc0 == pc1, {"rc": rc, "new_pycache": sorted(set(pc1) - set(pc0))})
def k14():  # OBS probes: refund larger than paid, credit note larger than invoice, payment before the invoice was issued, currency spelled with spaces
    res = {}
    inv = [{"invoice_id": "O1", "customer_id": "x", "currency": "USD", "amount": "100.00", "issued_at": "2026-07-10T09:00:00Z", "delivered_at": "2026-07-10T10:00:00Z", "status": "issued", "loaded_at": "2026-07-10T11:00:00Z"}]
    pay = [{"payment_id": "OP1", "invoice_id": "O1", "currency": "USD", "amount": "100.00", "received_at": "2026-07-05T09:00:00Z", "loaded_at": "2026-07-05T10:00:00Z"}]
    cr = [{"credit_id": "OR1", "invoice_id": "O1", "kind": "refund", "currency": "USD", "amount": "500.00", "issued_at": "2026-07-20T09:00:00Z", "loaded_at": "2026-07-20T10:00:00Z"},
          {"credit_id": "OC1", "invoice_id": "O1", "kind": "credit_note", "currency": "USD", "amount": "300.00", "issued_at": "2026-07-21T09:00:00Z", "loaded_at": "2026-07-21T10:00:00Z"}]
    p = write(TOP / "k14", inv, pay, cr); rc, rep, _ = run(p); u = (rep or {}).get("currencies", {}).get("USD", {})
    res["over_refund_over_credit"] = {"rc": rc, "closing": u.get("closing"), "revenue": u.get("recognized_revenue"), "exceptions": {k: v for k, v in (rep or {}).get("exceptions", {}).items() if v}}
    inv2 = [dict(inv[0], currency=" usd ")]; p2 = write(TOP / "k14b", inv2, [], []); rc2, rep2, _ = run(p2); res["currency_with_spaces"] = {"rc": rc2, "currencies": sorted((rep2 or {}).get("currencies", {})), "rejected": (rep2 or {}).get("exceptions", {}).get("rejected")}
    row("K14_obs_edge_probes", True, res, obs=True)
def inv1(**k):
    d = {"invoice_id": "V1", "customer_id": "x", "currency": "USD", "amount": "200.00", "issued_at": "2026-07-05T09:00:00Z", "delivered_at": "2026-07-05T10:00:00Z", "status": "issued", "loaded_at": "2026-07-05T11:00:00Z"}; d.update(k); return d
def pay1(**k):
    d = {"payment_id": "VP1", "invoice_id": "V1", "currency": "USD", "amount": "200.00", "received_at": "2026-07-06T09:00:00Z", "loaded_at": "2026-07-06T10:00:00Z"}; d.update(k); return d
def k15():  # void invoice: not billed, not revenue; payment to it unapplied (invoice_void)
    p = write(TOP / "k15", [inv1(status="void")], [pay1()], []); rc, rep, _ = run(p); u = (rep or {}).get("currencies", {}).get("USD", {})
    un = [(x.get("id"), x.get("reason")) for x in (rep or {}).get("exceptions", {}).get("unapplied", [])]
    row("K15_void_invoice", rc == 1 and u.get("billed") == "0.00" and u.get("recognized_revenue") == "0.00" and u.get("closing", {}).get("unapplied") == "200.00" and len(un) == 1 and "void" in un[0][1], {"rc": rc, "usd": {k: u.get(k) for k in ("billed", "recognized_revenue", "closing")}, "unapplied": un})
def k16():  # missing value: empty amount on an invoice and on a payment are rejected rows, not zero
    p = write(TOP / "k16", [inv1(), inv1(invoice_id="V2", amount="")], [pay1(), pay1(payment_id="VP2", amount="")], []); rc, rep, _ = run(p); u = (rep or {}).get("currencies", {}).get("USD", {})
    rj = (rep or {}).get("exceptions", {}).get("rejected", [])
    row("K16_missing_value_rejected", rc == 1 and len(rj) == 2 and u.get("billed") == "200.00" and u.get("cash_received") == "200.00", {"rc": rc, "rejected": rj, "billed": u.get("billed"), "cash": u.get("cash_received")})
def k17():  # an invoice excluded as conflicting cannot take payments: payment unapplied, AR not reduced
    p = write(TOP / "k17", [inv1(), inv1(amount="250.00")], [pay1()], []); rc, rep, _ = run(p); u = (rep or {}).get("currencies", {}).get("USD", {}); ex = (rep or {}).get("exceptions", {})
    row("K17_excluded_invoice_not_linkable", rc == 1 and [x.get("id") for x in ex.get("conflicting_versions", [])] == ["V1"] and u.get("billed") == "0.00" and u.get("closing", {}).get("unapplied") == "200.00" and u.get("closing", {}).get("ar_net") == "0.00",
        {"rc": rc, "conflicting": ex.get("conflicting_versions"), "unapplied": ex.get("unapplied"), "closing": u.get("closing")})
def k18():  # period end is exclusive: invoice issued exactly at end is not billed in the period
    p = write(TOP / "k18", [inv1(), inv1(invoice_id="V2", issued_at=iso(E), delivered_at=iso(E), loaded_at=iso(E + timedelta(hours=1)))], [pay1()], [], [["USD", "200.00", "0.00"]]); rc, rep, _ = run(p); u = (rep or {}).get("currencies", {}).get("USD", {})
    row("K18_period_end_exclusive", rc == 0 and u.get("billed") == "200.00" and u.get("recognized_revenue") == "200.00" and u.get("closing", {}).get("ar_net") == "0.00", {"rc": rc, "billed": u.get("billed"), "revenue": u.get("recognized_revenue"), "closing": u.get("closing")})
def k19():  # bank control: cash out difference, and a ledger currency missing from the statement, each give exit 1
    cr = [{"credit_id": "VR1", "invoice_id": "V1", "kind": "refund", "currency": "USD", "amount": "20.00", "issued_at": "2026-07-09T09:00:00Z", "loaded_at": "2026-07-09T10:00:00Z"}]
    p = write(TOP / "k19a", [inv1()], [pay1()], cr, [["USD", "200.00", "25.00"]]); rc, rep, _ = run(p); c = (rep or {}).get("controls", {}).get("USD", {})
    p2 = write(TOP / "k19b", [inv1(), inv1(invoice_id="V3", currency="EUR")], [pay1(), pay1(payment_id="VP3", invoice_id="V3", currency="EUR")], [], [["USD", "200.00", "0.00"]]); rc2, rep2, _ = run(p2); c2_ = (rep2 or {}).get("controls", {})
    row("K19_bank_out_and_one_sided_ledger", rc == 1 and c.get("ok") is False and c.get("difference_out") in ("5.00", "-5.00") and rc2 == 1 and c2_.get("EUR", {}).get("ok") is False, {"rc_out": rc, "usd": c, "rc_one_sided": rc2, "eur": c2_.get("EUR")})
def k20():  # doc-silent refusals, recorded: as_of before period end, duplicate JSON key in the package
    inv, pay = k01.cache; d = TOP / "k20"; p = write(d, inv, pay, [], extra={"as_of": "2026-07-20T00:00:00Z"}); rc, rep, _ = run(p)
    txt = (d / "package.json").read_text(); (d / "dup.json").write_text(txt[:-1] + ', "timezone": "Europe/Paris"}'); rc2 = subprocess.run([PY, str(TOOL), "reconcile", str(d / "dup.json")], cwd=d, env=ENV, capture_output=True).returncode
    row("K20_doc_silent_refusals", True, {"as_of_before_end_rc": rc, "duplicate_key_rc": rc2}, obs=True)
k01.cache = None
def _k01():
    k01.cache = k01()
for rid, fn in (("K01", _k01), ("K02", k02), ("K03", k03), ("K04", k04), ("K05", k05), ("K06", k06), ("K07", k07), ("K08", k08), ("K09", k09), ("K10", k10), ("K11", k11), ("K12", k12), ("K13", k13), ("K14", k14), ("K15", k15), ("K16", k16), ("K17", k17), ("K18", k18), ("K19", k19), ("K20", k20)):
    try: fn()
    except Exception as e: row(rid + "_crash", False, "harness or tool crash: %r" % (e,))
shutil.rmtree(TOP, ignore_errors=True)
json.dump(rows, open(OUT, "w"), indent=1, default=str)
core = [r for r in rows if r["kind"] == "core"]
for r in rows: print(r["id"], r["result"], json.dumps(r["detail"], default=str)[:900])
print("M14 ORACLE %d/%d core PASS" % (sum(r["result"] == "PASS" for r in core), len(core)))
