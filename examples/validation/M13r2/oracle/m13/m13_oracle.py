#!/usr/bin/env python3
"""M13 CSV-reconciliation oracle (written for M13; independent of the builder's reconcile_oracle.py
and tests, and of Muse's oracle). Derived from G13/M13 acceptance and csv-reconciliation.md:
exact metric and coverage, deterministic rerun, no silent imputation, no duplicate count, no fan-out,
no fictional warehouse, clean control, unseen failure and safe recovery, scale and concurrency.
Interface: <cmd> reconcile CONTRACT.json [--json] [--out REPORT] [--rejects REJECTS.csv]
           exit 0 reconciled, 1 reconciled_with_gaps, 2 invalid (nothing written)
Expected values are fixed by construction before any dirt is added. All data is synthetic.
Usage: python m13_oracle.py [--only K1,K5B] [--scale N] -- <candidate prefix...>"""
import copy, csv, io, json, os, random, shutil, subprocess, sys, tempfile, time
import concurrent.futures as cf
from decimal import Decimal as D
from pathlib import Path

HERE = Path(__file__).resolve().parent
CMD = []
HEADER = ["order_id", "customer_id", "amount", "currency", "status", "event_time", "loaded_at", "updated_at"]


class Fail(Exception):
    pass


def need(c, m):
    if not c:
        raise Fail(m)


def env(extra=None):
    e = {k: v for k, v in os.environ.items() if not k.startswith("M13_")}
    e["PYTHONDONTWRITEBYTECODE"] = "1"
    e.update(extra or {})
    return e


def contract(**over):
    c = {"schema": "solaris.csv-reconcile/1", "timezone": "America/Los_Angeles",
         "facts": {"file": "orders.csv", "grain": ["order_id"],
                   "columns": {"order_id": "str", "customer_id": "str", "amount": "decimal", "currency": "str",
                               "status": "str", "event_time": "timestamp", "loaded_at": "timestamp", "updated_at": "timestamp"},
                   "required": ["amount", "currency", "event_time"], "uppercase": ["currency"],
                   "thousands_separator": ",", "duplicate_policy": "latest:updated_at",
                   "status_column": "status", "exclude_status": ["test", "void"], "loaded_at_column": "loaded_at"},
         "dimension": {"file": "customers.csv", "key": "customer_id", "attributes": ["region"],
                       "columns": {"customer_id": "str", "region": "str"}, "duplicate_policy": "reject"},
         "window": {"column": "event_time", "start": "2026-09-01T00:00:00-07:00", "end": "2026-10-01T00:00:00-07:00"},
         "as_of": "2026-10-02T00:00:00Z",
         "metrics": [{"name": "revenue", "agg": "sum", "column": "amount", "by": ["currency"]},
                     {"name": "orders", "agg": "count_distinct", "column": "order_id", "by": []},
                     {"name": "buyers", "agg": "count_distinct", "column": "customer_id", "by": []},
                     {"name": "by_region", "agg": "sum", "column": "amount", "by": ["region"]}]}
    for k, v in over.items():
        if k.startswith("facts_"):
            c["facts"][k[6:]] = v
        else:
            c[k] = v
    return c


def o(i, cust="C1", amt="10.00", cur="USD", st="paid", ev="2026-09-10T12:00:00Z", la="2026-09-10T13:00:00Z", up="2026-09-10T12:00:00Z"):
    return [i, cust, amt, cur, st, ev, la, up]


BASE = [o("O1", "C1", "100.00"), o("O2", "C2", "50.00"), o("O3", "C3", "30.00", "EUR")]
CUST = [["C1", "west"], ["C2", "east"], ["C3", "west"]]


def csv_text(header, rows):
    b = io.StringIO()
    w = csv.writer(b, lineterminator="\n")
    w.writerow(header)
    for r in rows:
        if isinstance(r, str):
            b.write(r + "\n")
        else:
            w.writerow(r)
    return b.getvalue()


