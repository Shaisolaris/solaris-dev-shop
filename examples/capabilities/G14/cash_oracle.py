#!/usr/bin/env python3
"""G14 oracle: invoice, payment and credit reconciliation (recognized revenue versus cash).

Literal expected values for hand-worked cases, and for seeded random books an independent
double-entry journal (issue, delivery, credit note, payment, refund posted to AR, deferred,
unbilled, revenue, cash and unapplied accounts) that the tool's numbers must equal to the cent.
Runs  CMD reconcile PACKAGE --json [--out REPORT]  for every check.

Usage: cash_oracle.py [--seed N] [--quick] -- CMD...
"""
from __future__ import annotations

import argparse
import copy
import csv
import datetime as dt
import hashlib
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import time
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"
CMD = []
RESULTS = []
Z = Decimal("0")
UTC = dt.timezone.utc
START, END = dt.datetime(2026, 9, 1, tzinfo=UTC), dt.datetime(2026, 10, 1, tzinfo=UTC)
AS_OF = dt.datetime(2026, 10, 3, tzinfo=UTC)  # write_book default
FIELDS = {"invoices": ["invoice_id", "customer_id", "currency", "amount", "issued_at", "delivered_at", "status", "loaded_at"],
          "payments": ["payment_id", "invoice_id", "currency", "amount", "received_at", "loaded_at"],
          "credits": ["credit_id", "invoice_id", "kind", "currency", "amount", "issued_at", "loaded_at"]}


def iso(t):
    return "" if t is None else t.strftime("%Y-%m-%dT%H:%M:%SZ")


