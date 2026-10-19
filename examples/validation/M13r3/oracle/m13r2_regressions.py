#!/usr/bin/env python3
"""M13 r2 regression hunt: the G13 r2 tool (NEW) against the r1 tool (OLD, 7da20d4) on cases near the r2 fixes.
Usage: python m13r2_regressions.py PY NEW_csv_reconcile.py OLD_csv_reconcile.py
Synthetic data only; runs offline in a temp folder. Prints exit, status, revenue, orders, gaps and reject reasons."""
import json, os, subprocess, sys, tempfile
from pathlib import Path

PY, NEW, OLD = sys.argv[1:4]
COLS = {"order_id": "str", "amount": "decimal", "currency": "str", "status": "str",
        "event_time": "timestamp", "loaded_at": "timestamp", "updated_at": "timestamp"}


def contract(tz="UTC", as_of=None, window=("2026-09-01T00:00:00Z", "2026-10-01T00:00:00Z"), policy="latest:updated_at"):
    c = {"schema": "solaris.csv-reconcile/1", "timezone": tz,
         "facts": {"file": "orders.csv", "grain": ["order_id"], "columns": COLS, "required": ["amount", "currency", "event_time"],
                   "uppercase": ["currency"], "duplicate_policy": policy, "status_column": "status",
                   "exclude_status": ["void"], "loaded_at_column": "loaded_at"},
         "metrics": [{"name": "revenue", "agg": "sum", "column": "amount", "by": ["currency"]},
                     {"name": "orders", "agg": "count_distinct", "column": "order_id"}]}
    if as_of:
        c["as_of"] = as_of
    c["window"] = {"column": "event_time", "start": window[0], "end": window[1]}
    return c


def row(oid, amt, et, la="2026-09-15T00:00:00Z", up="2026-09-15T00:00:00Z", st="paid", cur="USD"):
    return [oid, amt, cur, st, et, la, up]


