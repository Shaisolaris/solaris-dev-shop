#!/usr/bin/env python3
"""G37 oracle: data drops whose inventory gaps, retention dates and request records are known by construction.

Usage: privacy_oracle.py [--seeds N] -- PYTHON TOOL   (default: compliance-auditor privacy_inventory.py)
Runs the tool as a fresh process (`review PACKAGE --json [--out DIR]`) and ends with ACCEPTED n/n or REJECTED k/n.
"""
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
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
FIX = HERE / "fixtures"
UTC = dt.timezone.utc
ASOF = dt.datetime(2026, 10, 2, tzinfo=UTC)


def iso(t):
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def run(cmd, pkg, out=None, env=None):
    a = cmd + ["review", str(pkg), "--json"] + (["--out", str(out)] if out else [])
    e = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", **(env or {}))
    try:
        r = subprocess.run(a, capture_output=True, text=True, timeout=600, env=e)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 99, None, str(exc), ""
    try:
        rep = json.loads(r.stdout) if r.stdout.strip() else None
    except json.JSONDecodeError:
        rep = None
    return r.returncode, rep, r.stderr, r.stdout


def codes(rep):
    return sorted({f.get("code") for f in (rep or {}).get("findings", []) or []})


def reqs(rep):
    return {r.get("request_id"): r for r in (rep or {}).get("requests", []) or []}


def due_lines(rep):
    return {r.get("table"): sorted(d.get("line") for d in r.get("due", [])) for r in (rep or {}).get("retention", []) or []}


def copyfx(name, d):
    shutil.copytree(FIX / name, d)
    return d / "package.json"


def random_drop(seed, n, d):
    """Customers and orders with known subjects, created dates and retention; requests with known answers."""
    rnd = random.Random(seed)
    shutil.copytree(FIX / "clean", d)
    cust, orders, want_due = [], [], {"customers.csv": [], "orders.csv": []}
    by_subject = {}
    for i in range(n):
        k = "K%d" % i
        created = ASOF - dt.timedelta(days=rnd.choice([10, 729, 730, 731, rnd.randint(1, 2000)]), seconds=rnd.choice([0, 0, 1]))
        cust.append([k, rnd.choice(["west", "east"]), "Synthetic Person %s" % k, "contact-token-%s" % k, iso(created), iso(created)])
        line = len(cust) + 1
        if created + dt.timedelta(days=730) <= ASOF:
            want_due["customers.csv"].append(line)
        by_subject.setdefault(k, []).append(("customers.csv", line))
    for j in range(n * 2):
        k = "K%d" % rnd.randrange(n)
        t = ASOF - dt.timedelta(days=rnd.choice([5, 2554, 2555, 2556, rnd.randint(1, 4000)]))
        orders.append(["A%d" % j, k, "%d.00" % rnd.randint(1, 500), "USD", "paid", iso(t), iso(t), iso(t)])
        line = len(orders) + 1
        if t + dt.timedelta(days=2555) <= ASOF:
            want_due["orders.csv"].append(line)
        by_subject.setdefault(k, []).append(("orders.csv", line))
    with open(d / "data/customers.csv", "w") as f:
        f.write("customer_id,region,name,contact,created_at,updated_at\n" + "".join(",".join(r) + "\n" for r in cust))
    with open(d / "data/orders.csv", "w") as f:
        f.write("order_id,customer_id,amount,currency,status,event_time,loaded_at,updated_at\n" + "".join(",".join(r) + "\n" for r in orders))
    want_req, lines = {}, []
    for q in range(40):
        k = "K%d" % rnd.randrange(n + 5)          # some subjects do not exist
        typ = rnd.choice(["access", "deletion", "correction"])
        ver = rnd.random() < 0.8
        jur = rnd.choice(["EU-GDPR", "US-CA-CCPA"])
        rec = dt.datetime(2026, rnd.randint(1, 9), rnd.randint(1, 28), 9, tzinfo=UTC)
        r = {"request_id": "Q%d" % q, "type": typ, "subject": k, "received_at": iso(rec), "identity_verified": ver, "jurisdiction": jur}
        lines.append(json.dumps(r))
        if rnd.random() < 0.2:
            lines.append(json.dumps(r))
        hits = sorted(by_subject.get(k, []), key=lambda x: (x[0], x[1]))
        if jur == "EU-GDPR":
            m = rec.month + 1
            y = rec.year + (m > 12)
            m = (m - 1) % 12 + 1
            due = rec.replace(year=y, month=m)
        else:
            due = rec + dt.timedelta(days=45)
        if not ver:
            st, keep = "awaiting_identity_verification", None
        elif not hits:
            st, keep = "no_records_found", None
        else:
            st = {"access": "access_package_ready_for_review", "deletion": "deletion_plan_ready_for_review",
                  "correction": "correction_ready_for_review"}[typ]
            keep = sorted(l for f, l in hits if f == "orders.csv") if typ == "deletion" else None
        want_req["Q%d" % q] = (st, due.isoformat(), None if not ver else sorted(hits), keep, ASOF > due)
    rnd.shuffle(lines)
    (d / "requests.jsonl").write_text("\n".join(lines) + "\n")
    return d / "package.json", want_due, want_req


