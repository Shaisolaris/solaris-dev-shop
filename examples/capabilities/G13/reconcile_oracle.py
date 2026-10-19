#!/usr/bin/env python3
"""G13 oracle: does a candidate reconcile dirty CSV into exact, accounted metrics?

The oracle builds ground truth FIRST (unique orders, customers, regions), computes the exact
answer, and only then injects dirt whose effect it knows: exact copies, superseded versions,
conflicting ties, missing amounts, malformed rows, late loads, test rows, out-of-window rows,
orphan and ambiguous customer keys. A candidate is any command that accepts
    <command> reconcile CONTRACT.json --json [--out REPORT]
and prints the solaris.csv-reconcile-report/1 JSON. All data is synthetic (seeded).

Usage: reconcile_oracle.py --tool "python3 path/to/csv_reconcile.py" [--seed N] [--scale-rows N] [--json]
Exit 0 only if every check passes.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import csv
import datetime as dt
import io
import json
import os
import random
import shlex
import subprocess
import sys
import tempfile
import time
from decimal import Decimal
from pathlib import Path

UTC = dt.timezone.utc
START = dt.datetime(2026, 9, 1, 7, 0, tzinfo=UTC)   # 2026-09-01 00:00 America/Los_Angeles
END = dt.datetime(2026, 10, 1, 7, 0, tzinfo=UTC)
AS_OF = dt.datetime(2026, 10, 2, 0, 0, tzinfo=UTC)
HEADER = ["order_id", "customer_id", "amount", "currency", "status", "event_time", "loaded_at", "updated_at"]


def unz(s):
    return dt.datetime.fromisoformat(s[:-1] + "+00:00" if s.endswith("Z") else s)  # 3.9-safe


def iso(t):
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def contract(controls=True, amount_required=True):
    c = {"schema": "solaris.csv-reconcile/1", "timezone": "America/Los_Angeles",
         "facts": {"file": "orders.csv", "grain": ["order_id"],
                   "columns": {"order_id": "str", "customer_id": "str", "amount": "decimal", "currency": "str", "status": "str",
                               "event_time": "timestamp", "loaded_at": "timestamp", "updated_at": "timestamp"},
                   "required": (["amount"] if amount_required else []) + ["currency", "event_time"], "uppercase": ["currency"],
                   "duplicate_policy": "latest:updated_at", "status_column": "status", "exclude_status": ["test", "void"],
                   "loaded_at_column": "loaded_at"},
         "dimension": {"file": "customers.csv", "key": "customer_id", "attributes": ["region"],
                       "columns": {"customer_id": "str", "region": "str"}, "duplicate_policy": "reject"},
         "window": {"column": "event_time", "start": "2026-09-01T00:00:00-07:00", "end": "2026-10-01T00:00:00-07:00"},
         "as_of": "2026-10-02T00:00:00Z",
         "metrics": [{"name": "revenue", "agg": "sum", "column": "amount", "by": ["currency"]},
                     {"name": "orders", "agg": "count_distinct", "column": "order_id"},
                     {"name": "revenue_by_region", "agg": "sum", "column": "amount", "by": ["region", "currency"]}]}
    if controls:
        c["controls"] = {"file": "control.csv", "sum_column": "amount"}
    return c


class Case:
    """Synthetic dataset with a known answer."""

    def __init__(self, seed, n_orders, dirty=True, amount_required=True):
        rnd = random.Random(seed)
        self.amount_required = amount_required
        regions = ["north", "south", "east", "west"]
        n_cust = max(4, n_orders // 20)
        cust = {f"K{i:05d}": rnd.choice(regions) for i in range(n_cust)}
        dim_rows = [[k, r] for k, r in cust.items()]
        ambiguous = set()
        if dirty:
            for k in rnd.sample(sorted(cust), max(1, n_cust // 50)):      # exact copies: harmless
                dim_rows.append([k, cust[k]])
            for k in rnd.sample(sorted(cust), max(1, n_cust // 40)):      # conflicting copies: ambiguous
                if k in ambiguous:
                    continue
                other = rnd.choice([r for r in regions if r != cust[k]])
                dim_rows.append([k, other])
                ambiguous.add(k)
        rnd.shuffle(dim_rows)
        self.dim_rows = dim_rows
        span = int((END - START).total_seconds()) - 7200
        rows, truth, by_region, naive = [], {}, {}, {}
        n_in = 0

        def t_in():
            return START + dt.timedelta(seconds=3600 + rnd.randrange(span))

        def add_naive(cur, amt):
            naive[cur] = naive.get(cur, Decimal(0)) + amt

        for i in range(n_orders):
            oid = f"A{i:07d}"
            if dirty and rnd.random() < 0.02:
                key = f"Z{i:05d}"   # orphan: not in the dimension
                region = "(unmatched)"
            else:
                key = rnd.choice(sorted(cust)) if n_orders < 5000 else f"K{rnd.randrange(n_cust):05d}"
                region = "(ambiguous)" if key in ambiguous else cust[key]
            cur = rnd.choice(["USD", "EUR"])
            amt = Decimal(rnd.randrange(1, 500000)) / 100
            ev = t_in()
            up = ev + dt.timedelta(minutes=rnd.randrange(1, 600))
            ld = up + dt.timedelta(minutes=5)
            final = [oid, key, f"{amt:.2f}", cur if not dirty or rnd.random() > 0.1 else cur.lower(), "paid", iso(ev), iso(ld), iso(up)]
            truth[cur] = truth.get(cur, Decimal(0)) + amt
            by_region[(region, cur)] = by_region.get((region, cur), Decimal(0)) + amt
            n_in += 1
            rows.append(final)
            add_naive(cur, amt)
        self.counts = {"rejected": 0, "missing_required": 0, "late": 0, "status": 0, "window": 0,
                       "exact": 0, "superseded": 0, "unresolved_rows": 0, "unresolved_keys": 0, "nulls_skipped": 0}
        self.join = {"unmatched": sum(1 for r in rows if r[1].startswith("Z")),
                     "ambiguous": sum(1 for r in rows if r[1] in ambiguous), "fact_key_missing": 0}
        self.join["matched"] = n_in - self.join["unmatched"] - self.join["ambiguous"]
        extra = []
        if dirty:
            base = list(rows)
            k = max(1, n_orders // 50)
            pool = rnd.sample(base, 4 * k)                      # disjoint picks keep the expected counts simple
            picks = [pool[i * k:(i + 1) * k] for i in range(4)]
            for r in picks[3]:                                  # newer "void" version cancels the order
                v = list(r)
                v[4] = "void"
                v[7] = iso(unz(r[7]) + dt.timedelta(hours=2))
                extra.append(v); self.counts["superseded"] += 1; self.counts["status"] += 1
                cur, amt = r[3].upper(), Decimal(r[2])
                add_naive(cur, amt)
                truth[cur] -= amt
                region = "(unmatched)" if r[1].startswith("Z") else ("(ambiguous)" if r[1] in ambiguous else cust[r[1]])
                by_region[(region, cur)] -= amt  # every amount is >= 0.01, so a 0 here means "no rows left"
                n_in -= 1
                self.join["matched" if region not in ("(unmatched)", "(ambiguous)") else region.strip("()")] -= 1
            for r in picks[0]:                                  # exact copies
                extra.append(list(r)); self.counts["exact"] += 1
                add_naive(r[3].upper(), Decimal(r[2]))
            for r in picks[1]:                                  # older version, superseded by the final row
                old = list(r)
                old[2] = f"{Decimal(r[2]) + Decimal('7.77'):.2f}"
                old[7] = iso(unz(r[7]) - dt.timedelta(hours=3))
                extra.append(old); self.counts["superseded"] += 1
                add_naive(r[3].upper(), Decimal(old[2]))
            for r in picks[2]:                                  # late newer version (loaded after as_of): ignored
                late = list(r)
                late[2] = f"{Decimal(r[2]) + Decimal('1000'):.2f}"
                late[7] = iso(AS_OF + dt.timedelta(hours=1)); late[6] = iso(AS_OF + dt.timedelta(hours=2))
                extra.append(late); self.counts["late"] += 1
                add_naive(r[3].upper(), Decimal(late[2]))
            j = 0
            def fresh(cur="USD", amt="10.00", status="paid", ev=None, ld=None, key=None):
                nonlocal j
                j += 1
                e = ev or t_in()
                l = ld or (e + dt.timedelta(minutes=5))
                return [f"D{j:07d}", key or f"K{rnd.randrange(n_cust):05d}", amt, cur, status, iso(e), iso(l), iso(e)]
            for _ in range(k):                                  # conflicting tie: both versions excluded
                a = fresh(amt="11.00"); b = list(a); b[2] = "12.00"
                extra += [a, b]; self.counts["unresolved_rows"] += 2; self.counts["unresolved_keys"] += 1
                add_naive("USD", Decimal("23.00"))
            for _ in range(k):                                  # missing amount
                r = fresh(amt="")
                extra.append(r)
                if amount_required:
                    self.counts["missing_required"] += 1
                else:
                    self.counts["nulls_skipped"] += 1
                    by = r[1]
                    self._null_row = True
                    region = "(ambiguous)" if by in ambiguous else cust.get(by, "(unmatched)")
                    if region == "(ambiguous)":
                        self.join["ambiguous"] += 1
                    elif region == "(unmatched)":
                        self.join["unmatched"] += 1
                    else:
                        self.join["matched"] += 1
                    n_in += 1
            for _ in range(k):                                  # malformed decimal
                extra.append(fresh(amt="12,5x")); self.counts["rejected"] += 1
            for _ in range(k):                                  # wrong field count
                extra.append(fresh()[:5]); self.counts["rejected"] += 1
            for _ in range(k):                                  # late new order
                extra.append(fresh(amt="50.00", ld=AS_OF + dt.timedelta(days=1))); self.counts["late"] += 1
                add_naive("USD", Decimal("50.00"))
            for _ in range(k):                                  # test status
                extra.append(fresh(amt="40.00", status="test")); self.counts["status"] += 1
                add_naive("USD", Decimal("40.00"))
            for _ in range(k):                                  # out of window (UTC early Sept 1 is still August locally)
                extra.append(fresh(amt="60.00", ev=dt.datetime(2026, 9, 1, 3, 0, tzinfo=UTC))); self.counts["window"] += 1
                add_naive("USD", Decimal("60.00"))
        allrows = rows + extra
        rnd.shuffle(allrows)
        self.rows = allrows
        self.truth = truth
        self.by_region = by_region
        self.naive = naive
        self.n_in = n_in
        self.n_rows = len(allrows)
        self.control_sum = sum((Decimal(r[2]) for r in allrows if len(r) == 8 and r[2] and "x" not in r[2]), Decimal(0))
        self.dirty = dirty

    def write(self, folder, rows=None, controls=True):
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        buf = io.StringIO()
        w = csv.writer(buf, lineterminator="\n")
        w.writerow(HEADER)
        w.writerows(rows if rows is not None else self.rows)
        (folder / "orders.csv").write_text(buf.getvalue(), encoding="utf-8")
        buf = io.StringIO()
        w = csv.writer(buf, lineterminator="\n")
        w.writerow(["customer_id", "region"])
        w.writerows(self.dim_rows)
        (folder / "customers.csv").write_text(buf.getvalue(), encoding="utf-8")
        (folder / "control.csv").write_text(f"file,rows,sum\norders.csv,{self.n_rows},{self.control_sum:.2f}\n", encoding="utf-8")
        (folder / "contract.json").write_text(json.dumps(contract(controls, self.amount_required), indent=2), encoding="utf-8")
        return folder / "contract.json"


def run(tool, contract_path, *extra, timeout=600, env=None):
    t0 = time.monotonic()
    p = subprocess.run(shlex.split(tool) + ["reconcile", str(contract_path), "--json", *extra],
                       capture_output=True, text=True, timeout=timeout, env=env)
    try:
        rep = json.loads(p.stdout)
    except ValueError:
        rep = None
    return p.returncode, rep, p.stdout, time.monotonic() - t0


def groups(rep, name):
    out = {}
    for g in (((rep or {}).get("metrics") or {}).get(name) or {}).get("groups", []) or []:
        key = tuple(v for _, v in sorted((g.get("group") or {}).items()))
        out[key] = g.get("value")
    return out


def dec_map(d):
    try:
        return {k: Decimal(str(v)) for k, v in d.items() if v is not None}  # an all-null group has no value
    except Exception:
        return {"unparseable": d}


def expect_metrics(rep, case):
    errs = []
    want = {(c,): v for c, v in case.truth.items() if v}
    got = dec_map(groups(rep, "revenue"))
    if got != want:
        errs.append(f"revenue {sorted(got.items())[:4]} != {sorted(want.items())[:4]}")
    want_r = {tuple(sorted([("currency", c), ("region", r)], key=lambda x: x[0])): v for (r, c), v in case.by_region.items()}
    want_r = {tuple(v for _, v in k): val for k, val in want_r.items() if val}
    got_r = dec_map(groups(rep, "revenue_by_region"))
    if got_r != want_r:
        errs.append("revenue_by_region differs from truth (fan-out, lost orphans or wrong dedup)")
    if sum(got_r.values(), Decimal(0)) != sum(case.truth.values(), Decimal(0)) and not errs:
        errs.append("segments do not add up to the total")
    o = groups(rep, "orders").get(())
    if o != case.n_in:
        errs.append(f"orders {o} != {case.n_in}")
    return errs


def expect_coverage(rep, case):
    errs = []
    cov = (rep or {}).get("coverage") or {}
    dup = cov.get("duplicates") or {}
    c = case.counts
    checks = [("rows_read", cov.get("rows_read"), case.n_rows), ("all_rows_accounted", cov.get("all_rows_accounted"), True),
              ("accounted", cov.get("accounted"), case.n_rows),
              ("rejected", sum((cov.get("rejected") or {}).values()), c["rejected"]),
              ("missing_required", sum((cov.get("missing_required") or {}).values()), c["missing_required"]),
              ("late", cov.get("late_after_as_of"), c["late"]), ("status", cov.get("excluded_status"), c["status"]),
              ("window", cov.get("outside_window"), c["window"]), ("exact", dup.get("exact_copies"), c["exact"]),
              ("superseded", dup.get("superseded_versions"), c["superseded"]),
              ("unresolved_rows", dup.get("rows_unresolved"), c["unresolved_rows"]),
              ("unresolved_keys", dup.get("keys_unresolved"), c["unresolved_keys"]),
              ("included", cov.get("included"), case.n_in)]
    for name, got, want in checks:
        if got != want:
            errs.append(f"coverage.{name} {got!r} != {want!r}")
    j = (((rep or {}).get("dimension") or {}).get("join")) or {}
    for k, v in case.join.items():
        if j.get(k) != v:
            errs.append(f"join.{k} {j.get(k)!r} != {v!r}")
    return errs


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--tool", required=True)
    ap.add_argument("--seed", type=int, default=1307)
    ap.add_argument("--rows", type=int, default=1500)
    ap.add_argument("--scale-rows", type=int, default=200000)
    ap.add_argument("--scale-seconds", type=float, default=120.0)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    results = []

    def check(cid, title, fn):
        try:
            errs = fn()
        except Exception as exc:  # a crash is a failure, never a pass
            errs = [f"oracle error: {exc.__class__.__name__}: {exc}"]
        results.append({"id": cid, "title": title, "pass": not errs, "errors": errs[:5]})

    with tempfile.TemporaryDirectory(prefix="g13-oracle-") as tmp:
        tmp = Path(tmp)
        clean = Case(a.seed, 200, dirty=False)
        dirty = Case(a.seed + 1, a.rows)
        cp_clean = clean.write(tmp / "clean")
        cp_dirty = dirty.write(tmp / "dirty")
        res = {}

        def o1():
            code, rep, _, _ = run(a.tool, cp_clean)
            e = expect_metrics(rep, clean) + expect_coverage(rep, clean)
            if code != 0 or (rep or {}).get("status") != "reconciled":
                e.append(f"clean control should be exit 0 / reconciled, got {code} / {(rep or {}).get('status')}")
            naive = ((rep or {}).get("naive_comparison") or {}).get("sum_every_parsed_row") or {}
            if dec_map(naive) != dec_map(groups(rep, "revenue") and {k[0]: v for k, v in groups(rep, "revenue").items()}):
                e.append("on clean data the naive sum must equal the reconciled sum")
            return e
        check("o1", "clean control reconciles with exit 0 and naive == correct", o1)

        def o2():
            code, rep, _, _ = run(a.tool, cp_dirty)
            res["dirty"] = rep
            e = expect_metrics(rep, dirty)
            if code != 1 or (rep or {}).get("status") != "reconciled_with_gaps":
                e.append(f"dirty data must be exit 1 / reconciled_with_gaps, got {code} / {(rep or {}).get('status')}")
            return e
        check("o2", "exact totals on dirty data (dedup, latest version, late and test rows out)", o2)

        def o3():
            return expect_coverage(res.get("dirty"), dirty)
        check("o3", "every row accounted in exactly one bucket; join counts exact", o3)

        def o4():
            e = []
            for s in (a.seed + 11, a.seed + 12):
                c2 = Case(s, 600)
                code, rep, _, _ = run(a.tool, c2.write(tmp / f"seed{s}"))
                e += [f"seed {s}: {x}" for x in expect_metrics(rep, c2) + expect_coverage(rep, c2)]
            return e
        check("o4", "unseen seeds give exact metrics and coverage", o4)

        def o5():
            c3 = Case(a.seed + 21, 400, amount_required=False)
            code, rep, _, _ = run(a.tool, c3.write(tmp / "nullable"))
            e = expect_metrics(rep, c3)
            skipped = ((rep or {}).get("metrics") or {}).get("revenue", {}).get("null_values_skipped")
            if skipped != c3.counts["nulls_skipped"]:
                e.append(f"null_values_skipped {skipped!r} != {c3.counts['nulls_skipped']} (missing must be counted, never 0-filled)")
            if "none" not in str((rep or {}).get("imputation", "")):
                e.append("report must state imputation none")
            if "null_metric_values" not in ((rep or {}).get("gaps") or []):
                e.append("null metric values must be reported as a gap")
            return e
        check("o5", "no silent imputation: nullable amount skipped and counted", o5)

        def o6():
            rep = res.get("dirty") or {}
            n = (rep.get("naive_comparison") or {}).get("sum_every_parsed_row") or {}
            e = []
            if dec_map(n) != dirty.naive:
                e.append(f"naive_comparison {n} != { {k: str(v) for k, v in sorted(dirty.naive.items())} }")
            tot = sum(dirty.truth.values(), Decimal(0))
            if not e and sum(dirty.naive.values(), Decimal(0)) <= tot:
                e.append("dirty data should show naive inflation")
            if "warehouse" not in str(rep.get("execution", "")):
                e.append("report must state where it executed (no fictional warehouse)")
            return e
        check("o6", "naive inflation shown next to the correct total", o6)

        def o7():
            code1, _, out1, _ = run(a.tool, cp_dirty)
            code2, _, out2, _ = run(a.tool, cp_dirty)
            e = [] if (out1 == out2 and code1 == code2) else ["two runs on the same input differ"]
            rows = list(dirty.rows)
            random.Random(99).shuffle(rows)
            sh = dirty.write(tmp / "shuffled", rows=rows)
            _, rep, _, _ = run(a.tool, sh)
            e += [f"shuffled: {x}" for x in expect_metrics(rep, dirty)]
            return e
        check("o7", "deterministic rerun and row-order invariance", o7)

        def o8():
            out = tmp / "report.json"
            code, rep, _, _ = run(a.tool, cp_clean, "--out", str(out))
            e = []
            if code != 0 or not out.exists():
                return ["could not write a first report with --out"]
            before = out.read_bytes()
            bad = tmp / "drift"
            clean.write(bad)
            txt = (bad / "orders.csv").read_text().replace("currency", "ccy", 1)
            (bad / "orders.csv").write_text(txt)
            code, rep, _, _ = run(a.tool, bad / "contract.json", "--out", str(out))
            if code != 2:
                e.append(f"schema drift should exit 2, got {code}")
            if out.read_bytes() != before:
                e.append("failed run changed the previous report")
            (bad / "orders.csv").write_text(txt.replace("ccy", "currency", 1))
            code, rep, _, _ = run(a.tool, bad / "contract.json", "--out", str(out))
            if code != 0 or json.loads(out.read_text()).get("status") != "reconciled":
                e.append("recovery after fixing the header did not produce a clean report")
            return e
        check("o8", "schema drift exits 2, keeps the previous report; fixing recovers", o8)

        def o9():
            e = []
            esc = tmp / "escape"
            clean.write(esc)
            c = json.loads((esc / "contract.json").read_text())
            c["facts"]["file"] = "../clean/orders.csv"
            (esc / "contract.json").write_text(json.dumps(c))
            code, _, _, _ = run(a.tool, esc / "contract.json")
            if code != 2:
                e.append(f"path outside the contract folder should exit 2, got {code}")
            ln = tmp / "link"
            clean.write(ln)
            (ln / "orders.csv").unlink()
            os.symlink(tmp / "clean" / "orders.csv", ln / "orders.csv")
            code, _, _, _ = run(a.tool, ln / "contract.json")
            if code != 2:
                e.append(f"symlinked input should exit 2, got {code}")
            code, _, _, _ = run(a.tool, cp_clean, "--out", str(tmp / "clean" / "orders.csv"))
            if code != 2 or (tmp / "clean" / "orders.csv").read_text().count("\n") != len(clean.rows) + 1:
                e.append("--out pointing at an input must be refused and leave it intact")
            return e
        check("o9", "input safety: no escape, no symlink, never overwrite inputs", o9)

        def o10():
            big = Case(a.seed + 31, a.scale_rows)
            cp = big.write(tmp / "scale")
            code, rep, _, secs = run(a.tool, cp)
            e = expect_metrics(rep, big) + expect_coverage(rep, big)
            res["scale"] = {"data_rows": big.n_rows, "seconds": round(secs, 2)}
            if secs > a.scale_seconds:
                e.append(f"scale run took {secs:.1f}s > {a.scale_seconds}s")
            return e
        check("o10", "scale: large dirty file exact within the time budget", o10)

        def o11():
            par = Case(a.seed + 41, max(2000, a.scale_rows // 8))
            cp = par.write(tmp / "parallel")
            outs = [tmp / "parallel" / f"r{i}.json" for i in range(4)]
            with cf.ThreadPoolExecutor(4) as ex:
                got = list(ex.map(lambda o: run(a.tool, cp, "--out", str(o)), outs))
            e = []
            if len({g[2] for g in got}) != 1 or len({o.read_bytes() for o in outs if o.exists()}) != 1:
                e.append("parallel runs disagree or a report is missing")
            e += expect_metrics(got[0][1], par)
            if any(p.name.endswith(".tmp") for p in (tmp / "parallel").iterdir()):
                e.append("temporary files left behind")
            res["parallel"] = {"runs": 4, "data_rows": par.n_rows}
            return e
        check("o11", "concurrency: 4 parallel runs agree byte for byte, no temp files left", o11)

        # o12 and o13 (G13 r2, from M13 Grok self-validation of 7da20d4): small seeded cases, one rule each
        rnd = random.Random(a.seed + 97)
        pre = "".join(rnd.choice("BCDFGHJKLMNPQRSTVWXZ") for _ in range(3))
        cents = [rnd.randint(100, 99999) for _ in range(3)]
        amts = [f"{c // 100}.{c % 100:02d}" for c in cents]
        usd = Decimal(amts[0]) + Decimal(amts[1])
        k = 0

        def r(i, cust="K1", amt="10.00", cur="USD", ev="2026-09-10T12:00:00Z", la="2026-09-10T13:00:00Z", up="2026-09-10T12:00:00Z", st="paid"):
            return [f"{pre}{i}", cust, amt, cur, st, ev, la, up]

        base = [r(1, "K1", amts[0]), r(2, "K2", amts[1]), r(3, "K1", amts[2], "EUR")]

        def mk(rows, control=None, header=HEADER, **over):
            nonlocal k
            k += 1
            d = tmp / f"m{k:03d}"
            d.mkdir()
            buf = io.StringIO()
            w = csv.writer(buf, lineterminator="\n")
            w.writerow(header)
            w.writerows(rows)
            (d / "orders.csv").write_text(buf.getvalue(), encoding="utf-8")
            (d / "customers.csv").write_text("customer_id,region\nK1,west\nK2,east\n", encoding="utf-8")
            c = contract(controls=control is not None)
            if control is not None:
                (d / "control.csv").write_text("file,rows,sum\norders.csv,%s,%s\n" % control, encoding="utf-8")
            for key, v in over.items():
                node, parts = c, key.split("__")
                for q in parts[:-1]:
                    node = node[q]
                if v is None:
                    node.pop(parts[-1], None)
                else:
                    node[parts[-1]] = v
            (d / "contract.json").write_text(json.dumps(c), encoding="utf-8")
            return d / "contract.json"

        def usd_of(rep):
            v = groups(rep, "revenue").get(("USD",))
            return None if v is None else Decimal(str(v))

        def rejects(cp):
            out = cp.parent / "rejects.csv"
            run(a.tool, cp, "--rejects", str(out))
            return out.read_text().splitlines()[1:] if out.exists() else []

        def dots(d):
            return sorted(p.name for p in d.iterdir() if p.name.startswith("."))

        def o12():
            e = []
            rows = base + [r(10, amt="1.00", ev=iso(START)), r(11, amt="2.00", ev=iso(END)),
                           r(12, amt="4.00", la=iso(AS_OF)), r(13, amt="8.00", la=iso(AS_OF + dt.timedelta(seconds=1)))]
            code, rep, _, _ = run(a.tool, mk(rows))
            cov = (rep or {}).get("coverage") or {}
            if usd_of(rep) != usd + 5 or cov.get("outside_window") != 1 or cov.get("late_after_as_of") != 1:
                e.append(f"half-open window / as_of boundary: USD {usd_of(rep)} (want {usd + 5}), outside {cov.get('outside_window')}, late {cov.get('late_after_as_of')}")
            ms = [{"name": "buyers", "agg": "count_distinct", "column": "customer_id"}, {"name": "priced", "agg": "count", "column": "amount"},
                  {"name": "smallest", "agg": "min", "column": "amount"}]
            code, rep, _, _ = run(a.tool, mk(base + [r(4, "K2", "")], facts__required=["currency", "event_time"], metrics=ms))
            got = tuple(groups(rep, n).get(()) for n in ("buyers", "priced", "smallest"))
            want = (2, 3, format(min(Decimal(x) for x in amts), "f"))
            if got != want or "null_metric_values" not in ((rep or {}).get("gaps") or []):
                e.append(f"count_distinct/count/min with a null amount: {got}, want {want}, gaps {(rep or {}).get('gaps')}")
            parsed = sum((Decimal(x) for x in amts), Decimal(0))
            code, rep, _, _ = run(a.tool, mk(base + [r(5, amt="1.0x")], control=("4", f"{parsed}")))
            ct = (rep or {}).get("controls") or {}
            if ct.get("match") is not False or "control_mismatch" not in ((rep or {}).get("gaps") or []):
                e.append(f"control whose rows and parsed sum agree but a row was rejected: match {ct.get('match')}")
            # value parsing: an exact copy spelled differently (10.5 / 10.50, usd / USD) collapses; strict thousands
            # grouping; 21 integer digits refused; a naive time is read in the contract zone, not UTC
            alt = amts[0] + "0"
            rows = base + [r(1, "K1", alt, "usd"), r(14, amt="1,234.50"), r(15, amt="1,23.00"), r(16, amt="1" * 21),
                           r(17, amt="16.00", ev="2026-10-01 03:00:00")]
            code, rep, _, _ = run(a.tool, mk(rows, facts__thousands_separator=","))
            cov = (rep or {}).get("coverage") or {}
            dup = cov.get("duplicates") or {}
            if (usd_of(rep) != usd + Decimal("1234.50") or dup.get("exact_copies") != 1 or cov.get("rejected") != {"bad_decimal": 2}
                    or cov.get("outside_window") != 1):
                e.append(f"value parsing: USD {usd_of(rep)} (want {usd + Decimal('1234.50')}), exact copies {dup.get('exact_copies')}, "
                         f"rejected {cov.get('rejected')}, outside window {cov.get('outside_window')} (naive 03:00 local on Oct 1 is outside)")
            cp = mk(base)
            out = cp.parent / "r.json"
            out.write_text("OLD\n")
            os.link(out, cp.parent / "alias.json")
            code, rep, _, _ = run(a.tool, cp, "--out", str(out))
            if (cp.parent / "alias.json").read_text() != "OLD\n" or not out.read_text().startswith("{") or dots(cp.parent):
                e.append("--out rewrote the old report in place (a reader can see a partial file) or left temp files")
            return e
        check("o12", "boundaries, value parsing, null-aware count/min, controls with rejects, replace-not-rewrite output", o12)

        def o13():
            e = []
            for tok in ("", "NULL"):
                cp = mk(base + [r(6, amt="4.00", la=tok)])
                code, rep, _, _ = run(a.tool, cp)
                if code != 1 or usd_of(rep) != usd or not (rep or {}).get("gaps") or not ((rep or {}).get("coverage") or {}).get("all_rows_accounted"):
                    e.append(f"N1 missing loaded_at ({tok!r}) under as_of: exit {code}, USD {usd_of(rep)}, gaps {(rep or {}).get('gaps')}")
            code, rep, _, _ = run(a.tool, mk(base + [r(2, "K2", "75.00", la="", up="2026-09-20T00:00:00Z")]))
            if usd_of(rep) != usd or code != 1:
                e.append(f"N1 a newer version with no loaded_at replaced the on-time one: USD {usd_of(rep)}, exit {code}")
            good = ["2026-09-10T12:00:00Z", "2026-09-10T12:00:00+00:00", "2026-09-10T12:00:00.5Z", "2026-09-10T12:00Z", "2026-09-10 12:00:00", "2026-09-10"]
            bad = ["20260910T120000Z", "2026-W37-4T12:00:00Z", "2026-09-10T12:00:00.1234567890Z", "2026-09-10T12:00:00+0", "2026-09-10T12:00:00 Z"]
            code, rep, _, _ = run(a.tool, mk(base + [r(20 + i, amt="1.00", ev=v) for i, v in enumerate(good + bad)]))
            rej = ((rep or {}).get("coverage") or {}).get("rejected")
            if rej != {"bad_timestamp": len(bad)} or usd_of(rep) != usd + len(good):
                e.append(f"N2 timestamp grammar: rejected {rej} (want {len(bad)} bad_timestamp), USD {usd_of(rep)}")
            cp = mk(base + [r(2, "K2", amts[1], la="2026-09-11T08:00:00Z")])
            code, rep, _, _ = run(a.tool, cp)
            if usd_of(rep) != usd or code != 0 or rejects(cp) != ["orders.csv,5,duplicate_exact,order_id"]:
                e.append(f"N3 re-delivery differing only in loaded_at: USD {usd_of(rep)}, exit {code}, rejects {rejects(cp)}")
            cp = mk(base + [r(7, amt="x")])
            ro = cp.parent / "ro"
            ro.mkdir()
            os.chmod(ro, 0o500)
            try:
                code, _, _, _ = run(a.tool, cp, "--rejects", str(cp.parent / "rej.csv"), "--out", str(ro / "r.json"))
            finally:
                os.chmod(ro, 0o700)
            if code != 2 or (cp.parent / "rej.csv").exists() or dots(cp.parent):
                e.append(f"N4 --out unwritable: exit {code}, --rejects written anyway {(cp.parent / 'rej.csv').exists()}")
            (cp.parent / "rej.csv").write_text("OLD\n")
            (cp.parent / "r.json").write_text("OLD\n")
            fault = cp.parent / "fault"
            fault.mkdir()
            (fault / "sitecustomize.py").write_text(
                "import os\n_r = os.replace\n"
                "def _x(s, d, *a, **k):\n"
                "    if str(d).endswith('r.json') and '.keep' not in str(s):\n        raise PermissionError(13, 'injected')\n"
                "    return _r(s, d, *a, **k)\nos.replace = _x\n")
            env = dict(os.environ, PYTHONPATH=str(fault))
            code, _, _, _ = run(a.tool, cp, "--rejects", str(cp.parent / "rej.csv"), "--out", str(cp.parent / "r.json"), env=env)
            if code != 2 or (cp.parent / "rej.csv").read_text() != "OLD\n" or (cp.parent / "r.json").read_text() != "OLD\n" or dots(cp.parent):
                e.append(f"N4 second rename failed: exit {code}; the first output was not put back or temp files were left")
            deep = tmp / "deep"
            deep.mkdir()
            (deep / "contract.json").write_text("[" * 100000 + "]" * 100000)
            code, rep, _, _ = run(a.tool, deep / "contract.json")
            if code != 2 or (rep or {}).get("status") != "invalid":
                e.append(f"N5 deeply nested contract: exit {code}, status {(rep or {}).get('status')}")
            code, rep, _, _ = run(a.tool, mk(base + [r(8, ev="2026-11-01 01:30:00"), r(9, ev="2026-03-08 02:30:00")]))
            rej = ((rep or {}).get("coverage") or {}).get("rejected") or {}
            if sum(rej.values()) != 2 or usd_of(rep) != usd:
                e.append(f"N6 DST ambiguous / nonexistent local times were guessed: rejected {rej}, USD {usd_of(rep)}")
            hdr = HEADER + ["rev"]
            rows = [x + ["1"] for x in base] + [r(2, "K2", "70.00") + ["\u0663"]]
            code, rep, _, _ = run(a.tool, mk(rows, header=hdr, facts__columns__rev="int", facts__duplicate_policy="latest:rev"))
            if usd_of(rep) != usd or ((rep or {}).get("coverage") or {}).get("rejected") != {"bad_int": 1}:
                e.append(f"N7 a non-ASCII digit was read as a number: USD {usd_of(rep)}")
            x = base + [r(1, "K1", amts[0] + "0")]
            va = groups(run(a.tool, mk(x))[1], "revenue")
            vb = groups(run(a.tool, mk([x[-1]] + x[:-1]))[1], "revenue")
            if va != vb:
                e.append(f"N8 the spelling of a total depends on row order: {va} vs {vb}")
            return e
        check("o13", "as_of without loaded_at, one time grammar, re-delivery, both-or-neither outputs, deep JSON, DST, ASCII digits, spelling", o13)

        # o14 (G13 r3, from the M13 r2 self-validation): export timestamp spellings and midnight DST days
        def o14():
            e = []
            spell = {"pg": "2026-09-12 12:00:00+00", "pgfrac": "2026-09-12 12:00:00.123456+00", "pg-07": "2026-09-12 05:00:00-07",
                     "dt2_7": "2026-09-12 12:00:00.1234567", "dto_7": "2026-09-12 12:00:00.1234567 +00:00", "dto_7w": "2026-09-12 05:00:00.1234567 -07:00",
                     "basic": "2026-09-12T05:00:00-0700", "basic+0530": "2026-09-12T17:30:00+0530", "nano": "2026-09-12T12:00:00.123456789Z"}
            for n, v in spell.items():
                micro = 123456 if ".123456" in v else 0
                for end_us, inside in ((micro + 1, True), (micro, False)):
                    cp = mk(base + [r(30, amt="4.00", ev=v)], timezone="UTC",
                            window={"column": "event_time", "start": "2026-09-01T00:00:00Z", "end": f"2026-09-12T12:00:00.{end_us:06d}Z"})
                    code, rep, _, _ = run(a.tool, cp)
                    want = usd + (4 if inside else 0)
                    if code != 0 or usd_of(rep) != want or ((rep or {}).get("coverage") or {}).get("rejected"):
                        e.append(f"RT {n} {v!r} with window end .{end_us:06d}: exit {code}, USD {usd_of(rep)} (want {want})")
            # digits past the sixth are dropped, not rounded
            cp = mk(base + [r(31, amt="4.00", ev="2026-09-12T12:00:00.1234569Z")], timezone="UTC",
                    window={"column": "event_time", "start": "2026-09-01T00:00:00Z", "end": "2026-09-12T12:00:00.123457Z"})
            code, rep, _, _ = run(a.tool, cp)
            if usd_of(rep) != usd + 4:
                e.append(f"RT a 7-digit fraction was rounded up past the window end: USD {usd_of(rep)}")
            for v in ("2026-10-02T00:00:00+00", "2026-10-02 00:00:00.123456789 +00:00"):
                code, rep, _, _ = run(a.tool, mk(base, as_of=v))
                if code == 2:
                    e.append(f"RT as_of {v!r} refused")
            # RD: a date-only value on a midnight DST change is the first instant of that day
            cp = mk([r(40, amt="1.00", ev="2026-09-06T03:59:59Z"), r(41, amt="2.00", ev="2026-09-06T04:00:00Z"),
                     r(42, amt="4.00", ev="2026-09-06"), r(43, amt="8.00", ev="2026-09-06 00:30")],
                    timezone="America/Santiago", as_of=None, window={"column": "event_time", "start": "2026-09-06", "end": "2026-10-01"})
            code, rep, _, _ = run(a.tool, cp)
            rej = ((rep or {}).get("coverage") or {}).get("rejected")
            if code == 2 or usd_of(rep) != Decimal("6.00") or rej != {"nonexistent_local_time": 1}:
                e.append(f"RD Santiago 2026-09-06: exit {code}, USD {usd_of(rep)} (want 6.00), rejected {rej}")
            cp = mk([r(50, amt="1.00", ev="2026-11-01T03:59:59Z"), r(51, amt="2.00", ev="2026-11-01T04:30:00Z"),
                     r(52, amt="4.00", ev="2026-11-01"), r(53, amt="8.00", ev="2026-11-01 00:30")],
                    timezone="America/Havana", as_of=None, window={"column": "event_time", "start": "2026-11-01", "end": "2026-12-01"})
            code, rep, _, _ = run(a.tool, cp)
            rej = ((rep or {}).get("coverage") or {}).get("rejected")
            if code == 2 or usd_of(rep) != Decimal("6.00") or rej != {"ambiguous_local_time": 1}:
                e.append(f"RD Havana 2026-11-01: exit {code}, USD {usd_of(rep)} (want 6.00), rejected {rej}")
            return e
        check("o14", "export timestamp spellings (PostgreSQL +00/-07, 7 and 9 digit fractions, -0700, SQL Server) read exactly; date-only days on midnight DST changes", o14)

    passed = sum(r["pass"] for r in results)
    summary = {"tool": a.tool, "seed": a.seed, "passed": passed, "total": len(results), "checks": results,
               "scale": res.get("scale"), "parallel": res.get("parallel")}
    if a.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        for r in results:
            print(f"{'PASS' if r['pass'] else 'FAIL'} {r['id']} {r['title']}")
            for x in r["errors"]:
                print(f"     - {x}")
        if res.get("scale"):
            print(f"scale: {res['scale']['data_rows']} data rows in {res['scale']['seconds']}s")
        print(f"{passed}/{len(results)} checks passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