class Work:
    def __init__(self, root):
        self.root = Path(root)
        self.n = 0

    def case(self, rows, cust=CUST, c=None, header=HEADER, control=None):
        self.n += 1
        d = self.root / f"c{self.n:03d}"
        d.mkdir(parents=True)
        (d / "orders.csv").write_text(csv_text(header, rows))
        (d / "customers.csv").write_text(csv_text(["customer_id", "region"], cust))
        c = copy.deepcopy(c or contract())
        if control is not None:
            (d / "control.csv").write_text(csv_text(["file", "rows", "sum"], [control]))
            c["controls"] = {"file": "control.csv", "sum_column": "amount"}
        (d / "contract.json").write_text(json.dumps(c, indent=1))
        return d

    def run(self, d, *extra, e=None, timeout=300):
        p = subprocess.run(CMD + ["reconcile", str(d / "contract.json"), "--json", *extra], capture_output=True,
                           text=True, env=env(e), timeout=timeout)
        try:
            rep = json.loads(p.stdout)
        except ValueError:
            rep = {}
        return p.returncode, rep, p


def rev(rep, name="revenue", key="currency"):
    out = {}
    for g in rep.get("metrics", {}).get(name, {}).get("groups", []):
        out[g["group"].get(key, "all") if key else "all"] = None if g["value"] is None else D(str(g["value"]))
    return out


def scalar(rep, name):
    g = rep.get("metrics", {}).get(name, {}).get("groups", [])
    return g[0]["value"] if len(g) == 1 else None


def cov(rep):
    return rep.get("coverage", {})


def dec(d):
    return {k: D(v) for k, v in d.items()}


# expectation: (label, rows, cust, contract, exit, revenue, orders, buyers, region, buckets, gaps_must, gaps_must_not)
def expect(w, label, rows, exit_, revenue, orders, buckets=None, cust=CUST, c=None, gaps=(), region=None, buyers=None, header=HEADER):
    d = w.case(rows, cust, c, header)
    rc, rep, p = w.run(d)
    bad = []
    if rc != exit_:
        bad.append(f"exit {rc} (want {exit_}) {p.stdout[:120]!r}")
    if rev(rep) != dec(revenue):
        bad.append(f"revenue {rev(rep)} (want {revenue})")
    if scalar(rep, "orders") != orders:
        bad.append(f"orders {scalar(rep, 'orders')} (want {orders})")
    if buyers is not None and scalar(rep, "buyers") != buyers:
        bad.append(f"buyers {scalar(rep, 'buyers')} (want {buyers})")
    if region is not None and rev(rep, "by_region", "region") != dec(region):
        bad.append(f"by_region {rev(rep, 'by_region', 'region')} (want {region})")
    cv = cov(rep)
    for path, want in (buckets or {}).items():
        v = cv
        for part in path.split("."):
            v = v.get(part, 0) if isinstance(v, dict) else None
        if v != want:
            bad.append(f"coverage.{path}={v} (want {want})")
    if cv and not cv.get("all_rows_accounted"):
        bad.append("not all rows accounted")
    for g in gaps:
        if g not in rep.get("gaps", []):
            bad.append(f"gap {g} missing from {rep.get('gaps')}")
    if exit_ == 0 and rep.get("gaps"):
        bad.append(f"unexpected gaps {rep.get('gaps')}")
    # segments add back to the headline
    if rep.get("metrics"):
        tot = sum((v for v in rev(rep).values() if v is not None), D(0))
        seg = sum((v for v in rev(rep, "by_region", "region").values() if v is not None), D(0))
        if tot != seg:
            bad.append(f"segments {seg} != total {tot}")
    return [f"{label}: " + "; ".join(bad)] if bad else []


def k1_clean_control(w):
    bad = expect(w, "clean", BASE, 0, {"USD": "150.00", "EUR": "30.00"}, 3, {"rows_read": 3, "included": 3},
                 region={"west": "130.00", "east": "50.00"}, buyers=3)
    d = w.case(BASE)
    rc, rep, _ = w.run(d)
    nv = rep.get("naive_comparison", {})
    need(dec(nv.get("sum_every_parsed_row", {})) == dec({"USD": "150.00", "EUR": "30.00"}), f"clean: naive sum {nv.get('sum_every_parsed_row')} should equal reconciled")
    need("warehouse" in rep.get("execution", "") and "none" in rep.get("imputation", ""), "clean: execution/imputation statements missing")
    need(not bad, "; ".join(bad))
    return "clean control: exit 0, exact totals, naive equals reconciled, execution and imputation stated"