def main():
    argv = sys.argv[1:]
    seeds = 3
    if argv[:1] == ["--seeds"]:
        seeds, argv = int(argv[1]), argv[2:]
    if argv[:1] == ["--"]:
        argv = argv[1:]
    cmd = argv or [sys.executable, str(ROOT / "employees/legal-compliance/compliance-auditor/privacy_inventory.py")]
    tmp = Path(tempfile.mkdtemp(prefix="g37-oracle-"))
    results = []

    def check(name, fn):
        try:
            ok, why = fn()
        except Exception as exc:
            ok, why = False, "%s: %s" % (exc.__class__.__name__, exc)
        results.append(bool(ok))
        print("%s %s%s" % ("PASS" if ok else "FAIL", name, "" if ok else "  (" + str(why)[:300] + ")"))

    def o1():
        rc, rep, err, _ = run(cmd, copyfx("clean", tmp / "o1"))
        r = reqs(rep).get("R1", {})
        vals = [p.get("values", {}) for p in r.get("access_package", [])]
        ok = rc == 0 and not codes(rep) and r.get("status") == "access_package_ready_for_review" \
            and r.get("due") == "2026-10-10T09:00:00+00:00" and sorted((x["file"], x["line"]) for x in r.get("records", [])) == \
            [("customers.csv", 2), ("orders.csv", 2), ("orders.csv", 4)] \
            and all(v.get("customer_id") == "K1" for v in vals) and len((rep or {}).get("inventory_map", [])) == 14
        return ok, (rc, codes(rep), r.get("status"), r.get("records"), err[-200:])
    check("o1 clean control: every field mapped, exit 0, access request finds exactly K1's three records", o1)

    SEPT_CODES = sorted(["flow_to_undeclared_system", "unmapped_field", "stale_inventory_entry", "retention_anchor_unreadable",
                         "rejected_request_rows", "conflicting_request_ids", "closed_late", "overdue_request", "unknown_jurisdiction_clock"])

    def o2():
        rc, rep, _, _ = run(cmd, copyfx("september", tmp / "o2"))
        R = reqs(rep)
        st = {k: v.get("status") for k, v in R.items()}
        want_st = {"R1": "access_package_ready_for_review", "R2": "deletion_plan_ready_for_review", "R3": "awaiting_identity_verification",
                   "R4": "correction_ready_for_review", "R5": "no_records_found", "R6": "access_package_ready_for_review"}
        um = [f for f in rep.get("findings", []) if f.get("code") == "unmapped_field"]
        r2 = R.get("R2", {})
        ok = rc == 1 and codes(rep) == SEPT_CODES and st == want_st \
            and due_lines(rep) == {"orders.csv": [6], "customers.csv": [6], "tickets.csv": [2, 5]} \
            and um and um[0].get("field") == "birth_date" and um[0].get("ignored_by_g13") is True \
            and R["R4"].get("due") == "2026-02-28T09:00:00+00:00" and R["R2"].get("due") == "2026-09-15T09:00:00+00:00" \
            and sorted((x["file"], x["line"]) for x in r2.get("retain_pending_review", [])) == [("orders.csv", 3), ("orders.csv", 4)] \
            and sorted((x["file"], x["line"]) for x in r2.get("delete", [])) == [("customers.csv", 3), ("tickets.csv", 2), ("tickets.csv", 3)] \
            and r2.get("propagate_to") == ["cfo-books", "crm-export", "helpdesk", "warehouse"] and R["R6"].get("due") is None
        return ok, (rc, codes(rep), st, due_lines(rep))
    check("o2 september hand-worked: findings, retention lines, request statuses, month-end clock, deletion versus hold", o2)

    def o3():
        out = tmp / "o3-out"
        rc, rep, _, stdout = run(cmd, copyfx("september", tmp / "o3"), out=out)
        r3 = reqs(rep).get("R3", {})
        blob = stdout + "".join(p.read_text() for p in out.glob("*")) if out.is_dir() else stdout
        leaked = [s for s in ("Synthetic Person K3", "contact-token-K3", "1979-07-07") if s in blob]
        return rc == 1 and r3.get("status") == "awaiting_identity_verification" and not r3.get("records") and not leaked \
            and out.joinpath("handoff.md").is_file(), (rc, r3, leaked)
    check("o3 an unverified request reveals nothing about the subject in the report, the handoff or stdout", o3)

    def o4():
        d = tmp / "o4"
        pkg = copyfx("clean", d)
        p = d / "data/orders.csv"
        lines = p.read_text().splitlines()
        lines[0] += ",gift_message"
        lines[1:] = [l + ",synthetic note" for l in lines[1:]]
        p.write_text("\n".join(lines) + "\n")
        inv = json.loads((d / "inventory.json").read_text())
        del inv["tables"]["customers.csv"]["fields"]["contact"]
        inv["tables"]["customers.csv"]["fields"]["phone"] = {"category": "contact", "purpose": "x", "basis": "y"}
        (d / "inventory.json").write_text(json.dumps(inv))
        rc, rep, _, _ = run(cmd, pkg)
        fs = rep.get("findings", [])
        got = sorted((f.get("code"), f.get("table"), f.get("field")) for f in fs)
        want = [("stale_inventory_entry", "customers.csv", "phone"), ("unmapped_field", "customers.csv", "contact"),
                ("unmapped_field", "orders.csv", "gift_message")]
        return rc == 1 and got == want, (rc, got)
    check("o4 inventory drift (a column G13 ignores appears, one is renamed) is named field by field", o4)

    def o5():
        bad = []
        for s in range(seeds):
            pkg, want_due, want_req = random_drop(500 + s, 300, tmp / ("o5-%d" % s))
            rc, rep, err, _ = run(cmd, pkg)
            got_due = due_lines(rep)
            R = reqs(rep)
            for q, (st, due, hits, keep, late) in want_req.items():
                r = R.get(q, {})
                gh = sorted((x["file"], x["line"]) for x in r.get("records", [])) if hits is not None else None
                gk = sorted(x["line"] for x in r.get("retain_pending_review", [])) if keep is not None else None
                over = any(f.get("code") == "overdue_request" and f.get("request_id") == q for f in rep.get("findings", []))
                if (r.get("status"), r.get("due"), gh, gk, over) != (st, due, hits, keep, late) or (hits is None and r.get("records")):
                    bad.append((s, q, r.get("status"), st, r.get("due"), due, over, late))
                    break
            if got_due != want_due or len(R) != len(want_req):
                bad.append((s, "due", {k: len(v) for k, v in got_due.items()}, {k: len(v) for k, v in want_due.items()}))
        return not bad, bad[:3]
    check("o5 %d seeded drops (300 people, 600 orders, 40 requests with copies): retention edges, records, holds and clocks equal construction" % seeds, o5)

    def o6():
        good = copyfx("clean", tmp / "o6")
        out = tmp / "o6-out"
        if run(cmd, good, out=out)[0] != 0:
            return False, "first run"
        before = {p.name: p.read_bytes() for p in out.iterdir()}
        src = good.read_text()
        bads = []
        variants = {
            "unknown_key": src.replace('"schema"', '"delete_now": true, "schema"'),
            "escape": src.replace('"inventory.json"', '"../o1/inventory.json"'),
            "missing": src.replace('"requests.jsonl"', '"nope.jsonl"'),
            "clock_no_source": src.replace('"months": 1, "source": "fixture value modelled on GDPR Art. 12(3) (one month, extendable); confirm with counsel"', '"months": 1'),
            "clock_float": src.replace('"days": 45', '"days": 45.5'),
            "naive_asof": src.replace('"2026-10-02T00:00:00Z"', '"2026-10-02"'),
            "badjson": src[:30],
        }
        for name, text in variants.items():
            d = tmp / ("o6-" + name)
            shutil.copytree(good.parent, d)
            (d / "package.json").write_text(text)
            rc, _, err, _ = run(cmd, d / "package.json", out=out)
            if rc != 2 or {p.name: p.read_bytes() for p in out.iterdir()} != before:
                bads.append((name, rc, err[-100:]))
        d = tmp / "o6-badcat"
        shutil.copytree(good.parent, d)
        inv = json.loads((d / "inventory.json").read_text())
        inv["tables"]["orders.csv"]["fields"]["amount"]["category"] = "money"
        (d / "inventory.json").write_text(json.dumps(inv))
        if run(cmd, d / "package.json", out=out)[0] != 2:
            bads.append(("bad_category",))
        if run(cmd, good, out=good.parent / "inside")[0] != 2:
            bads.append(("out_inside",))
        (out / "report.json").unlink()
        if run(cmd, good, out=out)[0] != 0 or not (out / "report.json").is_file():
            bads.append(("recovery",))
        md = (out / "handoff.md").read_text() if (out / "handoff.md").is_file() else ""
        if "Not legal advice" not in md or "qualified reviewer" not in md:
            bads.append(("handoff_label",))
        return not bads, bads
    check("o6 eight invalid packages and --out inside the package exit 2 and keep the previous output; recovery; handoff labelled", o6)

    def o7():
        d = tmp / "o7"
        pkg = copyfx("september", d)
        sums = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in d.rglob("*") if p.is_file()}
        g = tmp / "guard"
        g.mkdir()
        (g / "sitecustomize.py").write_text("import socket\nclass _S(socket.socket):\n    def connect(self, *a):\n        raise OSError('blocked')\nsocket.socket = _S\n")
        ps = [subprocess.Popen(cmd + ["review", str(pkg), "--json", "--out", str(tmp / ("o7-%d" % i))], stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=str(g))) for i in range(4)]
        [p.communicate(timeout=600) for p in ps]
        reps = {(tmp / ("o7-%d" % i) / "report.json").read_bytes() if (tmp / ("o7-%d" % i) / "report.json").is_file() else b"" for i in range(4)}
        after = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in d.rglob("*") if p.is_file()}
        return [p.returncode for p in ps] == [1] * 4 and len(reps) == 1 and b"" not in reps and after == sums, ([p.returncode for p in ps], len(reps))
    check("o7 four parallel runs with the network blocked: identical reports; data files byte-identical (nothing deleted)", o7)

    def o8():
        rc, rep, _, _ = run(cmd, copyfx("september", tmp / "o8"))
        why = " ".join(q.get("why", "") for q in (rep or {}).get("qualified_review", []))
        ob = (rep or {}).get("obligations", [])
        ok = rc == 1 and "tickets.csv.body" in why and "R2" in why and "BR-LGPD" in why and "EU-GDPR" in why and "hold_for_review" in why \
            and len({o.get("id") for o in ob}) == len(ob) >= 8 and all(o.get("refs") for o in ob) \
            and "Not legal advice" in (rep or {}).get("not_legal_advice", "")
        return ok, (rc, why[:200], len(ob))
    check("o8 qualified-review boundaries are visible (free text, retention hold, deletion conflict, unknown and configured clocks); every obligation traceable", o8)

    def o9():
        pkg, want_due, want_req = random_drop(99, 20000, tmp / "o9")
        t = time.time()
        rc, rep, _, _ = run(cmd, pkg)
        el = time.time() - t
        return rc in (0, 1) and due_lines(rep) == want_due and el < 120, (rc, round(el, 1))
    check("o9 scale: 20 000 people and 40 000 orders, retention equal to construction in under 120 s", o9)

    shutil.rmtree(tmp, ignore_errors=True)
    n, k = len(results), sum(results)
    print("%s %d/%d" % ("ACCEPTED" if k == n else "REJECTED", k, n))
    return 0 if k == n else 1


if __name__ == "__main__":
    sys.exit(main())
