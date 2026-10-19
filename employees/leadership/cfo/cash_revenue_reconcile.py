#!/usr/bin/env python3
"""Invoice, payment and credit reconciliation: recognized revenue versus cash (Solaris CFO).

Reads a package (JSON, schema "solaris.cash-revenue/1") that names an invoices file, a payments
file, a credits file (credit notes and refunds), an optional bank control file, the reporting
period, the time zone and an optional as-of cutoff. CSV parsing, typed decimal and timestamp
values and row rejects come from the G13 data-engineer tool (csv_reconcile.py read_table), so a
malformed row is rejected with its line, never guessed.

Per currency, never combined, with exact decimal arithmetic:
  billed, credit notes, recognized revenue (an invoice is recognized when its delivery is
  evidenced by delivered_at; credit notes after delivery are contra-revenue, before delivery they
  reduce deferred revenue), cash received, refunds paid, net cash; opening and closing receivables
  (net, split into amounts owed and customer credit balances), deferred revenue, unbilled revenue
  and unapplied cash; an AR roll-forward and a revenue-to-cash bridge that must both close to the
  cent; and the bank control when one is supplied.

Nothing is inferred: a payment without a usable invoice (no reference, unknown, void, rejected,
conflicting, other currency) stays unapplied cash with its reason; an invoice without delivery
evidence stays deferred and is named; rows loaded after as_of are late and listed; an id delivered
twice with the same content counts once, with different content every version is excluded and named.

Usage:
  cash_revenue_reconcile.py reconcile PACKAGE.json [--json] [--out REPORT]
Exit codes: 0 reconciled, no exceptions, controls match; 1 reconciled with exceptions or a control
difference (listed); 2 invalid package or input (nothing written).
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import os
import sys
import tempfile
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PACKAGE_SCHEMA = "solaris.cash-revenue/1"
REPORT_SCHEMA = "solaris.cash-revenue-report/1"
HERE = Path(__file__).resolve().parent
G13 = HERE.parent.parent / "data" / "data-engineer" / "csv_reconcile.py"
CENT = Decimal("0.01")
ZERO = Decimal("0")
TABLES = {
    "invoices": ({"invoice_id": "str", "customer_id": "str", "currency": "str", "amount": "decimal",
                  "issued_at": "timestamp", "delivered_at": "timestamp", "status": "str", "loaded_at": "timestamp"},
                 "invoice_id", ["customer_id", "currency", "amount", "issued_at", "status"]),
    "payments": ({"payment_id": "str", "invoice_id": "str", "currency": "str", "amount": "decimal",
                  "received_at": "timestamp", "loaded_at": "timestamp"},
                 "payment_id", ["currency", "amount", "received_at"]),
    "credits": ({"credit_id": "str", "invoice_id": "str", "kind": "str", "currency": "str", "amount": "decimal",
                 "issued_at": "timestamp", "loaded_at": "timestamp"},
                "credit_id", ["kind", "currency", "amount", "issued_at"]),
}
BANK = {"currency": "str", "cash_in": "decimal", "cash_out": "decimal"}


class Invalid(Exception):
    """The package cannot be reconciled; nothing is written."""


def _load_g13() -> Any:
    name = "solaris_g14_csv_reconcile"
    if name in sys.modules:
        return sys.modules[name]
    if not G13.is_file():
        raise Invalid("required tool data-engineer/csv_reconcile.py (G13) is not present")
    old = sys.dont_write_bytecode
    sys.dont_write_bytecode = True  # never leave __pycache__ in the data-engineer folder
    try:
        spec = importlib.util.spec_from_file_location(name, str(G13))
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
    finally:
        sys.dont_write_bytecode = old
    return mod


def _no_dupes(pairs: List[Tuple[str, Any]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k, v in pairs:
        if k in out:
            raise Invalid(f"duplicate key {k!r} in the package; ambiguous")
        out[k] = v
    return out


def _bad_const(name: str) -> Any:
    raise Invalid(f"non-finite number {name} in the package")


def money(d: Decimal) -> str:
    return str(d.quantize(CENT))


def load_package(path: str) -> Dict[str, Any]:
    g = _load_g13()
    p = Path(path)
    try:
        raw = p.read_bytes()
    except OSError as exc:
        raise Invalid(f"cannot read package: {exc.strerror}") from None
    try:
        doc = json.loads(raw.decode("utf-8"), object_pairs_hook=_no_dupes, parse_constant=_bad_const)
    except Invalid:
        raise
    except (UnicodeDecodeError, ValueError):
        raise Invalid(f"{p.name}: not valid UTF-8 JSON") from None
    if not isinstance(doc, dict) or doc.get("schema") != PACKAGE_SCHEMA:
        raise Invalid(f"schema must be {PACKAGE_SCHEMA!r}")
    extra = sorted(set(doc) - {"schema", "timezone", "period", "as_of", "invoices", "payments", "credits", "bank"})
    if extra:
        raise Invalid(f"unknown field(s) {extra}; refusing to ignore evidence")
    base = p.resolve().parent
    tzname = doc.get("timezone", "UTC")
    try:
        tz = g.ZoneInfo(tzname) if isinstance(tzname, str) else None
    except Exception:
        tz = None
    if tz is None:
        raise Invalid(f"timezone {tzname!r} is not a known IANA zone")
    per = doc.get("period")
    if not isinstance(per, dict):
        raise Invalid("period: expected {start, end}")
    try:
        start = g._time_const(per.get("start"), "period.start", tz)
        end = g._time_const(per.get("end"), "period.end", tz)
        as_of = None if doc.get("as_of") is None else g._time_const(doc["as_of"], "as_of", tz)
    except g.Invalid as exc:
        raise Invalid(str(exc)) from None
    if end <= start:
        raise Invalid("period.end must be after period.start")
    if as_of is not None and as_of < end:
        raise Invalid("as_of is before the period end; the period cannot be closed at that cutoff")
    tables = {}
    for kind, (cols, _key, _req) in list(TABLES.items()) + [("bank", (BANK, None, None))]:
        spec = doc.get(kind)
        if spec is None:
            if kind == "bank":
                continue
            raise Invalid(f"{kind}: the package must name the {kind} file")
        if not isinstance(spec, dict) or set(spec) - {"file", "header_aliases", "thousands_separator", "delimiter"}:
            raise Invalid(f"{kind}: give file and optionally header_aliases, thousands_separator, delimiter")
        t = dict(spec, columns=cols, uppercase=["currency"])
        try:
            tables[kind] = g._table(t, kind, base)
        except g.Invalid as exc:
            raise Invalid(str(exc)) from None
    return {"g13": g, "tz": tz, "start": start, "end": end, "as_of": as_of, "tables": tables, "package_sha256": hashlib.sha256(raw).hexdigest()}


def _content(row: Dict[str, Any]) -> Tuple:
    return tuple(sorted((k, str(v)) for k, v in row.items() if k not in ("_line", "loaded_at")))


def _clean(kind: str, P: Dict[str, Any], exc: Dict[str, List[Dict[str, Any]]], facts: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Read one table through G13 and return {id: row} for rows usable as evidence."""
    g = P["g13"]
    cols, key, req = TABLES[kind]
    t = P["tables"][kind]
    try:
        good, rejected, f = g.read_table(t, P["tz"])
    except g.Invalid as e:
        raise Invalid(str(e)) from None
    facts.append({"file": f["file"], "sha256": f["sha256"], "data_rows": f["data_rows"], "ignored_columns": f["ignored_columns"]})
    for r in rejected:
        exc["rejected"].append(dict(r, table=kind))
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for r in good:
        where = {"table": kind, "file": t["file"], "line": r["_line"], "id": r.get(key)}
        if r.get(key) is None:
            exc["rejected"].append(dict(where, reason="missing_value", detail=key))
            continue
        missing = [c for c in req if r.get(c) is None]
        if missing:
            exc["rejected"].append(dict(where, reason="missing_value", detail=",".join(missing)))
            exc["_excluded"][kind][r[key]] = "missing_value"
            continue
        a = r["amount"]
        if a <= 0 or a.as_tuple().exponent < -2:
            exc["rejected"].append(dict(where, reason="bad_amount", detail=str(a)))
            exc["_excluded"][kind][r[key]] = "bad_amount"
            continue
        if kind == "invoices" and r["status"] not in ("issued", "void"):
            exc["rejected"].append(dict(where, reason="bad_status", detail=r["status"][:20]))
            exc["_excluded"][kind][r[key]] = "bad_status"
            continue
        if kind == "credits" and r["kind"] not in ("credit_note", "refund"):
            exc["rejected"].append(dict(where, reason="bad_kind", detail=r["kind"][:20]))
            exc["_excluded"][kind][r[key]] = "bad_kind"
            continue
        if P["as_of"] is not None:
            if r.get("loaded_at") is None:
                exc["no_loaded_at"].append(where)
                exc["_excluded"][kind][r[key]] = "no_loaded_at"
                continue
            if r["loaded_at"] > P["as_of"]:
                exc["late"].append(dict(where, loaded_at=r["loaded_at"].isoformat()))
                exc["_excluded"][kind][r[key]] = "late"
                continue
        groups.setdefault(r[key], []).append(r)
    out: Dict[str, Dict[str, Any]] = {}
    for k, rows in groups.items():
        versions = {_content(r) for r in rows}
        if len(versions) > 1:
            exc["conflicting_versions"].append({"table": kind, "id": k, "lines": sorted(r["_line"] for r in rows)})
            exc["_excluded"][kind][k] = "conflicting_versions"
            continue
        exc["_duplicates"] += len(rows) - 1
        out[k] = rows[0]
    return out