SINGLE = [
    ("exact copy (100.0 vs 100.00, usd vs USD)", BASE + [o("O1", "C1", "100.0", "usd")], 0, {"USD": "150.00", "EUR": "30.00"}, 3, {"duplicates.exact_copies": 1}, ()),
    ("superseded version", BASE + [o("O2", "C2", "55.00", up="2026-09-11T00:00:00Z")], 0, {"USD": "155.00", "EUR": "30.00"}, 3, {"duplicates.superseded_versions": 1}, ()),
    ("tie unresolved", BASE + [o("O2", "C2", "55.00")], 1, {"USD": "100.00", "EUR": "30.00"}, 2, {"duplicates.rows_unresolved": 2, "duplicates.keys_unresolved": 1}, ("unresolved_duplicates",)),
    ("newer void cancels", BASE + [o("O2", "C2", "50.00", st="void", up="2026-09-11T00:00:00Z")], 0, {"USD": "100.00", "EUR": "30.00"}, 2, {"excluded_status": 1, "duplicates.superseded_versions": 1}, ()),
    ("missing amount", BASE + [o("O4", amt="")], 1, {"USD": "150.00", "EUR": "30.00"}, 3, {"missing_required.amount": 1}, ("missing_required",)),
    ("bad decimal 12..5", BASE + [o("O4", amt="12..5")], 1, {"USD": "150.00", "EUR": "30.00"}, 3, {"rejected.bad_decimal": 1}, ("rejected_rows",)),
    ("bad timestamp", BASE + [o("O4", ev="not-a-time")], 1, {"USD": "150.00", "EUR": "30.00"}, 3, {"rejected.bad_timestamp": 1}, ("rejected_rows",)),
    ("field count", BASE + ["O4,C1,1.00,USD,paid,2026-09-10T12:00:00Z,2026-09-10T13:00:00Z,2026-09-10T12:00:00Z,extra"], 1, {"USD": "150.00", "EUR": "30.00"}, 3, {"rejected.field_count": 1}, ("rejected_rows",)),
    ("grain missing", BASE + [o("", amt="9.00")], 1, {"USD": "150.00", "EUR": "30.00"}, 3, {"missing_required.order_id": 1}, ("missing_required",)),
    ("late row", BASE + [o("O4", amt="4.00", la="2026-10-03T00:00:00Z")], 1, {"USD": "150.00", "EUR": "30.00"}, 3, {"late_after_as_of": 1}, ("late_rows",)),
    ("late newer version keeps the older", BASE + [o("O2", "C2", "99.00", la="2026-10-03T00:00:00Z", up="2026-09-20T00:00:00Z")], 1, {"USD": "150.00", "EUR": "30.00"}, 3, {"late_after_as_of": 1, "duplicates.superseded_versions": 0}, ("late_rows",)),
    ("loaded exactly at as_of is in", BASE + [o("O4", amt="5.00", la="2026-10-02T00:00:00Z")], 0, {"USD": "155.00", "EUR": "30.00"}, 4, {"late_after_as_of": 0}, ()),
    ("test status", BASE + [o("O4", amt="4.00", st="test")], 0, {"USD": "150.00", "EUR": "30.00"}, 3, {"excluded_status": 1}, ()),
    ("window half-open in contract zone", BASE + [o("O4", amt="4.00", ev="2026-10-01T07:00:00Z"), o("O5", amt="7.00", ev="2026-09-01T07:00:00Z")], 0, {"USD": "157.00", "EUR": "30.00"}, 4, {"outside_window": 1}, ()),
    ("naive times read in contract zone", BASE + [o("O5", amt="3.00", ev="2026-09-01 00:30:00"), o("O6", amt="6.00", ev="2026-10-01 01:00:00")], 0, {"USD": "153.00", "EUR": "30.00"}, 4, {"outside_window": 1}, ()),
    ("thousands strict", BASE + [o("O4", amt="1,234.50"), o("O5", amt="1,23.00")], 1, {"USD": "1384.50", "EUR": "30.00"}, 4, {"rejected.bad_decimal": 1}, ("rejected_rows",)),
    ("newer version missing amount not papered", BASE + [o("O2", "C2", "", up="2026-09-11T00:00:00Z")], 1, {"USD": "100.00", "EUR": "30.00"}, 2, {"missing_required.amount": 1, "duplicates.superseded_versions": 1}, ("missing_required",)),
    ("count_distinct buyers", BASE + [o("O4", "C1", "1.00")], 0, {"USD": "151.00", "EUR": "30.00"}, 4, {}, ()),
    ("exact decimal sum", BASE + [o(f"P{i}", amt="0.10") for i in range(10)], 0, {"USD": "151.00", "EUR": "30.00"}, 13, {}, ()),
    ("21 integer digits refused", BASE + [o("O4", amt="1" * 21)], 1, {"USD": "150.00", "EUR": "30.00"}, 3, {"rejected.bad_decimal": 1}, ("rejected_rows",)),
]