def write_book(d, book, bank=None, as_of="2026-10-03T00:00:00Z", extra=None):
    d = Path(d)
    d.mkdir(parents=True, exist_ok=True)
    for kind, cols in FIELDS.items():
        with open(d / ("%s.csv" % kind), "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(cols)
            for r in book[kind]:
                w.writerow([iso(r[c]) if isinstance(r.get(c), dt.datetime) else ("" if r.get(c) is None else str(r[c])) for c in cols])
    pkg = {"schema": "solaris.cash-revenue/1", "timezone": "UTC", "period": {"start": iso(START), "end": iso(END)},
           "as_of": as_of, "invoices": {"file": "invoices.csv"}, "payments": {"file": "payments.csv"}, "credits": {"file": "credits.csv"}}
    if bank is not None:
        with open(d / "bank.csv", "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["currency", "cash_in", "cash_out"])
            for cur, (i, o) in sorted(bank.items()):
                w.writerow([cur, str(i), str(o)])
        pkg["bank"] = {"file": "bank.csv"}
    if extra:
        pkg.update(extra)
    (d / "package.json").write_text(json.dumps(pkg, indent=1))
    return d / "package.json"


def random_book(rng, n=300, currencies=("USD", "EUR", "JPY")):
    """Valid, linked books (every payment and credit points at an issued invoice in its currency)
    plus a few unapplied payments; times spread over July to November."""
    base = dt.datetime(2026, 7, 1, tzinfo=UTC)
    rnd_t = lambda lo, hi: base + dt.timedelta(minutes=rng.randrange(lo * 1440, hi * 1440))
    book = {"invoices": [], "payments": [], "credits": []}
    for i in range(n):
        cur = rng.choice(currencies)
        amt = Decimal(rng.randrange(1000, 500000)) / 100
        issued = rnd_t(0, 120)
        dl = rng.random()
        delivered = None if dl < 0.05 else (issued - dt.timedelta(days=rng.randrange(1, 10)) if dl < 0.15 else issued + dt.timedelta(days=rng.randrange(0, 40)))
        iid = "INV-%05d" % i
        book["invoices"].append({"invoice_id": iid, "customer_id": "c%d" % (i % 50), "currency": cur, "amount": amt, "issued_at": issued,
                                 "delivered_at": delivered, "status": "issued", "loaded_at": issued})
        paid = Z
        for j in range(rng.randrange(0, 3)):
            p = (amt * Decimal(rng.choice([25, 50, 60, 100, 110])) / 100).quantize(Decimal("0.01"))
            t = issued + dt.timedelta(days=rng.randrange(-5, 50))
            book["payments"].append({"payment_id": "PAY-%05d-%d" % (i, j), "invoice_id": iid, "currency": cur, "amount": p, "received_at": t, "loaded_at": t})
            paid += p
        if rng.random() < 0.2:
            c = (amt * Decimal(rng.choice([10, 20, 50])) / 100).quantize(Decimal("0.01"))
            t = issued + dt.timedelta(days=rng.randrange(0, 45))
            book["credits"].append({"credit_id": "CN-%05d" % i, "invoice_id": iid, "kind": "credit_note", "currency": cur, "amount": c, "issued_at": t, "loaded_at": t})
        if paid > 0 and rng.random() < 0.15:
            r = (paid * Decimal(rng.choice([10, 50])) / 100).quantize(Decimal("0.01"))
            t = issued + dt.timedelta(days=rng.randrange(1, 60))
            book["credits"].append({"credit_id": "RF-%05d" % i, "invoice_id": iid, "kind": "refund", "currency": cur, "amount": r, "issued_at": t, "loaded_at": t})
    for k in range(max(1, n // 50)):
        t = rnd_t(40, 110)
        book["payments"].append({"payment_id": "PAY-U%03d" % k, "invoice_id": "NOPE-%d" % k, "currency": rng.choice(currencies),
                                 "amount": Decimal(rng.randrange(100, 9999)) / 100, "received_at": t, "loaded_at": t})
    return book


def journal(book):
    """Independent double-entry ledger over the as-of view (rows loaded after AS_OF are not known yet).
    Returns expected per-currency report values."""
    book = {k: [r for r in v if r["loaded_at"] <= AS_OF] for k, v in book.items()}
    inv = {r["invoice_id"]: r for r in book["invoices"] if r["status"] == "issued"}
    ev = []  # (time, order, kind, record)
    for r in inv.values():
        ev.append((r["issued_at"], 0, "issue", r))
        if r["delivered_at"] is not None:
            ev.append((r["delivered_at"], 1, "deliver", r))
    for r in book["payments"]:
        ok = r["invoice_id"] in inv and inv[r["invoice_id"]]["currency"] == r["currency"]
        ev.append((r["received_at"], 2, "pay" if ok else "upay", r))
    for r in book["credits"]:
        ok = r["invoice_id"] in inv and inv[r["invoice_id"]]["currency"] == r["currency"]
        ev.append((r["issued_at"], 2, r["kind"] if ok else "u" + r["kind"], r))
    ev.sort(key=lambda e: (e[0], e[1]))

    def snapshot(T):
        acc, sub, st = {}, {}, {}
        A = lambda cur: acc.setdefault(cur, {k: Z for k in ("ar", "deferred", "unbilled", "revenue", "cash", "unapplied")})
        for t, _o, kind, r in ev:
            if t >= T:
                break
            cur = r["currency"]
            a = A(cur)
            if kind == "issue":
                s = st.setdefault(r["invoice_id"], {"issued": False, "delivered": False, "cn": Z})
                s["issued"] = True
                sub[r["invoice_id"]] = sub.get(r["invoice_id"], Z) + r["amount"]
                a["ar"] += r["amount"]
                if s["delivered"]:
                    a["unbilled"] -= r["amount"]
                else:
                    a["deferred"] += r["amount"]
            elif kind == "deliver":
                s = st.setdefault(r["invoice_id"], {"issued": False, "delivered": False, "cn": Z})
                s["delivered"] = True
                if s["issued"]:
                    a["deferred"] -= r["amount"] - s["cn"]
                    a["revenue"] += r["amount"] - s["cn"]
                else:
                    a["unbilled"] += r["amount"]
                    a["revenue"] += r["amount"]
            elif kind == "credit_note":
                s = st[r["invoice_id"]]
                s["cn"] += r["amount"]
                sub[r["invoice_id"]] -= r["amount"]
                a["ar"] -= r["amount"]
                if s["delivered"]:
                    a["revenue"] -= r["amount"]
                else:
                    a["deferred"] -= r["amount"]
            elif kind == "pay":
                a["cash"] += r["amount"]
                a["ar"] -= r["amount"]
                sub[r["invoice_id"]] = sub.get(r["invoice_id"], Z) - r["amount"]
            elif kind == "refund":
                a["cash"] -= r["amount"]
                a["ar"] += r["amount"]
                sub[r["invoice_id"]] = sub.get(r["invoice_id"], Z) + r["amount"]
            elif kind == "upay":
                a["cash"] += r["amount"]
                a["unapplied"] += r["amount"]
            elif kind == "urefund":
                a["cash"] -= r["amount"]
                a["unapplied"] -= r["amount"]
        owed, credit = {}, {}
        for iid, bal in sub.items():
            cur = inv[iid]["currency"]
            if bal > 0:
                owed[cur] = owed.get(cur, Z) + bal
            else:
                credit[cur] = credit.get(cur, Z) - bal
        return acc, owed, credit
    a0, o0, c0 = snapshot(START)
    a1, o1, c1 = snapshot(END)
    out = {}
    curs = set(a0) | set(a1)
    for cur in curs:
        z = {k: Z for k in ("ar", "deferred", "unbilled", "revenue", "cash", "unapplied")}
        x, y = a0.get(cur, z), a1.get(cur, z)
        billed = sum((r["amount"] for r in inv.values() if r["currency"] == cur and START <= r["issued_at"] < END), Z)
        cin = sum((r["amount"] for r in book["payments"] if r["currency"] == cur and START <= r["received_at"] < END), Z)
        cout = sum((r["amount"] for r in book["credits"] if r["currency"] == cur and r["kind"] == "refund" and START <= r["issued_at"] < END), Z)
        m = lambda v: str(v.quantize(Decimal("0.01")))
        out[cur] = {"recognized_revenue": m(y["revenue"] - x["revenue"]), "billed": m(billed), "cash_received": m(cin), "refunds_paid": m(cout),
                    "net_cash": m(y["cash"] - x["cash"]),
                    "closing": {"ar_net": m(y["ar"]), "deferred": m(y["deferred"]), "unbilled": m(y["unbilled"]), "unapplied": m(y["unapplied"]),
                                "ar_owed": m(o1.get(cur, Z)), "customer_credit": m(c1.get(cur, Z))},
                    "opening": {"ar_net": m(x["ar"]), "deferred": m(x["deferred"]), "unbilled": m(x["unbilled"]), "unapplied": m(x["unapplied"]),
                                "ar_owed": m(o0.get(cur, Z)), "customer_credit": m(c0.get(cur, Z))}}
    return out


def view(rep):
    """The fields the journal predicts."""
    out = {}
    for cur, c in (rep or {}).get("currencies", {}).items():
        out[cur] = {k: c.get(k) for k in ("recognized_revenue", "billed", "cash_received", "refunds_paid", "net_cash")}
        out[cur]["closing"] = c.get("closing")
        out[cur]["opening"] = c.get("opening")
    return out


def run(pkg, out=None, env=None):
    p = subprocess.run(CMD + ["reconcile", str(pkg), "--json"] + (["--out", str(out)] if out else []), capture_output=True, text=True, timeout=300, env=env)
    try:
        rep = json.loads(p.stdout) if p.returncode in (0, 1) else None
    except ValueError:
        rep = None
    return p.returncode, rep, p.stdout


def check(name, fn):
    try:
        ok, msg = fn()
    except Exception as exc:
        ok, msg = False, "%s: %s" % (type(exc).__name__, str(exc)[:200])
    RESULTS.append((name, ok))
    print("%s %s: %s" % ("PASS" if ok else "FAIL", name, msg))


def cur(rep, c, *path):
    v = (rep or {}).get("currencies", {}).get(c, {})
    for k in path:
        v = v.get(k, {}) if isinstance(v, dict) else None
    return v


def tree(d):
    h = hashlib.sha256()
    for root, dirs, files in sorted(os.walk(d)):
        dirs.sort()
        for f in sorted(files):
            p = os.path.join(root, f)
            h.update(p.encode() + open(p, "rb").read())
    return h.hexdigest()


SEPT_USD = {"billed": "2550.00", "credit_notes": "150.00", "recognized_revenue": "2000.00", "cash_received": "2195.00", "refunds_paid": "0.00", "net_cash": "2195.00"}
SEPT_USD_CLOSE = {"ar_net": "700.00", "ar_owed": "700.00", "customer_credit": "0.00", "deferred": "400.00", "unbilled": "0.00", "unapplied": "195.00"}


def main():
    global CMD
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=1409)
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("cmd", nargs=argparse.REMAINDER)
    a = ap.parse_args()
    CMD = a.cmd[1:] if a.cmd[:1] == ["--"] else a.cmd
    if not CMD:
        ap.error("give the tool command after --")
    rng = random.Random(a.seed)
    tmp = Path(tempfile.mkdtemp(prefix="g14-oracle-"))
    sept = tmp / "sept"
    shutil.copytree(FIX / "september", sept)

    def o1():
        rc, rep, _ = run(FIX / "clean" / "package.json")
        want = {"billed": "2250.50", "recognized_revenue": "2250.50", "cash_received": "2250.50", "net_cash": "2250.50"}
        got = {k: cur(rep, "USD", k) for k in want}
        ok = rc == 0 and got == want and cur(rep, "USD", "closing", "ar_net") == "0.00" and (rep or {}).get("result") == "reconciled" \
            and all(not v for v in (rep or {"exceptions": {"x": 1}})["exceptions"].values())
        return ok, "clean control: exact, no exceptions, exit 0" if ok else "rc %s got %s" % (rc, got)
    check("o1 clean control", o1)

    def o2():
        rc, rep, _ = run(sept / "package.json")
        got = {k: cur(rep, "USD", k) for k in SEPT_USD}
        close = cur(rep, "USD", "closing")
        eur = {k: cur(rep, "EUR", k) for k in ("recognized_revenue", "cash_received", "refunds_paid", "net_cash")}
        ok = rc == 1 and got == SEPT_USD and close == SEPT_USD_CLOSE and cur(rep, "USD", "opening", "ar_net") == "300.00" \
            and eur == {"recognized_revenue": "400.00", "cash_received": "450.00", "refunds_paid": "50.00", "net_cash": "400.00"} \
            and cur(rep, "GBP", "recognized_revenue") == "0.00" and cur(rep, "GBP", "closing", "unapplied") == "90.00"
        return ok, "hand-worked September book: USD revenue 2000.00 vs cash 2195.00, AR 300.00 -> 700.00, deferred 400.00, unapplied 195.00; EUR and GBP exact" if ok \
            else "rc %s USD %s close %s EUR %s" % (rc, got, close, eur)
    check("o2 partial payments, revenue versus cash", o2)

    def o3():
        rc, rep, _ = run(sept / "package.json")
        un = {(u["id"], u["currency"], u["reason"]) for u in (rep or {}).get("exceptions", {}).get("unapplied", [])}
        b = random_book(random.Random(a.seed + 3), n=60, currencies=("USD", "EUR"))
        for r in b["invoices"]:  # identical amounts in two currencies: any combining shows
            r["amount"] = Decimal("100.00")
        p = write_book(tmp / "o3", b)
        rc2, rep2, _ = run(p)
        ok = rc == 1 and ("P9", "USD", "currency_mismatch") in un and ("P11", "GBP", "invoice_void") in un and ("P8", "USD", "unknown_invoice") in un \
            and sorted((rep or {}).get("currencies", {})) == ["EUR", "GBP", "USD"] and view(rep2) == journal(b)
        return ok, "per-currency totals never combined; a USD payment on a EUR invoice stays unapplied USD; void-invoice payment unapplied" if ok \
            else "unapplied %s currencies %s" % (sorted(un), sorted((rep or {}).get("currencies", {})))
    check("o3 currency not silently combined", o3)

    def o4():
        rc, rep, _ = run(sept / "package.json")
        b = {"invoices": [{"invoice_id": "X1", "customer_id": "c", "currency": "USD", "amount": Decimal("400.00"), "issued_at": START + dt.timedelta(days=2),
                           "delivered_at": START + dt.timedelta(days=3), "status": "issued", "loaded_at": START + dt.timedelta(days=2)}],
             "payments": [{"payment_id": "Y1", "invoice_id": "X1", "currency": "USD", "amount": Decimal("450.00"), "received_at": START + dt.timedelta(days=4), "loaded_at": START + dt.timedelta(days=4)}],
             "credits": [{"credit_id": "Z1", "invoice_id": "X1", "kind": "refund", "currency": "USD", "amount": Decimal("20.00"), "issued_at": START + dt.timedelta(days=9), "loaded_at": START + dt.timedelta(days=9)}]}
        rc2, rep2, _ = run(write_book(tmp / "o4", b))
        ok = rc == 1 and cur(rep, "USD", "credit_notes") == "150.00" and cur(rep, "USD", "closing", "deferred") == "400.00" \
            and cur(rep, "EUR", "closing", "customer_credit") == "0.00" and rc2 == 0 \
            and cur(rep2, "USD", "closing") == {"ar_net": "-30.00", "ar_owed": "0.00", "customer_credit": "30.00", "deferred": "0.00", "unbilled": "0.00", "unapplied": "0.00"} \
            and cur(rep2, "USD", "recognized_revenue") == "400.00" and cur(rep2, "USD", "net_cash") == "430.00"
        return ok, "credit note after delivery is contra-revenue, before delivery reduces deferred; overpayment 50 then refund 20 leaves customer credit 30.00, not negative AR owed" if ok \
            else "o4 values %s %s" % (cur(rep2, "USD", "closing"), cur(rep2, "USD", "net_cash"))
    check("o4 refunds, credit notes and overpayment", o4)

    def o5():
        rc, rep, _ = run(sept / "package.json")
        late = [x["id"] for x in (rep or {}).get("exceptions", {}).get("late", [])]
        p = json.loads((sept / "package.json").read_text())
        p["as_of"] = "2026-10-06T00:00:00Z"
        (sept / "later.json").write_text(json.dumps(p))
        rc2, rep2, _ = run(sept / "later.json")
        ok = rc == 1 and late == ["P10"] and cur(rep2, "USD", "cash_received") == "2275.00" and cur(rep2, "USD", "closing", "ar_owed") == "620.00" \
            and not rep2["exceptions"]["late"] and rep2["controls"]["USD"]["ok"] is False and rep2["controls"]["USD"]["difference_in"] == "-80.00"
        os.unlink(sept / "later.json")
        return ok, "row loaded after as_of is late and named; a later cutoff takes it in (cash 2275.00, AR owed 620.00) and the bank control shows the 80.00 difference" if ok \
            else "late %s cash %s" % (late, cur(rep2, "USD", "cash_received"))
    check("o5 late rows and later cutoff", o5)

    def o6():
        d = tmp / "o6"
        shutil.copytree(sept, d)
        txt = (d / "invoices.csv").read_text().replace("I2,cust-b,USD,500.00", "I2,cust-b,USD,")
        (d / "invoices.csv").write_text(txt)
        with open(d / "payments.csv", "a") as fh:
            fh.write("P13,I1,USD,5.00,2026-09-20T09:00:00Z,\n")
            fh.write("P14,I1,USD,-5.00,2026-09-20T09:00:00Z,2026-09-20T10:00:00Z\n")
            fh.write("P15,I1,USD,1.005,2026-09-20T09:00:00Z,2026-09-20T10:00:00Z\n")
        with open(d / "credits.csv", "a") as fh:
            fh.write("C8,I6,credit_note,USD,10.00,2026-09-07T10:00:00Z,2026-09-07T11:00:00Z\n")
        rc, rep, _ = run(d / "package.json")
        ex = (rep or {}).get("exceptions", {})
        un = {(u["id"], u["reason"]) for u in ex.get("unapplied", [])}
        rej = {(r.get("id"), r["reason"]) for r in ex.get("rejected", [])}
        unl = [(x["id"], x["reason"]) for x in ex.get("unlinked_credits", [])]
        ok = rc == 1 and ("I2", "missing_value") in rej and ("P14", "bad_amount") in rej and ("P15", "bad_amount") in rej \
            and unl == [("C8", "credit_note_before_invoice")] and ("P2", "invoice_missing_value") in un and [x["id"] for x in ex.get("no_loaded_at", [])] == ["P13"] \
            and [x["id"] for x in ex.get("undelivered", [])] == ["I4"] and cur(rep, "USD", "recognized_revenue") == "1500.00" \
            and cur(rep, "USD", "closing", "unapplied") == "395.00"
        return ok, "invoice without an amount rejected and its payment unapplied; negative and sub-cent amounts rejected; credit note dated before its invoice unlinked; payment without loaded_at excluded and named; undelivered invoice named and not recognized" if ok \
            else "rej %s un %s unl %s rev %s" % (sorted(rej), sorted(un), unl, cur(rep, "USD", "recognized_revenue"))
    check("o6 missing evidence stays explicit", o6)

    def o7():
        d = tmp / "o7"
        shutil.copytree(sept, d)
        for f in ("invoices.csv", "payments.csv", "credits.csv"):
            lines = (d / f).read_text().splitlines()
            body = [l for l in lines[1:] if l]
            again = [l.rsplit(",", 1)[0] + ",2026-10-02T23:00:00Z" if not l.endswith("2026-10-05T12:00:00Z") else l for l in body]
            rng.shuffle(again)
            (d / f).write_text("\n".join([lines[0]] + body + again) + "\n")
        rc1, r1, out1 = run(sept / "package.json")
        rc2, r2, _ = run(d / "package.json")
        rc3, _, out3 = run(sept / "package.json")
        ok = rc1 == rc2 == 1 and r1["currencies"] == r2["currencies"] and out1 == out3 and [c["id"] for c in r2["exceptions"]["conflicting_versions"]] == ["P12"] \
            and r2["counts"]["exact_duplicates_collapsed"] > r1["counts"]["exact_duplicates_collapsed"]
        return ok, "every row delivered again (later load, shuffled): same balances; conflicting P12 excluded and named; rerun byte-identical" if ok \
            else "currencies differ or conflicts %s" % (r2 or {}).get("exceptions", {}).get("conflicting_versions")
    check("o7 duplicates and repeated import", o7)

    def o8():
        d = tmp / "o8"
        shutil.copytree(sept, d)
        (d / "bank.csv").write_text("currency,cash_in,cash_out\nUSD,2195.00,0.00\nEUR,450.00,45.00\nCHF,10.00,0.00\n")
        rc, rep, _ = run(d / "package.json")
        c = (rep or {}).get("controls") or {}
        d2 = tmp / "o8-clean"
        shutil.copytree(FIX / "clean", d2)
        (d2 / "bank.csv").write_text("currency,cash_in,cash_out\nUSD,2250.50,0.01\n")
        rc2, rep2, _ = run(d2 / "package.json")
        ok = rc == 1 and c.get("USD", {}).get("ok") is True and c.get("EUR", {}).get("difference_out") == "-5.00" and c.get("EUR", {}).get("ok") is False \
            and c.get("CHF", {}).get("ok") is False and c.get("GBP", {}).get("ok") is False and "CHF" not in rep["currencies"] \
            and rc2 == 1 and (rep2 or {}).get("result") == "reconciled_with_exceptions" and rep2["controls"]["USD"]["difference_out"] == "0.01"
        return ok, "bank control per currency: EUR refund difference -5.00, a bank-only CHF line and a missing GBP line flagged; a control difference alone turns a clean book into exit 1" if ok else "controls %s" % c
    check("o8 bank control", o8)

    def o9():
        bad = []
        for k in range(3):
            b = random_book(random.Random(a.seed * 10 + k), n=250)
            rc, rep, _ = run(write_book(tmp / ("o9-%d" % k), b))
            exp = journal(b)
            if rc not in (0, 1) or view(rep) != exp:
                g = view(rep)
                diff = [(c, f) for c in exp for f in exp[c] if (g.get(c) or {}).get(f) != exp[c][f]]
                bad.append((k, rc, diff[:4]))
            elif not all(ch["ok"] for c in rep["currencies"].values() for ch in c["checks"].values()):
                bad.append((k, "checks"))
        return not bad, "three seeded books (250 invoices, USD/EUR/JPY, partial, over- and pre-payments, credit notes, refunds, unbilled): equal to an independent double-entry journal to the cent; roll-forward and bridge close" if not bad else str(bad)
    check("o9 independent journal", o9)

    def o10():
        out = tmp / "o10.json"
        out.write_text("previous\n")
        cases = []
        d = tmp / "o10"
        shutil.copytree(sept, d)
        base = json.loads((d / "package.json").read_text())
        variants = [dict(base, schema="x"), dict(base, as_of="2026-09-20T00:00:00Z"), dict(base, invoices={"file": "../outside.csv"}),
                    dict(base, extra=1), dict(base, timezone="Mars/Olympus"), dict(base, period={"start": "2026-10-01", "end": "2026-09-01"})]
        for i, v in enumerate(variants):
            (d / ("v%d.json" % i)).write_text(json.dumps(v))
            cases.append(run(d / ("v%d.json" % i), out=out)[0])
        (d / "dup.json").write_text('{"as_of": "2026-10-04T00:00:00Z",' + json.dumps(base)[1:])
        cases.append(run(d / "dup.json", out=out)[0])
        (d / "payments.csv").write_text((d / "payments.csv").read_text().replace("received_at", "paid_on", 1))
        cases.append(run(d / "package.json", out=out)[0])
        kept = out.read_text() == "previous\n"
        rc, _, _ = run(sept / "package.json", out=out)
        rec = rc == 1 and json.loads(out.read_text())["currencies"]["USD"]["recognized_revenue"] == "2000.00"
        ok = cases == [2] * 8 and kept and rec
        return ok, "eight invalid packages (schema, early as_of, path escape, unknown field, zone, reversed period, duplicate key, header drift) exit 2 with the previous report kept; next valid run writes it" if ok \
            else "rcs %s kept %s rec %s" % (cases, kept, rec)
    check("o10 invalid input and recovery", o10)

    if not a.quick:
        def o11():
            b = random_book(random.Random(a.seed + 11), n=40000)
            p = write_book(tmp / "o11", b)
            t0 = time.time()
            rc, rep, _ = run(p)
            el = time.time() - t0
            ok = rc in (0, 1) and view(rep) == journal(b) and el < 120
            return ok, "40 000 invoices, %d payments, %d credits: equal to the journal in %.1fs" % (len(b["payments"]), len(b["credits"]), el) if ok else "rc %s %.1fs" % (rc, el)
        check("o11 operational scale", o11)

    def o12():
        guard = tmp / "guard"
        guard.mkdir()
        (guard / "sitecustomize.py").write_text("import socket\ndef _d(*a, **k):\n    raise RuntimeError('network denied')\nsocket.socket = _d\nsocket.create_connection = _d\n")
        before = tree(sept)
        rc, rep, _ = run(sept / "package.json", env=dict(os.environ, PYTHONPATH=str(guard), PYTHONDONTWRITEBYTECODE="1"))
        ok = rc == 1 and tree(sept) == before and cur(rep, "USD", "recognized_revenue") == "2000.00"
        return ok, "runs under a socket-denying guard; package folder byte-identical" if ok else "rc %s" % rc
    check("o12 offline and read-only", o12)

    def o13():
        # negative transactions larger than what they reverse (the M14 K14 book): invoice 100.00 paid 100.00,
        # then a 500.00 refund and a 300.00 credit note. The arithmetic stands, but it must be challenged.
        d = lambda n: START + dt.timedelta(days=n)
        b = {"invoices": [{"invoice_id": "K1", "customer_id": "c", "currency": "USD", "amount": Decimal("100.00"), "issued_at": d(2),
                           "delivered_at": d(3), "status": "issued", "loaded_at": d(2)}],
             "payments": [{"payment_id": "KP1", "invoice_id": "K1", "currency": "USD", "amount": Decimal("100.00"), "received_at": d(4), "loaded_at": d(4)}],
             "credits": [{"credit_id": "KR1", "invoice_id": "K1", "kind": "refund", "currency": "USD", "amount": Decimal("500.00"), "issued_at": d(6), "loaded_at": d(6)},
                         {"credit_id": "KC1", "invoice_id": "K1", "kind": "credit_note", "currency": "USD", "amount": Decimal("300.00"), "issued_at": d(7), "loaded_at": d(7)}]}
        rc, rep, _ = run(write_book(tmp / "o13", b))
        ex = (rep or {}).get("exceptions", {})
        bad_ok = rc == 1 and (rep or {}).get("result") == "reconciled_with_exceptions" and cur(rep, "USD", "recognized_revenue") == "-200.00" \
            and [(x.get("id"), x.get("excess")) for x in ex.get("over_refunded", [])] == [("K1", "400.00")] \
            and [(x.get("id"), x.get("excess")) for x in ex.get("over_credited", [])] == [("K1", "200.00")] \
            and all(c["ok"] for c in rep["currencies"]["USD"]["checks"].values())
        # boundaries: a refund equal to the payment and a credit note equal to the invoice are not challenged
        b["credits"][0]["amount"] = Decimal("100.00")
        b["credits"][1]["amount"] = Decimal("100.00")
        rc2, rep2, _ = run(write_book(tmp / "o13b", b))
        ex2 = (rep2 or {}).get("exceptions", {})
        edge_ok = rc2 == 0 and not ex2.get("over_refunded") and not ex2.get("over_credited")
        ok = bad_ok and edge_ok
        return ok, "refund 500 on 100 paid and credit 300 on a 100 invoice: exit 1, over_refunded excess 400.00 and over_credited excess 200.00 named, checks still close; equal amounts not challenged" if ok \
            else "rc %s ex %s / rc %s ex %s" % (rc, {k: ex.get(k) for k in ("over_refunded", "over_credited")}, rc2, {k: ex2.get(k) for k in ("over_refunded", "over_credited")})
    check("o13 over-refund and over-credit challenged", o13)

    passed = sum(1 for _, ok in RESULTS if ok)
    print("%s: %d/%d checks passed (seed %d)" % ("ACCEPTED" if passed == len(RESULTS) else "REJECTED", passed, len(RESULTS), a.seed))
    shutil.rmtree(tmp, ignore_errors=True)
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
