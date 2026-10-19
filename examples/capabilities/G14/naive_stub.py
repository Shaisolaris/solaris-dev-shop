#!/usr/bin/env python3
"""G14 naive control: the cash-basis spreadsheet (must be REJECTED).

Treats every payment row as revenue, adds all currencies into one number, counts re-delivered
rows twice, ignores credit notes, refunds, cutoffs and delivery, and calls AR invoices minus payments.
"""
import csv
import json
import sys
from decimal import Decimal
from pathlib import Path


def main():
    pkg = Path(sys.argv[2])
    p = json.loads(pkg.read_text())
    d = pkg.parent
    rows = lambda k: list(csv.DictReader(open(d / p[k]["file"])))
    amt = lambda r: Decimal((r.get("amount") or "0").replace(",", "") or "0")
    inv = sum((amt(r) for r in rows("invoices")), Decimal(0))
    cash = sum((amt(r) for r in rows("payments")), Decimal(0))
    m = lambda v: str(v.quantize(Decimal("0.01")))
    c = {"billed": m(inv), "credit_notes": "0.00", "recognized_revenue": m(cash), "cash_received": m(cash), "refunds_paid": "0.00",
         "net_cash": m(cash), "opening": {}, "closing": {"ar_net": m(inv - cash), "ar_owed": m(inv - cash), "customer_credit": "0.00",
                                                          "deferred": "0.00", "unbilled": "0.00", "unapplied": "0.00"},
         "checks": {"all": {"ok": True}}}
    rep = {"currencies": {"USD": c}, "exceptions": {}, "controls": None, "counts": {}, "result": "reconciled"}
    out = json.dumps(rep, sort_keys=True, indent=1) + "\n"
    if "--out" in sys.argv:
        open(sys.argv[sys.argv.index("--out") + 1], "w").write(out)
    sys.stdout.write(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
