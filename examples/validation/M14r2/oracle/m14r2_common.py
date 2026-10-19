# M14 r2 helpers (Grok self-validation): package writer and runner, same layout as the M14 oracle (v3), copied here so
# the r2 oracle does not import a module that runs on import.
import csv, io, json, subprocess, sys
from datetime import datetime, timezone
S = datetime(2026, 7, 1, tzinfo=timezone.utc); E = datetime(2026, 8, 1, tzinfo=timezone.utc); ASOF = datetime(2026, 8, 6, tzinfo=timezone.utc)
def iso(t): return t.strftime("%Y-%m-%dT%H:%M:%SZ") if t else ""
IH = ["invoice_id", "customer_id", "currency", "amount", "issued_at", "delivered_at", "status", "loaded_at"]
PH = ["payment_id", "invoice_id", "currency", "amount", "received_at", "loaded_at"]
CH = ["credit_id", "invoice_id", "kind", "currency", "amount", "issued_at", "loaded_at"]
ENV = {"PATH": "/usr/bin:/bin", "HOME": "/tmp", "PYTHONDONTWRITEBYTECODE": "1", "LC_ALL": "C"}
def write(d, inv, pay, cr):
    d.mkdir(parents=True, exist_ok=True)
    for name, h, rs in (("invoices.csv", IH, inv), ("payments.csv", PH, pay), ("credits.csv", CH, cr)):
        b = io.StringIO(); w = csv.writer(b, lineterminator="\n"); w.writerow(h); [w.writerow([r.get(k, "") for k in h]) for r in rs]; (d / name).write_text(b.getvalue())
    pk = {"schema": "solaris.cash-revenue/1", "timezone": "UTC", "period": {"start": iso(S), "end": iso(E)}, "as_of": iso(ASOF),
          "invoices": {"file": "invoices.csv"}, "payments": {"file": "payments.csv"}, "credits": {"file": "credits.csv"}}
    (d / "package.json").write_text(json.dumps(pk)); return d / "package.json"
def run(tool, p):
    cp = subprocess.run([sys.executable, str(tool), "reconcile", str(p), "--json"], cwd=p.parent, env=ENV, capture_output=True, text=True, timeout=300)
    try: rep = json.loads(cp.stdout)
    except Exception: rep = None
    return cp.returncode, rep, cp
L = "2026-08-05T00:00:00Z"
def inv(i, amt, issued="2026-07-02T00:00:00Z", deliv="2026-07-03T00:00:00Z", cur="USD", status="issued", loaded=L): return dict(invoice_id=i, customer_id="c-" + i, currency=cur, amount=amt, issued_at=issued, delivered_at=deliv, status=status, loaded_at=loaded)
def pay(p, i, amt, at="2026-07-10T00:00:00Z", cur="USD", loaded=L): return dict(payment_id=p, invoice_id=i, currency=cur, amount=amt, received_at=at, loaded_at=loaded)
def cr(c, i, kind, amt, at="2026-07-15T00:00:00Z", cur="USD", loaded=L): return dict(credit_id=c, invoice_id=i, kind=kind, currency=cur, amount=amt, issued_at=at, loaded_at=loaded)
