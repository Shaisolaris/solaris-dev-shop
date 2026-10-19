#!/usr/bin/env python3
"""Naive control for the G22 oracle: the same CLI with the shortcuts webhook handlers usually take.

It loads the real payment_ledger.py and swaps in three habits: the signature and timestamp are not
checked, an event that arrives before what it needs is dropped instead of held, and an order is taken
without checking available stock (it books phantom stock to make the order fit). Not for use; it exists so the oracle and tests can show they catch
these habits.
"""
import importlib.util
import sys
from pathlib import Path

TOOL = Path(__file__).resolve().parents[3] / "employees" / "specialized" / "payments-specialist" / "payment_ledger.py"
spec = importlib.util.spec_from_file_location("payment_ledger_naive", str(TOOL))
m = importlib.util.module_from_spec(spec)
sys.dont_write_bytecode = True
spec.loader.exec_module(m)

m.hmac.compare_digest = lambda a, b: True
m.SIG_RE = m.re.compile(r"^t=([0-9]{1,12}),v1=(.*)$")
_apply = m.apply


def apply(con, ev):
    state, reason = _apply(con, ev)
    if state == "held":
        return "exception", "dropped: " + reason
    if state == "exception" and reason.startswith("out_of_stock"):
        sku = reason.split()[1]
        con.execute("UPDATE skus SET on_hand = on_hand + 1000, initial = initial + 1000 WHERE sku = ?", (sku,))
        return _apply(con, ev)
    return state, reason


m.apply = apply
if __name__ == "__main__":
    sys.exit(m.main())