def k2_single_dirt(w):
    bad = []
    for label, rows, ex, revenue, orders, buckets, gaps in SINGLE:
        bad += expect(w, label, rows, ex, revenue, orders, buckets, gaps=gaps, buyers=(3 if label == "count_distinct buyers" else None))
    c = contract(facts_required=["currency", "event_time"])
    c["metrics"].append({"name": "priced", "agg": "count", "column": "amount", "by": []})
    d = w.case(BASE + [o("O4", amt="")], c=c)
    rc, rep, _ = w.run(d)
    if not (rc == 1 and rev(rep) == dec({"USD": "150.00", "EUR": "30.00"}) and scalar(rep, "orders") == 4 and scalar(rep, "priced") == 3
            and rep["metrics"]["revenue"]["null_values_skipped"] == 1 and "null_metric_values" in rep.get("gaps", [])):
        bad.append(f"nullable amount: rc {rc} revenue {rev(rep)} orders {scalar(rep, 'orders')} gaps {rep.get('gaps')} "
                   f"nulls {rep.get('metrics', {}).get('revenue', {}).get('null_values_skipped')} priced {scalar(rep, 'priced')} (want 3)")
    need(not bad, "; ".join(bad))
    return f"{len(SINGLE)} single-dirt cases: exact totals, buckets, exit codes and gaps"


def k3_join(w):
    bad = []
    bad += expect(w, "orphan key", BASE + [o("O4", "C9", "4.00")], 1, {"USD": "154.00", "EUR": "30.00"}, 4,
                  gaps=("unmatched_or_missing_join_key",), region={"west": "130.00", "east": "50.00", "(unmatched)": "4.00"})
    bad += expect(w, "ambiguous dimension key", BASE, 1, {"USD": "150.00", "EUR": "30.00"}, 3, cust=CUST + [["C2", "north"]],
                  gaps=("ambiguous_dimension_key",), region={"west": "130.00", "(ambiguous)": "50.00"})
    bad += expect(w, "dimension exact copy no fan-out", BASE, 0, {"USD": "150.00", "EUR": "30.00"}, 3, cust=CUST + [["C1", "west"]],
                  region={"west": "130.00", "east": "50.00"})
    bad += expect(w, "missing fact key", BASE + [o("O4", "", "4.00")], 1, {"USD": "154.00", "EUR": "30.00"}, 4,
                  gaps=("unmatched_or_missing_join_key",), region={"west": "130.00", "east": "50.00", "(unmatched)": "4.00"})
    d = w.case(BASE + [o("O4", "C1", "1.00")], CUST + [["C1", "west"], ["C1", "west"]])
    rc, rep, _ = w.run(d)
    need(rev(rep, "by_region", "region").get("west") == D("131.00"), f"triple dimension copy fanned out: {rev(rep, 'by_region', 'region')}")
    need(not bad, "; ".join(bad))
    return "orphan, ambiguous, exact-copy and missing keys: segments add back, no fan-out"