def reconcile(path: str) -> Tuple[Dict[str, Any], int]:
    P = load_package(path)
    start, end = P["start"], P["end"]
    exc: Dict[str, Any] = {"rejected": [], "late": [], "no_loaded_at": [], "conflicting_versions": [], "unapplied": [],
                           "unlinked_credits": [], "undelivered": [], "_excluded": {k: {} for k in TABLES}, "_duplicates": 0}
    facts: List[Dict[str, Any]] = []
    inv = _clean("invoices", P, exc, facts)
    pay = _clean("payments", P, exc, facts)
    cred = _clean("credits", P, exc, facts)
    void = {k for k, r in inv.items() if r["status"] == "void"}
    for k in void:
        exc["_excluded"]["invoices"][k] = "void"
    inv = {k: r for k, r in inv.items() if k not in void}

    def link(r: Dict[str, Any]) -> Optional[str]:
        """Why this payment/credit cannot be applied to its invoice, or None."""
        i = r.get("invoice_id")
        if i is None:
            return "no_invoice_reference"
        if i in exc["_excluded"]["invoices"]:
            return "invoice_" + exc["_excluded"]["invoices"][i]
        if i not in inv:
            return "unknown_invoice"
        if inv[i]["currency"] != r["currency"]:
            return "currency_mismatch"
        return None

    events: List[Tuple[str, str, dt.datetime, Decimal, Optional[str]]] = []  # (type, currency, time, amount, invoice)
    for k, r in sorted(pay.items()):
        why = link(r)
        if why:
            exc["unapplied"].append({"table": "payments", "id": k, "currency": r["currency"], "amount": money(r["amount"]), "reason": why})
            events.append(("unapplied_pay", r["currency"], r["received_at"], r["amount"], None))
        else:
            events.append(("pay", r["currency"], r["received_at"], r["amount"], r["invoice_id"]))
    for k, r in sorted(cred.items()):
        why = link(r)
        if why is None and r["kind"] == "credit_note" and r["issued_at"] < inv[r["invoice_id"]]["issued_at"]:
            why = "credit_note_before_invoice"
        if r["kind"] == "refund":
            if why:
                exc["unapplied"].append({"table": "credits", "id": k, "currency": r["currency"], "amount": money(-r["amount"]), "reason": why})
                events.append(("unapplied_ref", r["currency"], r["issued_at"], r["amount"], None))
            else:
                events.append(("ref", r["currency"], r["issued_at"], r["amount"], r["invoice_id"]))
        elif why:
            exc["unlinked_credits"].append({"id": k, "currency": r["currency"], "amount": money(r["amount"]), "reason": why})
        else:
            events.append(("cn", r["currency"], r["issued_at"], r["amount"], r["invoice_id"]))

    def state(T: dt.datetime) -> Dict[str, Dict[str, Decimal]]:
        """Balances as at T (events strictly before T), per currency."""
        per_inv: Dict[str, Dict[str, Decimal]] = {k: {"cn": ZERO, "pay": ZERO, "ref": ZERO} for k in inv}
        unapplied: Dict[str, Decimal] = {}
        cash: Dict[str, Decimal] = {}
        for typ, cur, t, amt, i in events:
            if t >= T:
                continue
            if typ in ("pay", "unapplied_pay"):
                cash[cur] = cash.get(cur, ZERO) + amt
            elif typ in ("ref", "unapplied_ref"):
                cash[cur] = cash.get(cur, ZERO) - amt
            if typ == "unapplied_pay":
                unapplied[cur] = unapplied.get(cur, ZERO) + amt
            elif typ == "unapplied_ref":
                unapplied[cur] = unapplied.get(cur, ZERO) - amt
            else:
                per_inv[i][typ] += amt
        out: Dict[str, Dict[str, Decimal]] = {}
        blank = lambda: {k: ZERO for k in ("ar_owed", "customer_credit", "ar_net", "deferred", "unbilled", "unapplied", "cum_revenue", "cum_cash")}
        for k, r in inv.items():
            s = out.setdefault(r["currency"], blank())
            v = per_inv[k]
            issued = r["issued_at"] < T
            delivered = r["delivered_at"] is not None and r["delivered_at"] < T
            bal = (r["amount"] - v["cn"] if issued else ZERO) - v["pay"] + v["ref"]
            s["ar_net"] += bal
            if bal > 0:
                s["ar_owed"] += bal
            else:
                s["customer_credit"] -= bal
            if delivered:
                s["cum_revenue"] += r["amount"] - v["cn"]
                if not issued:
                    s["unbilled"] += r["amount"]
            elif issued:
                s["deferred"] += r["amount"] - v["cn"]
        for cur in set(unapplied) | set(cash):
            s = out.setdefault(cur, blank())
            s["unapplied"] = unapplied.get(cur, ZERO)
            s["cum_cash"] = cash.get(cur, ZERO)
        return out

    s0, s1 = state(start), state(end)
    flows: Dict[str, Dict[str, Decimal]] = {}

    def fl(cur: str) -> Dict[str, Decimal]:
        return flows.setdefault(cur, {k: ZERO for k in ("billed", "credit_notes", "cash_received", "refunds_paid", "applied_payments", "applied_refunds")})
    deferred_items: List[Dict[str, Any]] = []
    for k, r in sorted(inv.items()):
        if start <= r["issued_at"] < end:
            fl(r["currency"])["billed"] += r["amount"]
        else:
            fl(r["currency"])
        if r["delivered_at"] is None:
            exc["undelivered"].append({"id": k, "currency": r["currency"], "amount": money(r["amount"]),
                                       "reason": "no delivery evidence (delivered_at empty); held as deferred, never recognized"})
        elif r["delivered_at"] >= end and r["issued_at"] < end:
            deferred_items.append({"id": k, "currency": r["currency"], "delivered_at": r["delivered_at"].isoformat()})
    for typ, cur, t, amt, i in events:
        if not (start <= t < end):
            fl(cur)
            continue
        f = fl(cur)
        if typ in ("pay", "unapplied_pay"):
            f["cash_received"] += amt
            if typ == "pay":
                f["applied_payments"] += amt
        elif typ in ("ref", "unapplied_ref"):
            f["refunds_paid"] += amt
            if typ == "ref":
                f["applied_refunds"] += amt
        elif typ == "cn":
            f["credit_notes"] += amt

    currencies: Dict[str, Any] = {}
    all_ok = True
    zero_state = {k: ZERO for k in ("ar_owed", "customer_credit", "ar_net", "deferred", "unbilled", "unapplied", "cum_revenue", "cum_cash")}
    for cur in sorted(set(flows) | set(s0) | set(s1)):
        a, b, f = s0.get(cur, zero_state), s1.get(cur, zero_state), fl(cur)
        revenue = b["cum_revenue"] - a["cum_revenue"]
        net_cash = f["cash_received"] - f["refunds_paid"]
        roll = a["ar_net"] + f["billed"] - f["credit_notes"] - f["applied_payments"] + f["applied_refunds"]
        bridge = (b["ar_net"] - a["ar_net"]) - (b["deferred"] - a["deferred"]) + (b["unbilled"] - a["unbilled"]) - (b["unapplied"] - a["unapplied"])
        checks = {"ar_rollforward": {"expected_closing_ar": money(roll), "closing_ar": money(b["ar_net"]), "ok": roll == b["ar_net"]},
                  "revenue_cash_bridge": {"revenue_minus_cash": money(revenue - net_cash), "balance_changes": money(bridge), "ok": revenue - net_cash == bridge},
                  "cash_ledger": {"cash_from_balances": money(b["cum_cash"] - a["cum_cash"]), "net_cash": money(net_cash), "ok": b["cum_cash"] - a["cum_cash"] == net_cash}}
        all_ok = all_ok and all(c["ok"] for c in checks.values())
        currencies[cur] = {
            "billed": money(f["billed"]), "credit_notes": money(f["credit_notes"]), "recognized_revenue": money(revenue),
            "cash_received": money(f["cash_received"]), "refunds_paid": money(f["refunds_paid"]), "net_cash": money(net_cash),
            "opening": {k: money(a[k]) for k in ("ar_owed", "customer_credit", "ar_net", "deferred", "unbilled", "unapplied")},
            "closing": {k: money(b[k]) for k in ("ar_owed", "customer_credit", "ar_net", "deferred", "unbilled", "unapplied")},
            "checks": checks,
        }
    controls = None
    if "bank" in P["tables"]:
        g = P["g13"]
        try:
            brows, brej, bf = g.read_table(P["tables"]["bank"], P["tz"])
        except g.Invalid as e:
            raise Invalid(str(e)) from None
        facts.append({"file": bf["file"], "sha256": bf["sha256"], "data_rows": bf["data_rows"], "ignored_columns": bf["ignored_columns"]})
        for r in brej:
            exc["rejected"].append(dict(r, table="bank"))
        bank: Dict[str, Dict[str, Decimal]] = {}
        dup_cur = []
        for r in brows:
            if r.get("currency") is None or r.get("cash_in") is None or r.get("cash_out") is None:
                exc["rejected"].append({"table": "bank", "file": bf["file"], "line": r["_line"], "reason": "missing_value", "detail": "currency,cash_in,cash_out"})
                continue
            if r["currency"] in bank:
                dup_cur.append(r["currency"])
            bank[r["currency"]] = {"cash_in": r["cash_in"], "cash_out": r["cash_out"]}
        controls = {}
        for cur in sorted(set(bank) | set(currencies)):
            have = currencies.get(cur)
            bk = bank.get(cur)
            rec_in = Decimal(have["cash_received"]) if have else ZERO
            rec_out = Decimal(have["refunds_paid"]) if have else ZERO
            if cur in dup_cur:
                controls[cur] = {"ok": False, "detail": "bank file lists this currency more than once"}
            elif bk is None:
                controls[cur] = {"ok": rec_in == 0 and rec_out == 0, "detail": "no bank line for this currency",
                                 "ledger_cash_in": money(rec_in), "ledger_cash_out": money(rec_out)}
            else:
                controls[cur] = {"ok": bk["cash_in"] == rec_in and bk["cash_out"] == rec_out,
                                 "bank_cash_in": money(bk["cash_in"]), "ledger_cash_in": money(rec_in), "difference_in": money(bk["cash_in"] - rec_in),
                                 "bank_cash_out": money(bk["cash_out"]), "ledger_cash_out": money(rec_out), "difference_out": money(bk["cash_out"] - rec_out)}
    excluded = exc.pop("_excluded")
    dups = exc.pop("_duplicates")
    for k in exc:
        exc[k].sort(key=lambda x: json.dumps(x, sort_keys=True, default=str))
    clean = not any(exc[k] for k in ("rejected", "late", "no_loaded_at", "conflicting_versions", "unapplied", "unlinked_credits", "undelivered")) \
        and all_ok and (controls is None or all(c["ok"] for c in controls.values()))
    rep = {"schema": REPORT_SCHEMA, "package_sha256": P["package_sha256"],
           "period": {"start": start.isoformat(), "end": end.isoformat()}, "as_of": P["as_of"].isoformat() if P["as_of"] else None,
           "currencies": currencies, "controls": controls, "exceptions": exc,
           "counts": {"invoices_used": len(inv), "void_invoices": len(void), "payments_used": len(pay), "credits_used": len(cred),
                      "exact_duplicates_collapsed": dups, "excluded_ids": sum(len(v) for v in excluded.values())},
           "deferred_after_period": deferred_items, "inputs": facts, "result": "reconciled" if clean else "reconciled_with_exceptions",
           "note": "currencies are never combined; no FX conversion is performed",
           "read_only": "local files only; nothing was posted, sent or changed"}
    return rep, 0 if clean else 1


