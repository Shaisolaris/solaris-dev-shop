#!/usr/bin/env python3
"""M13 r3 probes (Grok self-validation) for the G13 r3 fixes RT (timestamp spellings) and RD (date-only on midnight DST days).
Usage: python m13r3_probes.py PY TOOL [OLD_TOOL]
v2: v1 had two harness errors (rejected compared to an int, not the reason map; a wrong hand value for
Santiago 2026-04-05, checked against zoneinfo). Every expected instant below is written by hand from the spelling (not computed with the tool's parser). An accepted spelling
is checked to the microsecond: the row must be excluded by a window ending exactly at its instant and included by a window
ending 1 microsecond later. Synthetic data only; offline; temp folders."""
import datetime as _dt, json, os, subprocess, sys, tempfile
from pathlib import Path

PY, TOOL = sys.argv[1:3]
OLD = sys.argv[3] if len(sys.argv) > 3 else None
COLS = {"order_id": "str", "amount": "decimal", "currency": "str", "status": "str",
        "event_time": "timestamp", "loaded_at": "timestamp", "updated_at": "timestamp"}
fails = []


def contract(tz="UTC", start="2026-09-01T00:00:00Z", end="2026-10-01T00:00:00Z", as_of=None):
    c = {"schema": "solaris.csv-reconcile/1", "timezone": tz,
         "facts": {"file": "orders.csv", "grain": ["order_id"], "columns": COLS, "required": ["amount", "currency", "event_time"],
                   "uppercase": ["currency"], "duplicate_policy": "latest:updated_at", "status_column": "status",
                   "exclude_status": ["void"], "loaded_at_column": "loaded_at"},
         "metrics": [{"name": "revenue", "agg": "sum", "column": "amount", "by": ["currency"]}],
         "window": {"column": "event_time", "start": start, "end": end}}
    if as_of:
        c["as_of"] = as_of
    return c


def row(oid, amt, et, la="2026-09-15T00:00:00Z", up="2026-09-15T00:00:00Z"):
    return [oid, amt, "USD", "paid", et, la, up]