def gen(seed, n, scale=False):
    """Truth first: n orders, then dirt with known effects. Returns rows, customers, expected."""
    rnd = random.Random(seed)
    custs = [[f"K{i}", rnd.choice(["west", "east", "north"])] for i in range(max(3, n // 10))]
    exp = {"USD": D(0), "EUR": D(0)}
    rows, orders = [], 0
    for i in range(n):
        amt = D(rnd.randint(1, 999999)) / 100
        cur = rnd.choice(["USD", "EUR"])
        ev = f"2026-09-{rnd.randint(2, 29):02d}T{rnd.randint(0, 23):02d}:{rnd.randint(0, 59):02d}:00Z"
        r = o(f"T{i}", rnd.choice(custs)[0], f"{amt:.2f}", cur.lower() if rnd.random() < .1 else cur, ev=ev, la="2026-09-30T00:00:00Z")
        kind = rnd.random()
        if kind < .05:  # superseded: an older version precedes the truth
            old = list(r)
            old[2], old[7] = f"{amt + 1:.2f}", "2026-09-01T00:00:00Z"
            rows.append(old)
            r[7] = "2026-09-15T00:00:00Z"
        rows.append(r)
        if kind > .95:  # exact copy, with a different spelling of the same amount
            c2 = list(r)
            c2[2] = f"{amt:.3f}"
            rows.append(c2)
        exp[cur] += amt
        orders += 1
    extra = 0
    for j in range(max(4, n // 25)):
        k = rnd.choice(["test", "late", "window", "bad", "missing", "orphan"])
        if k == "test":
            rows.append(o(f"X{j}", amt="5.00", st="test"))
        elif k == "late":
            rows.append(o(f"X{j}", amt="5.00", la="2026-10-05T00:00:00Z"))
        elif k == "window":
            rows.append(o(f"X{j}", amt="5.00", ev="2026-08-15T00:00:00Z"))
        elif k == "bad":
            rows.append(o(f"X{j}", amt="5.0.0"))
        elif k == "missing":
            rows.append(o(f"X{j}", amt=""))
        else:
            rows.append(o(f"X{j}", "NOPE", "5.00"))
            exp["USD"] += D("5.00")
            orders += 1
        extra += 1
    rnd.shuffle(rows)
    return rows, custs, {k: f"{v:.2f}" for k, v in exp.items()}, orders


def k4_seeded_unseen(w):
    bad = []
    for seed in (7, 1301, 90210):
        rows, custs, exp, orders = gen(seed, 400)
        d = w.case(rows, custs)
        rc, rep, _ = w.run(d)
        if rev(rep) != dec(exp) or scalar(rep, "orders") != orders or cov(rep).get("rows_read") != len(rows) or not cov(rep).get("all_rows_accounted"):
            bad.append(f"seed {seed}: revenue {rev(rep)} want {exp}; orders {scalar(rep, 'orders')} want {orders}; rows_read {cov(rep).get('rows_read')} want {len(rows)}")
    need(not bad, "; ".join(bad))
    return "3 seeded unseen datasets (truth built before dirt) reconcile exactly"


def k5a_as_of(w):
    # covered in SINGLE too; here: as_of in a non-UTC offset and lateness judged on loaded_at, not event_time
    c = contract(as_of="2026-10-01T17:00:00-07:00")
    bad = expect(w, "as_of with offset", BASE + [o("O4", amt="4.00", la="2026-10-02T00:00:00Z"), o("O5", amt="6.00", la="2026-10-02T00:00:01Z")],
                 1, {"USD": "154.00", "EUR": "30.00"}, 4, {"late_after_as_of": 1}, c=c, gaps=("late_rows",))
    need(not bad, "; ".join(bad))
    return "as_of compared as an instant on loaded_at"


def k5b_as_of_missing_loaded_at(w):
    """With an as_of cutoff, a row whose loaded_at is missing cannot be judged on time. Using it is
    an assumption (imputing loaded_at <= as_of); the run must not report a clean `reconciled`."""
    d = w.case(BASE + [o("O4", amt="4.00", la="")])
    rc, rep, _ = w.run(d)
    included = scalar(rep, "orders") == 4
    need(not (rc == 0 and rep.get("status") == "reconciled" and not rep.get("gaps")),
         f"row with no loaded_at under as_of: exit {rc}, status {rep.get('status')}, gaps {rep.get('gaps')}, included={included}, notes={rep.get('notes')}")
    return f"missing loaded_at under as_of is not reported clean (exit {rc}, gaps {rep.get('gaps')})"


def k6_deterministic(w):
    rows, custs, exp, orders = gen(42, 300)
    d = w.case(rows, custs)
    outs = []
    for e in ({}, {"PYTHONHASHSEED": "1", "TZ": "Asia/Tokyo"}, {"PYTHONHASHSEED": "987", "TZ": "UTC", "LC_ALL": "C"}):
        rc, rep, p = w.run(d, e=e)
        outs.append(p.stdout)
    need(len(set(outs)) == 1, "reruns under different PYTHONHASHSEED/TZ/locale differ")
    rnd = random.Random(5)
    sh = list(rows)
    rnd.shuffle(sh)
    d2 = w.case(sh, custs[::-1])
    rc2, rep2, _ = w.run(d2)
    rep1 = json.loads(outs[0])
    for name in rep1["metrics"]:
        k = rep1["metrics"][name]["by"][0] if rep1["metrics"][name]["by"] else None
        need(rev(rep1, name, k) == rev(rep2, name, k) if rep1["metrics"][name]["agg"] == "sum" else rep1["metrics"][name] == rep2["metrics"][name],
             f"shuffled rows change metric {name}")
    c1, c2 = dict(rep1["coverage"]), dict(rep2["coverage"])
    need(c1 == c2, f"shuffled rows change coverage: {c1} vs {c2}")
    return "3 reruns byte-identical; shuffled rows and dimension give numerically the same metrics and the same coverage"


def k6b_value_spelling_stable(w):
    """Exact copies may spell one amount two ways (10.50, 10.500). The reported total must not
    change its spelling with row order."""
    rows = BASE + [o("O1", "C1", "100.000")]
    a = w.run(w.case(rows))[1]
    b = w.run(w.case([rows[-1]] + rows[:-1]))[1]
    va = [g["value"] for g in a["metrics"]["revenue"]["groups"]]
    vb = [g["value"] for g in b["metrics"]["revenue"]["groups"]]
    need(va == vb, f"same data, rows reordered: revenue spelled {va} vs {vb}")
    return f"revenue spelled {va} in both orders"


def k7_rejects_and_lines(w):
    rows = BASE + [o("O4", amt="12..5"), o("O1", "C1", "100.0"), o("O5", amt="4.00", st="test")]
    d = w.case(rows)
    rc, rep, p = w.run(d, "--rejects", str(d / "rej.csv"))
    need((d / "rej.csv").exists(), "--rejects not written")
    rej = list(csv.DictReader((d / "rej.csv").open()))
    mine = [r for r in rej if r.get("file") == "orders.csv"]
    c = cov(rep)
    need(len(mine) == c["rows_read"] - c["included"], f"rejects lists {len(mine)} fact rows, coverage excludes {c['rows_read'] - c['included']}")
    lines = {r["reason"]: int(r["line"]) for r in mine}
    need(lines.get("bad_decimal") == 5, f"bad_decimal reported at line {lines.get('bad_decimal')}, the row is on line 5")
    need(lines.get("excluded_status") == 7, f"excluded_status at line {lines.get('excluded_status')}, want 7")
    return f"--rejects names every excluded fact row ({len(mine)}) with the right line numbers"


def k8_invalid_and_recovery(w):
    d = w.case(BASE)
    out = d / "report.json"
    rc, rep, _ = w.run(d, "--out", str(out))
    need(rc == 0 and out.exists(), f"good run did not write --out (rc {rc})")
    good = out.read_bytes()
    bad = []

    def refused(label, prep, *args):
        snap = {p.name: p.read_bytes() for p in d.iterdir() if p.is_file()}
        prep()
        rc, rep, p = w.run(d, "--out", str(out), "--rejects", str(d / "rej2.csv"), *args)
        after = {p.name: p.read_bytes() for p in d.iterdir() if p.is_file() and not p.is_symlink()}
        changed = [k for k in after if k in snap and after[k] != snap[k] and k not in ("orders.csv", "contract.json", "customers.csv", "control.csv")]
        new = [k for k in after if k not in snap]
        if rc != 2 or changed or new or out.read_bytes() != good:
            bad.append(f"{label}: rc {rc}, changed {changed}, new {new}, report kept {out.read_bytes() == good}")

    orig = (d / "orders.csv").read_text()
    refused("schema drift", lambda: (d / "orders.csv").write_text(orig.replace("currency", "curr", 1)))
    (d / "orders.csv").write_text(orig)
    c0 = (d / "contract.json").read_text()
    for label, txt in (("duplicate key", c0.replace('"timezone"', '"timezone": "UTC", "timezone"', 1)),
                       ("NaN", c0.replace('"as_of": "2026-10-02T00:00:00Z"', '"as_of": NaN', 1)),
                       ("unknown zone", c0.replace("America/Los_Angeles", "Mars/Olympus", 1)),
                       ("dotdot", c0.replace('"orders.csv"', '"../orders.csv"', 1)),
                       ("absolute", c0.replace('"orders.csv"', json.dumps(str(d / "orders.csv")), 1))):
        refused(label, lambda t=txt: (d / "contract.json").write_text(t))
        (d / "contract.json").write_text(c0)
    (d / "real.csv").write_text(orig)
    os.symlink(d / "real.csv", d / "link.csv")
    refused("symlink", lambda: (d / "contract.json").write_text(c0.replace('"orders.csv"', '"link.csv"', 1)))
    (d / "contract.json").write_text(c0)
    rc, rep, p = w.run(d, "--out", str(d / "orders.csv"))
    if rc != 2 or (d / "orders.csv").read_text() != orig:
        bad.append(f"--out onto an input: rc {rc}")
    rc, rep, p = w.run(d, "--out", str(d / "same.csv"), "--rejects", str(d / "same.csv"))
    if rc != 2 or (d / "same.csv").exists():
        bad.append(f"--out and --rejects same file: rc {rc}")
    # recovery: the fixed input rewrites the report
    (d / "orders.csv").write_text(orig.replace("100.00", "101.00", 1))
    rc, rep, p = w.run(d, "--out", str(out))
    if rc != 0 or out.read_bytes() == good:
        bad.append(f"recovery run did not rewrite the report (rc {rc})")
    left = [p.name for p in d.iterdir() if p.name.endswith(".tmp")]
    if left:
        bad.append(f"temp files left {left}")
    need(not bad, "; ".join(bad))
    return "drift, duplicate key, NaN, unknown zone, .., absolute, symlink, --out on input, same targets: exit 2, nothing written; fixed input recovers"


def k9_controls(w):
    bad = []
    d = w.case(BASE, control=["orders.csv", "3", "180.00"])
    rc, rep, _ = w.run(d)
    if rc != 0 or not rep.get("controls", {}).get("match"):
        bad.append(f"matching control: rc {rc} {rep.get('controls')}")
    d = w.case(BASE, control=["orders.csv", "3", "181.00"])
    rc, rep, _ = w.run(d)
    if rc != 1 or "control_mismatch" not in rep.get("gaps", []):
        bad.append(f"sum mismatch: rc {rc} gaps {rep.get('gaps')}")
    d = w.case(BASE + [o("O4", amt="x")], control=["orders.csv", "4", "180.00"])
    rc, rep, _ = w.run(d)
    if rep.get("controls", {}).get("match"):
        bad.append("control matched although a row was rejected")
    need(not bad, "; ".join(bad))
    return "controls: match, sum mismatch and rejected-row mismatch"


def k10_composite_grain(w):
    c = contract()
    c["facts"].update(grain=["invoice_id", "line_no"], duplicate_policy="latest:rev",
                      columns={"invoice_id": "str", "line_no": "int", "rev": "int", "customer_id": "str", "amount": "decimal",
                               "currency": "str", "status": "str", "event_time": "timestamp", "loaded_at": "timestamp"})
    c["metrics"] = [{"name": "revenue", "agg": "sum", "column": "amount", "by": ["currency"]},
                    {"name": "orders", "agg": "count_distinct", "column": "invoice_id", "by": []},
                    {"name": "by_region", "agg": "sum", "column": "amount", "by": ["region"]}]
    h = ["invoice_id", "line_no", "rev", "customer_id", "amount", "currency", "status", "event_time", "loaded_at"]
    t, l = "2026-09-10T12:00:00Z", "2026-09-10T13:00:00Z"
    rows = [["I1", "1", "1", "C1", "10.00", "USD", "paid", t, l], ["I1", "2", "1", "C1", "20.00", "USD", "paid", t, l],
            ["I1", "2", "3", "C1", "25.00", "USD", "paid", t, l], ["I1", "2", "2", "C1", "99.00", "USD", "paid", t, l],
            ["I2", "1", "1", "C2", "5.00", "USD", "paid", t, l], ["I2", "01", "1", "C2", "5.00", "USD", "paid", t, l]]
    bad = expect(w, "composite grain latest:int", rows, 0, {"USD": "40.00"}, 2, {"duplicates.superseded_versions": 2, "duplicates.exact_copies": 1},
                 c=c, header=h, region={"west": "35.00", "east": "5.00"})
    need(not bad, "; ".join(bad))
    return "composite grain with latest:<int>; line_no 1 and 01 are the same key"


def k11_offline(w):
    d = w.case(BASE)
    log = w.root / "net.log"
    rc, rep, _ = w.run(d, e={"PYTHONPATH": str(HERE / "inject"), "M13_NET_LOG": str(log)})
    n = len(log.read_text().splitlines()) if log.exists() else 0
    need(rc == 0 and n == 0, f"offline guard: rc {rc}, {n} network attempts")
    return "0 network attempts under the socket/DNS guard"


def k12_concurrency(w):
    rows, custs, exp, orders = gen(11, 3000)
    d = w.case(rows, custs)
    shared = d / "shared.json"
    rc, rep, p = w.run(d, "--out", str(d / "seq.json"))
    seq = (d / "seq.json").read_bytes()

    def one(i):
        return w.run(d, "--out", str(shared), "--rejects", str(d / f"rej{i}.csv"))[0]

    import threading
    shared.write_bytes(seq)
    stop, torn, reads = threading.Event(), [], [0]

    def reader():  # a consumer polling the report must only ever see a whole report
        while not stop.is_set():
            try:
                b = shared.read_bytes()
            except FileNotFoundError:
                torn.append("missing")
                continue
            reads[0] += 1
            if b != seq:
                torn.append(len(b))
    t = threading.Thread(target=reader)
    t.start()
    with cf.ThreadPoolExecutor(8) as ex:
        rcs = list(ex.map(one, range(8)))
    stop.set()
    t.join()
    need(not torn, f"a concurrent reader saw {len(torn)} torn or missing reports out of {reads[0]} reads (sizes {sorted(set(map(str, torn)))[:5]})")
    need(set(rcs) == {rc}, f"parallel exits {rcs} vs sequential {rc}")
    need(shared.read_bytes() == seq, "shared --out after 8 concurrent writers differs from the sequential report")
    rejs = {(d / f"rej{i}.csv").read_bytes() for i in range(8)}
    need(len(rejs) == 1, "parallel --rejects differ")
    left = [x.name for x in d.iterdir() if x.name.startswith(".") or x.name.endswith(".tmp")]
    need(not left, f"temp files left {left}")
    return f"8 concurrent runs into one --out: same exit, final report equals sequential bytes, a reader saw only whole reports ({reads[0]} reads), no temp files"


def k13_scale(w, n):
    rows, custs, exp, orders = gen(2026, n)
    d = w.case(rows, custs)
    t0 = time.time()
    rc, rep, p = w.run(d, timeout=900)
    el = time.time() - t0
    need(rev(rep) == dec(exp) and scalar(rep, "orders") == orders and cov(rep).get("all_rows_accounted"),
         f"{len(rows)} rows: revenue {rev(rep)} want {exp}, orders {scalar(rep, 'orders')} want {orders}, rc {rc} {p.stderr[-200:]}")
    return f"{len(rows)} rows exact in {el:.1f}s"


CHECKS = [k1_clean_control, k2_single_dirt, k3_join, k4_seeded_unseen, k5a_as_of, k5b_as_of_missing_loaded_at,
          k6_deterministic, k6b_value_spelling_stable, k7_rejects_and_lines, k8_invalid_and_recovery, k9_controls, k10_composite_grain,
          k11_offline, k12_concurrency, k13_scale]


def main():
    global CMD
    args = sys.argv[1:]
    i = args.index("--")
    opts, CMD = args[:i], args[i + 1:]
    only = None
    scale = 20000
    if "--only" in opts:
        only = {x.strip().upper() for x in opts[opts.index("--only") + 1].split(",")}
    if "--scale" in opts:
        scale = int(opts[opts.index("--scale") + 1])
    tmp = Path(tempfile.mkdtemp(prefix="m13o-"))
    passed = total = 0
    try:
        for ch in CHECKS:
            if only and ch.__name__.split("_")[0].upper() not in only:
                continue
            total += 1
            w = Work(tmp / ch.__name__)
            try:
                msg = ch(w, scale) if ch is k13_scale else ch(w)
                print(f"PASS {ch.__name__}: {msg}")
                passed += 1
            except Fail as e:
                print(f"FAIL {ch.__name__}: {str(e)[:1500]}")
            except Exception as e:  # a crash in the candidate output counts as a failure
                print(f"FAIL {ch.__name__}: oracle could not read candidate output ({e.__class__.__name__}: {str(e)[:300]})")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"SUMMARY {passed}/{total} pass; oracle {'ACCEPTS' if passed == total else 'REJECTS'} candidate")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