def render(r: Dict[str, Any]) -> str:
    lines = [f"period {r['period']['start']} to {r['period']['end']}: {r['result']}"]
    for cur, c in r["currencies"].items():
        lines.append(f"  {cur}: revenue {c['recognized_revenue']}, net cash {c['net_cash']} (in {c['cash_received']}, refunds {c['refunds_paid']}), "
                     f"billed {c['billed']}, credit notes {c['credit_notes']}")
        lines.append(f"       closing AR {c['closing']['ar_net']} (owed {c['closing']['ar_owed']}, customer credit {c['closing']['customer_credit']}), "
                     f"deferred {c['closing']['deferred']}, unbilled {c['closing']['unbilled']}, unapplied cash {c['closing']['unapplied']}")
        bad = [k for k, v in c["checks"].items() if not v["ok"]]
        lines.append("       checks: " + ("all close" if not bad else "FAILED " + ", ".join(bad)))
    for cur, c in (r["controls"] or {}).items():
        lines.append(f"  bank control {cur}: {'ok' if c['ok'] else 'DIFFERENCE'}")
    for k, v in r["exceptions"].items():
        if v:
            lines.append(f"  {k}: {len(v)}")
    return "\n".join(lines) + "\n"


def _write_atomic(out: Path, data: bytes) -> None:
    out = out.resolve()
    fd, tmp = tempfile.mkstemp(prefix=".cash-revenue-", dir=str(out.parent))
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, str(out))
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="cash_revenue_reconcile.py", description="Recognized revenue versus cash, per currency.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("reconcile")
    r.add_argument("package")
    r.add_argument("--json", action="store_true")
    r.add_argument("--out")
    a = ap.parse_args(argv)
    try:
        rep, code = reconcile(a.package)
    except Invalid as exc:
        print(f"invalid: {exc}", file=sys.stderr)
        return 2
    data = (json.dumps(rep, sort_keys=True, indent=1) + "\n").encode()
    if a.out:
        _write_atomic(Path(a.out), data)
    sys.stdout.write(data.decode() if a.json else render(rep))
    return code


if __name__ == "__main__":
    sys.exit(main())