def run(tool, c, rows):
    with tempfile.TemporaryDirectory(prefix="m13r2-reg-") as d:
        Path(d, "contract.json").write_text(json.dumps(c))
        Path(d, "orders.csv").write_text("order_id,amount,currency,status,event_time,loaded_at,updated_at\n" +
                                         "".join(",".join(r) + "\n" for r in rows))
        p = subprocess.run([PY, tool, "reconcile", os.path.join(d, "contract.json"), "--json"], capture_output=True, text=True,
                           env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
        try:
            j = json.loads(p.stdout)
        except ValueError:
            return f"rc={p.returncode} unparsable: {(p.stdout + p.stderr)[-160:]!r}"
        if j.get("status") == "invalid":
            return f"rc={p.returncode} invalid: {j.get('error')}"
        m = j["metrics"]
        revs = {"/".join(g["group"].values()): g["value"] for g in m["revenue"]["groups"]}
        orders = [g["value"] for g in m["orders"]["groups"]]
        return f"rc={p.returncode} {j['status']} revenue={revs} orders={orders} gaps={j['gaps']} rejected={j['coverage']['rejected']}"


def case(title, c, rows):
    a, b = run(NEW, c, rows), run(OLD, c, rows)
    print(f"[{title}]\n    r2 {a}\n    r1 {b}" + ("" if a != b else "\n    (same)"))


base = [row("O1", "100.00", "2026-09-10T12:00:00Z"), row("O2", "50.00", "2026-09-11T12:00:00Z")]
print("RT timestamp spellings that common exports write (one extra row O3 USD 4.00 with this event_time)")
for label, ts in (("PostgreSQL timestamptz text (+00)", "2026-09-12 12:00:00+00"),
                  ("PostgreSQL with fraction (+00)", "2026-09-12 12:00:00.123456+00"),
                  ("PostgreSQL non-UTC session (+05:30)", "2026-09-12 12:00:00+05:30"),
                  ("PostgreSQL hour offset (-07)", "2026-09-12 05:00:00-07"),
                  ("SQL Server datetime2(7)", "2026-09-12 12:00:00.1234567"),
                  ("SQL Server datetimeoffset(7)", "2026-09-12 12:00:00.1234567 +00:00"),
                  ("ISO basic offset (-0700)", "2026-09-12T05:00:00-0700"),
                  ("MySQL DATETIME (naive)", "2026-09-12 12:00:00"),
                  ("JavaScript toISOString", "2026-09-12T12:00:00.000Z"),
                  ("Go RFC3339Nano", "2026-09-12T12:00:00.123456789Z")):
    case(f"RT {label}: {ts}", contract(), base + [row("O3", "4.00", ts)])

print("RD date-only and midnight wall times where midnight does not exist (America/Santiago, DST start 2026-09-06 00:00)")
case("RD fact row event_time 2026-09-06 (date only)", contract(tz="America/Santiago"),
     base + [row("O3", "4.00", "2026-09-06", la="2026-09-15", up="2026-09-15")])
case("RD window start 2026-09-06 (date only, contract)", contract(tz="America/Santiago", window=("2026-09-06", "2026-10-01")),
     [row("O1", "100.00", "2026-09-10T12:00:00Z")])
case("RD control: America/Los_Angeles date 2026-09-06", contract(tz="America/Los_Angeles"),
     base + [row("O3", "4.00", "2026-09-06", la="2026-09-15", up="2026-09-15")])

print("RN interactions of the N1/N3/N8 fixes")
case("RN re-delivery identical but loaded_at, both on time (N3)", contract(as_of="2026-10-02T00:00:00Z"),
     base + [row("O2", "50.00", "2026-09-11T12:00:00Z", la="2026-09-16T00:00:00Z")])
case("RN re-delivery: first copy loaded late, second on time", contract(as_of="2026-10-02T00:00:00Z"),
     [row("O1", "100.00", "2026-09-10T12:00:00Z"), row("O2", "50.00", "2026-09-11T12:00:00Z", la="2026-10-05T00:00:00Z"),
      row("O2", "50.00", "2026-09-11T12:00:00Z", la="2026-09-16T00:00:00Z")])
case("RN no as_of, copy with blank loaded_at (N1 must not apply)", contract(),
     base + [row("O2", "50.00", "2026-09-11T12:00:00Z", la="")])
case("RN latest:loaded_at policy, versions differ in amount", contract(policy="latest:loaded_at"),
     [row("O1", "100.00", "2026-09-10T12:00:00Z"), row("O1", "120.00", "2026-09-10T12:00:00Z", la="2026-09-20T00:00:00Z")])
case("RN latest:loaded_at policy, versions identical except loaded_at", contract(policy="latest:loaded_at"),
     [row("O1", "100.00", "2026-09-10T12:00:00Z"), row("O1", "100.00", "2026-09-10T12:00:00Z", la="2026-09-20T00:00:00Z")])
case("RN as_of, newer version loaded_at blank, older on time (N1)", contract(as_of="2026-10-02T00:00:00Z"),
     base + [row("O2", "75.00", "2026-09-11T12:00:00Z", la="", up="2026-09-20T00:00:00Z")])
case("RN void re-delivery differing only in loaded_at and status", contract(),
     base + [row("O2", "50.00", "2026-09-11T12:00:00Z", la="2026-09-16T00:00:00Z", st="void")])

print("RW write path (N4)")
for title, setup in (("RW --out over an existing report, --rejects new", "existing"), ("RW --out into a read-only folder", "ro")):
    for name, tool in (("r2", NEW), ("r1", OLD)):
        with tempfile.TemporaryDirectory(prefix="m13r2-reg-") as d:
            Path(d, "contract.json").write_text(json.dumps(contract()))
            Path(d, "orders.csv").write_text("order_id,amount,currency,status,event_time,loaded_at,updated_at\n" +
                                             "".join(",".join(r) + "\n" for r in base + [row("O9", "x", "2026-09-12T00:00:00Z")]))
            out = Path(d, "out"); out.mkdir()
            if setup == "existing":
                Path(out, "report.json").write_text("old\n")
            else:
                out.chmod(0o555)
            p = subprocess.run([PY, tool, "reconcile", os.path.join(d, "contract.json"), "--json", "--out", str(out / "report.json"),
                                "--rejects", os.path.join(d, "rejects.csv")], capture_output=True, text=True)
            left = sorted(x.name for x in out.iterdir()) + sorted(x.name for x in Path(d).iterdir() if x.name.startswith("."))
            rej = Path(d, "rejects.csv").exists()
            out.chmod(0o755)
            print(f"[{title}] {name} rc={p.returncode} files in out/ and hidden in folder: {left} rejects.csv written: {rej}")