def run(c, rows, tool=None):
    with tempfile.TemporaryDirectory(prefix="m13r3-pr-") as d:
        Path(d, "contract.json").write_text(json.dumps(c))
        with open(Path(d, "orders.csv"), "w", newline="", encoding="utf-8") as f:
            f.write("order_id,amount,currency,status,event_time,loaded_at,updated_at\n" + "".join(",".join(r) + "\n" for r in rows))
        p = subprocess.run([PY, tool or TOOL, "reconcile", os.path.join(d, "contract.json"), "--json"], capture_output=True,
                           text=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
        if "Traceback" in p.stderr:
            return {"rc": p.returncode, "tb": p.stderr[-200:]}
        try:
            j = json.loads(p.stdout)
        except ValueError:
            return {"rc": p.returncode, "raw": (p.stdout + p.stderr)[-160:]}
        if j.get("status") == "invalid":
            return {"rc": p.returncode, "invalid": j.get("error")}
        revs = {"/".join(g["group"].values()): g["value"] for g in j["metrics"]["revenue"]["groups"]}
        return {"rc": p.returncode, "usd": revs.get("USD"), "gaps": j["gaps"], "rejected": j["coverage"]["rejected"]}


def check(name, ok, got, extra=""):
    print(f"{'PASS' if ok else 'FAIL'} {name}: {got}{extra}")
    if not ok:
        fails.append(name)


base = [row("O1", "100.00", "2026-09-10T12:00:00Z"), row("O2", "50.00", "2026-09-11T12:00:00Z")]
num = lambda r: float(r["usd"]) if r.get("usd") is not None else None

print("== p01 RT accepted spellings, each checked to the microsecond (row O3 USD 4.00; window end at its instant, then +1us)")
ACC = [  # spelling, true instant truncated to the microsecond (UTC, written by hand), instant + 1 us
    ("2026-09-12 12:00:00+00", "2026-09-12T12:00:00Z", "2026-09-12T12:00:00.000001Z"),
    ("2026-09-12 12:00:00.123456+00", "2026-09-12T12:00:00.123456Z", "2026-09-12T12:00:00.123457Z"),
    ("2026-09-12 05:00:00-07", "2026-09-12T12:00:00Z", "2026-09-12T12:00:00.000001Z"),
    ("2026-09-12 05:00:00.5-07", "2026-09-12T12:00:00.500000Z", "2026-09-12T12:00:00.500001Z"),
    ("2026-09-12 17:30:00+05:30", "2026-09-12T12:00:00Z", "2026-09-12T12:00:00.000001Z"),
    ("2026-09-12T17:30:00+0530", "2026-09-12T12:00:00Z", "2026-09-12T12:00:00.000001Z"),
    ("2026-09-12T05:00:00-0700", "2026-09-12T12:00:00Z", "2026-09-12T12:00:00.000001Z"),
    ("2026-09-12 12:00:00.1234567 +00:00", "2026-09-12T12:00:00.123456Z", "2026-09-12T12:00:00.123457Z"),
    ("2026-09-12 05:00:00.9999999 -07:00", "2026-09-12T12:00:00.999999Z", "2026-09-12T12:00:01Z"),
    ("2026-09-12T12:00:00.123456789Z", "2026-09-12T12:00:00.123456Z", "2026-09-12T12:00:00.123457Z"),
    ("2026-09-12T12:00:00.000000999Z", "2026-09-12T12:00:00Z", "2026-09-12T12:00:00.000001Z"),
    ("2026-09-12 12:00:00.1234567", "2026-09-12T12:00:00.123456Z", "2026-09-12T12:00:00.123457Z"),
    ("2026-09-12t12:00z", "2026-09-12T12:00:00Z", "2026-09-12T12:00:00.000001Z"),
    ("2026-09-12 12:00 -07", "2026-09-12T19:00:00Z", "2026-09-12T19:00:00.000001Z"),
    ("2026-09-13 11:59:00+23:59", "2026-09-12T12:00:00Z", "2026-09-12T12:00:00.000001Z"),
    ("2026-09-11 12:01:00-23:59", "2026-09-12T12:00:00Z", "2026-09-12T12:00:00.000001Z"),
    ("2026-09-12 12:00:00-00", "2026-09-12T12:00:00Z", "2026-09-12T12:00:00.000001Z"),
]
for s, inst, nxt in ACC:
    a = run(contract(end=inst), base + [row("O3", "4.00", s)])
    b = run(contract(end=nxt), base + [row("O3", "4.00", s)])
    check(f"p01 {s!r} == {inst}", num(a) == 150.0 and num(b) == 154.0 and a["rc"] == 0 and b["rc"] == 0,
          f"end=instant usd={a.get('usd')} rc={a['rc']}; end=+1us usd={b.get('usd')} rc={b['rc']}")

print("== p02 RT refused spellings (expect exit 1, USD 150.00, rejected == {bad_timestamp: 1})")
REF = ["2026-09-12T12:00:00.1234567890Z", "2026-09-12 12:00:00+0", "2026-09-12 12:00:00+000", "2026-09-12 12:00:00+05:60",
       "2026-09-12 12:00:00+0560", "2026-09-12 12:00:00+24:00", "2026-09-12 12:00:00+24", "2026-09-12 12:00:00 Z",
       "2026-09-12 12:00:00  +00", "2026-09-12 12:00:00.Z", "2026-09-12 12:00:00.+00", "2026-09-12 12:00:00+05:3",
       "2026-09-12 12:00:00+5", "2026-09-12 12:00:00+05:30:00", "2026-09-12 12:00:00+05:", "2026-09-12 12:00:00.\u0661\u0662Z",
       "2026-09-12 12:00:00+\uff10\uff10", "2026-09-12 12:00:00 +0", "2026-09-12 12:00:00+00:00Z", "20260912T120000Z",
       "2026-W37-6", "2026-09-12 24:00:00Z", "2026-09-12 12:00:60Z", "2026-09-12 12:00:00 UTC", "2026-09-12T12Z"]
for s in REF:
    r = run(contract(), base + [row("O3", "4.00", s)])
    check(f"p02 refused {s!r}", r["rc"] == 1 and num(r) == 150.0 and r.get("rejected") == {"bad_timestamp": 1}, r)

print("== p03 documented limit: digits past the sixth are dropped; consequences at contract bounds with sub-microsecond digits")
r = run(contract(end="2026-09-12T12:00:00.0000005Z"), base + [row("O3", "4.00", "2026-09-12T12:00:00.0000001Z")])
print(f"OBS p03a window end .0000005Z, row .0000001Z (truly inside the window): usd={r.get('usd')} rc={r['rc']} (154.00 is exact)")
r = run(contract(start="2026-09-12T12:00:00.0000005Z"), [row("O3", "4.00", "2026-09-12T12:00:00.0000001Z"), row("O4", "1.00", "2026-09-20T00:00:00Z")])
print(f"OBS p03b window start .0000005Z, row .0000001Z (truly before the window): usd={r.get('usd')} rc={r['rc']} (1.00 is exact)")
r = run(contract(as_of="2026-10-02T00:00:00.0000001Z"), base + [row("O3", "4.00", "2026-09-12T12:00:00Z", la="2026-10-02T00:00:00.0000009Z")])
print(f"OBS p03c as_of .0000001Z, loaded_at .0000009Z (truly late): usd={r.get('usd')} gaps={r.get('gaps')} rc={r['rc']} (150.00 with late_rows is exact)")
r = run(contract(), base + [row("O3", "4.00", "2026-09-12T12:00:00Z", up="2026-09-15T00:00:00.0000001Z"),
                            row("O3", "5.00", "2026-09-12T12:00:00Z", up="2026-09-15T00:00:00.0000002Z")])
print(f"OBS p03d two versions whose updated_at differ only in the 7th digit: usd={r.get('usd')} gaps={r.get('gaps')} rc={r['rc']} (loud tie expected per doc)")

print("== p04 RD date-only values on midnight DST days (expected first instant written by hand)")
RD = [("America/Santiago", "2026-09-06", "2026-09-06T04:00:00Z", "midnight spring-forward 00:00 -> 01:00 (-04 -> -03)"),
      ("America/Havana", "2026-11-01", "2026-11-01T04:00:00Z", "midnight fall-back 01:00 -> 00:00 (-04 -> -05), first midnight"),
      ("Asia/Beirut", "2026-03-29", "2026-03-28T22:00:00Z", "midnight spring-forward 00:00 -> 01:00 (+02 -> +03)"),
      ("Asia/Beirut", "2026-10-25", "2026-10-24T22:00:00Z", "fall-back 00:00 -> 23:00 the day before; 00:00 +02 happens once"),
      ("America/Santiago", "2026-04-05", "2026-04-05T04:00:00Z", "fall-back at 03:00 UTC (00:00 -03 -> 23:00 -04 the day before); 00:00 -04 happens once"),
      ("America/Los_Angeles", "2026-09-06", "2026-09-06T07:00:00Z", "control, no transition"),
      ("America/Los_Angeles", "2026-03-08", "2026-03-08T08:00:00Z", "control, 02:00 transition, midnight unaffected")]
for tz, day, inst, why in RD:
    nxt = inst.replace(":00Z", ":00.000001Z")
    a = run(contract(tz=tz, start="2026-01-01T00:00:00Z", end=inst), [row("O3", "4.00", day, la="2026-09-15", up="2026-09-15"), row("O1", "1.00", "2026-01-02T00:00:00Z")])
    b = run(contract(tz=tz, start="2026-01-01T00:00:00Z", end=nxt), [row("O3", "4.00", day, la="2026-09-15", up="2026-09-15"), row("O1", "1.00", "2026-01-02T00:00:00Z")])
    check(f"p04 row {tz} {day} == {inst} ({why})", num(a) == 1.0 and num(b) == 5.0, f"end=instant usd={a.get('usd')} rc={a['rc']}; +1us usd={b.get('usd')} rc={b['rc']}")
    # contract window start = the date-only day: a row at the first instant is inside, a row 1 us before is outside
    w_in = run(contract(tz=tz, start=day, end="2027-01-01T00:00:00Z"), [row("O3", "4.00", inst)])
    one_before = (_dt.datetime.strptime(inst, "%Y-%m-%dT%H:%M:%SZ") - _dt.timedelta(microseconds=1)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    w_out = run(contract(tz=tz, start=day, end="2027-01-01T00:00:00Z"), [row("O3", "4.00", one_before), row("O4", "2.00", "2026-12-01T00:00:00Z")])
    check(f"p04 window start {tz} {day} == {inst}", num(w_in) == 4.0 and num(w_out) == 2.0 and "invalid" not in w_in,
          f"row at instant usd={w_in.get('usd', w_in)}; row 1us before usd={w_out.get('usd', w_out)}")

print("== p05 RD scope: clock times in a gap or repeat are still refused (N6 kept)")
for tz, s, why in (("America/Santiago", "2026-09-06 00:30", "nonexistent_local_time"), ("America/Havana", "2026-11-01 00:30", "ambiguous_local_time"),
                   ("Asia/Beirut", "2026-10-24 23:30", "ambiguous_local_time"), ("America/Santiago", "2026-09-06 00:00", "nonexistent_local_time")):
    r = run(contract(tz=tz), base + [row("O3", "4.00", s, la="2026-09-15", up="2026-09-15")])
    check(f"p05 {tz} {s!r} refused", r["rc"] == 1 and num(r) == 150.0 and r.get("rejected") == {why: 1}, r, f" (expect {why})")
r = run(contract(tz="America/Santiago", start="2026-09-06 00:00", end="2026-10-01"), base)
check("p05 contract window start '2026-09-06 00:00' Santiago (clock time in the gap) invalid", "invalid" in r and r["rc"] == 2, r)

print("== p06 observation: a calendar day that never existed (Pacific/Apia skipped 2011-12-30)")
r = run(contract(tz="Pacific/Apia", start="2011-12-29T00:00:00Z", end="2011-12-30T10:00:00Z"), [row("O3", "4.00", "2011-12-30"), row("O1", "1.00", "2011-12-29T12:00:00Z")])
r2 = run(contract(tz="Pacific/Apia", start="2011-12-29T00:00:00Z", end="2011-12-30T10:00:00.000001Z"), [row("O3", "4.00", "2011-12-30"), row("O1", "1.00", "2011-12-29T12:00:00Z")])
print(f"OBS p06 '2011-12-30' in Pacific/Apia (no such local day): end=10:00Z usd={r.get('usd', r)}; end=+1us usd={r2.get('usd', r2)} (5.00 at +1us means read as 2011-12-30T10:00Z = 2011-12-31 00:00 local)")

if OLD:
    print("== p07 r2 tool on the same p01 spellings (for comparison only)")
    acc_old = sum(1 for s, inst, nxt in ACC if num(run(contract(end=nxt), base + [row("O3", "4.00", s)], OLD)) == 154.0)
    print(f"r2 tool accepts {acc_old}/{len(ACC)} p01 spellings at the right instant")
print(f"SUMMARY {'OK' if not fails else 'FAIL'} failures={len(fails)} {fails}")
