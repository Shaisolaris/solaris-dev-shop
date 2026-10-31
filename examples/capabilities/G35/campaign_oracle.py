#!/usr/bin/env python3
"""G35 oracle: builds campaign books whose answer is known by construction, then checks a campaign ledger tool.

Usage: campaign_oracle.py [--seeds N] -- PYTHON TOOL     (default tool: the paid-ads-manager campaign_ledger.py)
Prints one line per check and ends with ACCEPTED n/n or REJECTED k/n. Exit 0 alone proves nothing.
The oracle never imports the tool; it runs it as a fresh process and reads its --json report.
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
from decimal import Decimal, ROUND_HALF_EVEN
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
FIX = HERE / "fixtures"
UTC = dt.timezone.utc
T0 = dt.datetime(2026, 9, 1, tzinfo=UTC)
Q2, Q4 = Decimal("0.01"), Decimal("0.0001")


def iso(t):
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def run(cmd, pkg, out=None, env=None):
    a = cmd + ["reconcile", str(pkg), "--json"] + (["--out", str(out)] if out else [])
    e = dict({name: os.environ[name] for name in (
                 'PATH', 'HOME', 'USERPROFILE', 'HOMEDRIVE', 'HOMEPATH', 'TMPDIR',
                 'TMP', 'TEMP', 'SystemRoot', 'SYSTEMROOT', 'SystemDrive', 'COMSPEC',
                 'ComSpec', 'PATHEXT', 'LANG', 'LC_ALL', 'LC_CTYPE', 'TZ',
                 'PYTHONUTF8', 'PYTHONIOENCODING', 'PYTHONNOUSERSITE', 'PYTHONSAFEPATH', 'GIT_CONFIG_NOSYSTEM', 'GIT_CONFIG_GLOBAL',
                 'GIT_CONFIG_SYSTEM', 'SSL_CERT_FILE', 'SSL_CERT_DIR', 'REQUESTS_CA_BUNDLE', 'CURL_CA_BUNDLE', 'CI',
                 'GITHUB_ACTIONS',
             ) if name in os.environ}, PYTHONDONTWRITEBYTECODE="1")
    e.update(env or {})
    try:
        r = subprocess.run(a, capture_output=True, text=True, timeout=600, env=e)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 99, None, str(exc)
    try:
        rep = json.loads(r.stdout) if r.stdout.strip() else None
    except json.JSONDecodeError:
        rep = None
    return r.returncode, rep, r.stderr


def camp(rep, cid):
    for c in (rep or {}).get("campaigns", []) or []:
        if c.get("id") == cid:
            return c
    return {}


def fig(rep, cid):
    c = camp(rep, cid)
    return tuple(c.get(k) for k in ("spend", "conversions", "attributed_revenue", "cpa", "roas"))


def codes(rep):
    return sorted({f.get("code") for f in (rep or {}).get("findings", []) or []})


def copy_fixture(name, dst):
    shutil.copytree(FIX / name, dst)
    return dst / "campaign.json"


def ratio(a, b, q):
    return None if b == 0 else str((Decimal(a) / Decimal(b)).quantize(q, rounding=ROUND_HALF_EVEN))


# ----------------------------------------------------------------- generated books
def contracts(d):
    for n in ("spend-contract.json", "orders-contract.json"):
        shutil.copy(FIX / "september" / n, d / n)


def write_book(d, campaigns, spend_rows, orders, touches, convs, creatives=None, finance=None, as_of="2026-10-02T00:00:00Z"):
    d.mkdir(parents=True, exist_ok=True)
    contracts(d)
    pkg = {"schema": "solaris.campaign-ledger/1", "as_of": as_of,
           "window": {"start": "2026-09-01T00:00:00Z", "end": "2026-10-01T00:00:00Z"},
           "spend": {"contract": "spend-contract.json"}, "orders": {"contract": "orders-contract.json"},
           "campaigns": campaigns, "touches": "touches.jsonl", "conversions": "conversions.jsonl"}
    if creatives is not None:
        (d / "creatives.json").write_text(json.dumps({"creatives": creatives}))
        pkg["creatives"] = "creatives.json"
    if finance is not None:
        pkg["finance"] = finance
    (d / "campaign.json").write_text(json.dumps(pkg, indent=1))
    with open(d / "spend.csv", "w") as f:
        f.write("campaign_id,day,spend,currency,loaded_at,updated_at\n")
        for r in spend_rows:
            f.write(",".join(r) + "\n")
    with open(d / "orders.csv", "w") as f:
        f.write("order_id,amount,currency,status,event_time,loaded_at,updated_at\n")
        for r in orders:
            f.write(",".join(r) + "\n")
    with open(d / "touches.jsonl", "w") as f:
        for t in touches:
            f.write(json.dumps(t) + "\n")
    with open(d / "conversions.jsonl", "w") as f:
        for c in convs:
            f.write(json.dumps(c) + "\n")
    return d / "campaign.json"


def C(cid, cur="USD", click=7, view=0, total="100000.00", daily="5000.00", fs="2026-09-01", fe="2026-09-30"):
    return {"id": cid, "name": cid, "currency": cur, "flight_start": fs, "flight_end": fe, "budget_total": total,
            "budget_daily": daily, "click_window_days": click, "view_window_days": view}


def touch(tid, cid, user, kind, at):
    return {"touch_id": tid, "campaign_id": cid, "user": user, "kind": kind, "at": iso(at), "loaded_at": iso(at + dt.timedelta(minutes=5))}


def conv(eid, oid, user, at, source="server", value=None, cur=None):
    e = {"event_id": eid, "order_id": oid, "user": user, "at": iso(at), "loaded_at": iso(at + dt.timedelta(minutes=5)), "source": source}
    if value is not None:
        e["value"], e["currency"] = value, cur
    return e


def order(oid, amount, cur, at, status="paid"):
    return [oid, amount, cur, status, iso(at), iso(at + dt.timedelta(hours=1)), iso(at)]


def random_book(seed, n_orders, d):
    """Every order's campaign is decided first; touches and events are then drawn to make that answer true."""
    rnd = random.Random(seed)
    cams = [C("S1", click=7, view=0), C("S2", click=3, view=1), C("S3", click=1, view=1), C("E1", cur="EUR", click=7)]
    cmap = {c["id"]: c for c in cams}
    exp = {c["id"]: {"spend": Decimal(0), "orders": 0, "rev": Decimal(0)} for c in cams}
    unattr = {"USD": Decimal(0), "EUR": Decimal(0)}
    total = {"USD": Decimal(0), "EUR": Decimal(0)}
    spend_rows = []
    for c in cams:
        for dday in range(30):
            dd = (T0 + dt.timedelta(days=dday)).date().isoformat()
            v = Decimal(rnd.randint(100, 40000)) / 100
            ld = iso(T0 + dt.timedelta(days=dday + 1))
            if rnd.random() < 0.2:      # restated later: old version first, newer one wins
                old = Decimal(rnd.randint(100, 40000)) / 100
                spend_rows.append([c["id"], dd, str(old), c["currency"], ld, iso(T0 + dt.timedelta(days=dday, hours=1))])
            row = [c["id"], dd, str(v), c["currency"].lower() if rnd.random() < 0.1 else c["currency"], ld, iso(T0 + dt.timedelta(days=dday, hours=2))]
            spend_rows.append(row)
            if rnd.random() < 0.1:
                spend_rows.append(list(row))
            exp[c["id"]]["spend"] += v
    orders, touches, convs = [], [], []
    tn = 0
    for i in range(n_orders):
        oid, user = "O%d" % i, "u%d" % i
        cur = "EUR" if rnd.random() < 0.15 else "USD"
        at = T0 + dt.timedelta(days=rnd.randint(9, 28), seconds=rnd.randint(0, 86399))
        val = Decimal(rnd.randint(500, 50000)) / 100
        orders.append(order(oid, str(val), cur, at))
        if rnd.random() < 0.05:
            orders.append(order(oid, str(val), cur, at))
        total[cur] += val
        pool = [c for c in cams if c["currency"] == cur]
        scen = rnd.choice(["click", "click", "click", "view", "stale", "none", "tie", "after"])
        if scen == "view" and not any(c["view_window_days"] for c in pool):
            scen = "click"
        def T(cid, kind, t):
            nonlocal tn
            tn += 1
            touches.append(touch("T%d" % tn, cid, user, kind, t))
        winner = None
        if scen == "click":
            c = rnd.choice(pool)
            w = c["click_window_days"] * 86400
            back = rnd.choice([0, w, rnd.randint(0, w)])
            T(c["id"], "click", at - dt.timedelta(seconds=back))
            other = rnd.choice(pool)
            T(other["id"], "click", at - dt.timedelta(seconds=back + rnd.randint(1, 3600)))   # older click loses
            T(other["id"], "view", at - dt.timedelta(seconds=rnd.randint(0, 60)))             # a view never beats a click
            winner = c
        elif scen == "view":
            c = rnd.choice([c for c in pool if c["view_window_days"]])
            w = c["view_window_days"] * 86400
            T(c["id"], "view", at - dt.timedelta(seconds=rnd.choice([0, w, rnd.randint(0, w)])))
            winner = c
        elif scen == "stale":
            c = rnd.choice(pool)
            T(c["id"], "click", at - dt.timedelta(seconds=c["click_window_days"] * 86400 + 1))
            if c["view_window_days"] == 0:
                T(c["id"], "view", at - dt.timedelta(seconds=10))
        elif scen == "tie" and len(pool) > 1:
            a, b = rnd.sample(pool, 2)
            t = at - dt.timedelta(seconds=rnd.randint(0, 3600))
            T(a["id"], "click", t)
            T(b["id"], "click", t)
        elif scen == "after":
            c = rnd.choice(pool)
            T(c["id"], "click", at + dt.timedelta(seconds=1))
        if scen != "none":
            k = rnd.choice(["one", "pair", "copy"])
            e = conv("E%d" % i, oid, user, at, value=str(val + (1 if rnd.random() < 0.2 else 0)), cur=cur)
            convs.append(e)
            if k == "pair":
                convs.append(conv("E%db" % i, oid, user, at + dt.timedelta(seconds=rnd.randint(1, 30)), source="pixel"))
            if k == "copy":
                convs.append(dict(e))
        if winner:
            exp[winner["id"]]["orders"] += 1
            exp[winner["id"]]["rev"] += val
        else:
            unattr[cur] += val
    rnd.shuffle(spend_rows)
    rnd.shuffle(touches)
    rnd.shuffle(convs)
    pkg = write_book(d, cams, spend_rows, orders, touches, convs)
    want = {cid: (str(e["spend"].quantize(Q2)), e["orders"], str(e["rev"].quantize(Q2)),
                  None if e["orders"] == 0 else str((e["spend"] / e["orders"]).quantize(Q2, rounding=ROUND_HALF_EVEN)),
                  ratio(e["rev"], e["spend"], Q4)) for cid, e in exp.items()}
    return pkg, want, {k: str(v.quantize(Q2)) for k, v in unattr.items()}, {k: str(v.quantize(Q2)) for k, v in total.items()}


# ----------------------------------------------------------------- checks
def main():
    argv = sys.argv[1:]
    seeds = 3
    if argv[:1] == ["--seeds"]:
        seeds, argv = int(argv[1]), argv[2:]
    if argv[:1] == ["--"]:
        argv = argv[1:]
    cmd = argv or [sys.executable, str(ROOT / "employees/marketing/paid-ads-manager/campaign_ledger.py")]
    tmp = Path(tempfile.mkdtemp(prefix="g35-oracle-"))
    results = []

    def check(name, fn):
        try:
            ok, why = fn()
        except Exception as exc:  # a crash in the tool's output shape is a failure, not an oracle error
            ok, why = False, "%s: %s" % (exc.__class__.__name__, exc)
        results.append(ok)
        print("%s %s%s" % ("PASS" if ok else "FAIL", name, "" if ok else "  (" + str(why)[:300] + ")"))

    def o1():
        rc, rep, _ = run(cmd, copy_fixture("clean", tmp / "o1"))
        want = ("30.00", 2, "75.00", "15.00", "2.5000")
        cr = [(c.get("id"), c.get("status")) for c in (rep or {}).get("creatives", [])]
        ok = rc == 0 and rep and rep.get("status") == "reconciled" and fig(rep, "C-search") == want and not codes(rep) \
            and cr == [("K1", "ready_for_human_review")]
        return ok, (rc, fig(rep, "C-search"), codes(rep), cr)
    check("o1 clean control: exact figures, exit 0, truthful creative ready", o1)

    SEPT = {"C-search": ("73.00", 2, "180.00", "36.50", "2.4658"), "C-social": ("25.00", 2, "110.00", "12.50", "4.4000"),
            "C-eu": ("8.00", 1, "45.00", "8.00", "5.6250")}
    SEPT_CODES = sorted(["spend_export_gaps", "spend_for_unknown_campaign", "rejected_touch_rows", "late_conversion_rows",
                         "touches_for_unknown_campaign", "conversion_without_order", "over_daily_budget", "spend_outside_flight",
                         "order_value_differs_from_recognized_revenue", "creatives_blocked"])
    SEPT_UN = {"ambiguous_touch": {"USD": {"orders": 1, "value": "25.00"}}, "no_conversion_event": {"USD": {"orders": 1, "value": "200.00"}},
               "no_eligible_touch": {"USD": {"orders": 1, "value": "40.00"}}}
    SEPT_CR = {"K1": "held_unverified", "K2": "held_unverified", "K3": "blocked", "K4": "blocked", "K5": "blocked", "K6": "blocked"}

    def o2():
        rc, rep, _ = run(cmd, copy_fixture("september", tmp / "o2"))
        got = {k: fig(rep, k) for k in SEPT}
        cr = {c.get("id"): c.get("status") for c in (rep or {}).get("creatives", [])}
        un = (rep or {}).get("unattributed")
        fin = [f for f in (rep or {}).get("findings", []) if f.get("code") == "order_value_differs_from_recognized_revenue"]
        chk = (rep or {}).get("checks", {}).get("USD", {})
        ok = rc == 1 and got == SEPT and codes(rep) == SEPT_CODES and un == SEPT_UN and cr == SEPT_CR \
            and fin and fin[0].get("difference") == "60.00" and chk.get("spend_export_total") == "102.00" and chk.get("unassigned_spend") == "4.00"
        return ok, (rc, got, codes(rep), un, cr)
    check("o2 september hand-worked: spend, attribution, findings, creatives, finance difference 60.00", o2)

    def o3():
        d = tmp / "o3"
        pkg = copy_fixture("september", d)
        for name in ("touches.jsonl", "conversions.jsonl"):
            lines = (d / name).read_text().splitlines()
            good = [l for l in lines if l.endswith("}")]
            bad = [l for l in lines if not l.endswith("}")]
            mix = good * 3 + bad
            random.Random(7).shuffle(mix)
            (d / name).write_text("\n".join(mix) + "\n")
        raw = (d / "spend.csv").read_bytes().decode("utf-8-sig").splitlines()
        body = raw[1:] * 2
        random.Random(8).shuffle(body)
        (d / "spend.csv").write_text("\n".join([raw[0]] + body) + "\n")
        rc, rep, _ = run(cmd, pkg)
        got = {k: fig(rep, k) for k in SEPT}
        return rc == 1 and got == SEPT and (rep or {}).get("unattributed") == SEPT_UN, (rc, got)
    check("o3 every row re-delivered three times and shuffled: same figures", o3)

    def o4():
        t = dt.datetime(2026, 9, 10, 12, tzinfo=UTC)
        cams = [C("A", click=7, view=1), C("B", click=7, view=0)]
        o, tc, cv, want_a, want_b = [], [], [], 0, 0
        cases = [  # (campaign, kind, conversion offset from touch, attributed?)
            ("A", "click", dt.timedelta(days=7), True), ("A", "click", dt.timedelta(days=7, seconds=1), False),
            ("A", "click", dt.timedelta(seconds=-1), False), ("A", "view", dt.timedelta(days=1), True),
            ("A", "view", dt.timedelta(days=1, seconds=1), False), ("B", "view", dt.timedelta(seconds=1), False),
            ("B", "click", dt.timedelta(0), True)]
        for i, (cid, kind, off, yes) in enumerate(cases):
            u, oid = "w%d" % i, "W%d" % i
            tc.append(touch("t%d" % i, cid, u, kind, t))
            cv.append(conv("e%d" % i, oid, u, t + off))
            o.append(order(oid, "10.00", "USD", t + off))
            want_a += yes and cid == "A"
            want_b += yes and cid == "B"
        spend = [["A", "2026-09-10", "10.00", "USD", "2026-09-11T00:00:00Z", "2026-09-11T00:00:00Z"],
                 ["B", "2026-09-10", "10.00", "USD", "2026-09-11T00:00:00Z", "2026-09-11T00:00:00Z"]]
        rc, rep, err = run(cmd, write_book(tmp / "o4", cams, spend, o, tc, cv))
        ga, gb = camp(rep, "A").get("conversions"), camp(rep, "B").get("conversions")
        return rc == 0 and ga == want_a == 2 and gb == want_b == 1, (rc, ga, gb, want_a, want_b, err[-200:])
    check("o4 window edges: exactly 7 days and 1 day count, one second more or a touch after the conversion does not, view 0 = none", o4)

    def o5():
        bad = []
        for s in range(seeds):
            pkg, want, un, tot = random_book(1000 + s, 1500, tmp / ("o5-%d" % s))
            rc, rep, err = run(cmd, pkg)
            got = {k: fig(rep, k) for k in want}
            gun = {cur: str(sum(Decimal(u.get(cur, {}).get("value", "0")) for u in (rep or {}).get("unattributed", {}).values()))
                   for cur in un}
            gun = {k: str(Decimal(v).quantize(Q2)) for k, v in gun.items()}
            if rc != 0 or got != want or gun != un:
                bad.append((s, rc, [(k, got[k], want[k]) for k in want if got[k] != want[k]][:2], gun, un, err[-200:]))
        return not bad, bad
    check("o5 %d seeded books (1500 orders, restatements, pixel+server pairs, ties, stale and after-conversion clicks) equal construction" % seeds, o5)

    def o6():
        cams = [C("A", total="30.00", daily="10.00"), C("B", total="30.00", daily="10.00")]
        spend = [["A", "2026-09-%02d" % d, "10.00", "USD", "2026-09-20T00:00:00Z", "2026-09-20T00:00:00Z"] for d in (1, 2, 3)]
        spend += [["B", "2026-09-01", "10.01", "USD", "2026-09-20T00:00:00Z", "2026-09-20T00:00:00Z"],
                  ["B", "2026-09-02", "10.00", "USD", "2026-09-20T00:00:00Z", "2026-09-20T00:00:00Z"],
                  ["B", "2026-09-03", "10.00", "USD", "2026-09-20T00:00:00Z", "2026-09-20T00:00:00Z"]]
        rc, rep, _ = run(cmd, write_book(tmp / "o6", cams, spend, [], [], []))
        fs = (rep or {}).get("findings", [])
        daily = [f for f in fs if f.get("code") == "over_daily_budget"]
        tot = [f for f in fs if f.get("code") == "over_total_budget"]
        ok = rc == 1 and [f.get("campaign") for f in daily] == ["B"] and [d.get("day") for d in daily[0].get("days", [])] == ["2026-09-01"] \
            and [f.get("campaign") for f in tot] == ["B"] and camp(rep, "A").get("budget_remaining") == "0.00" \
            and camp(rep, "B").get("budget_remaining") == "-0.01"
        return ok, (rc, daily, tot)
    check("o6 budgets: spend equal to the cap is fine, one cent over is named (daily and total)", o6)

    def o7():
        t = dt.datetime(2026, 9, 10, 12, tzinfo=UTC)
        cams = [C("A")]
        spend = [["A", "2026-09-10", "3.00", "USD", "2026-09-11T00:00:00Z", "2026-09-11T00:00:00Z"]]
        orders_ = [order("X1", "7.00", "USD", t)]
        tc = [touch("t1", "A", "v1", "click", t - dt.timedelta(hours=1))]
        cv = [conv("e1", "X1", "v1", t)]
        cr = [{"id": "ok1", "campaign_id": "A", "channel": "search", "headline": "Return of 2.33x", "body": "1 order.",
               "claims": [{"text": "2.33x", "figure": "campaign:A:roas"}, {"text": "1 order", "figure": "campaign:A:conversions"}]},
              {"id": "ok2", "campaign_id": "A", "channel": "social", "material_connection": "employee", "disclosure": "#employee",
               "headline": "Made by our team #employee", "body": "No numbers here.", "claims": []},
              {"id": "bad_round", "campaign_id": "A", "channel": "search", "headline": "Return of 2.34x", "body": "",
               "claims": [{"text": "2.34x", "figure": "campaign:A:roas"}]},
              {"id": "bad_unclaimed", "campaign_id": "A", "channel": "search", "headline": "Save 40 percent", "body": "", "claims": []},
              {"id": "bad_publish", "campaign_id": "A", "channel": "search", "headline": "Hi", "body": "", "claims": [], "status": "live"},
              {"id": "bad_disclosure", "campaign_id": "A", "channel": "social", "material_connection": "paid",
               "headline": "Loved by creators", "body": "", "claims": []},
              {"id": "bad_figure", "campaign_id": "A", "channel": "search", "headline": "CTR 5", "body": "",
               "claims": [{"text": "CTR 5", "figure": "campaign:A:ctr"}]}]
        rc, rep, err = run(cmd, write_book(tmp / "o7", cams, spend, orders_, tc, cv, creatives=cr))
        st = {c.get("id"): c.get("status") for c in (rep or {}).get("creatives", [])}
        want = {"ok1": "ready_for_human_review", "ok2": "ready_for_human_review", "bad_round": "blocked", "bad_unclaimed": "blocked",
                "bad_publish": "blocked", "bad_disclosure": "blocked", "bad_figure": "blocked"}
        return rc == 1 and st == want and camp(rep, "A").get("roas") == "2.3333", (rc, st, err[-200:])
    check("o7 creatives: rounded true claims pass, wrong rounding, unclaimed numbers, publish status, missing disclosure and unknown figures block", o7)

    def o8():
        good = copy_fixture("clean", tmp / "o8")
        out = tmp / "o8-out"
        rc0, _, _ = run(cmd, good, out=out)
        if rc0 != 0 or not (out / "report.json").is_file():
            return False, ("first run", rc0)
        before = {p.name: p.read_bytes() for p in out.iterdir()}
        src = json.loads(good.read_text())
        bads = []
        def variant(name, mutate=None, text=None):
            d = tmp / ("o8-" + name)
            shutil.copytree(good.parent, d)
            if text is not None:
                (d / "campaign.json").write_text(text)
            else:
                p = json.loads(json.dumps(src))
                mutate(p, d)
                (d / "campaign.json").write_text(json.dumps(p))
            return d / "campaign.json"
        cases = [
            variant("float", text=good.read_text().replace('"300.00"', '300.00')),
            variant("unknown_key", lambda p, d: p.update(spend_now=True)),
            variant("escape", lambda p, d: p.update(touches="../o8/touches.jsonl")),
            variant("missing", lambda p, d: p.update(conversions="nope.jsonl")),
            variant("dupe", lambda p, d: p["campaigns"].append(dict(p["campaigns"][0]))),
            variant("badjson", text="{\"schema\": "),
            variant("window", lambda p, d: p.update(window={"start": "2026-09-02T00:00:00Z", "end": "2026-10-01T00:00:00Z"})),
            variant("metric", lambda p, d: (d / "orders-contract.json").write_text(
                (d / "orders-contract.json").read_text().replace('"by": ["order_id", "currency"]', '"by": ["currency"]'))),
            variant("g13_invalid", lambda p, d: (d / "spend-contract.json").write_text("{}")),
        ]
        for pkg in cases:
            rc, _, err = run(cmd, pkg, out=out)
            after = {p.name: p.read_bytes() for p in out.iterdir()}
            if rc != 2 or after != before:
                bads.append((pkg.parent.name, rc, err[-120:]))
        rc, _, _ = run(cmd, good, out=good.parent / "inside")
        if rc != 2:
            bads.append(("out_inside_package", rc))
        (out / "report.json").unlink()
        rc2, _, _ = run(cmd, good, out=out)
        if rc2 != 0 or not (out / "report.json").is_file() or not (out / "campaign-brief.md").is_file():
            bads.append(("recovery", rc2))
        md = (out / "campaign-brief.md").read_text() if (out / "campaign-brief.md").is_file() else ""
        if "INTERNAL DRAFT" not in md or "Nothing was published" not in md:
            bads.append(("brief_label", md[:80]))
        return not bads, bads
    check("o8 nine invalid packages and --out inside the package exit 2 and keep the previous report; recovery writes both files", o8)

    def o9():
        d = tmp / "o9"
        pkg = copy_fixture("september", d)
        sums = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in d.rglob("*") if p.is_file()}
        guard = tmp / "noguard"
        guard.mkdir()
        (guard / "sitecustomize.py").write_text(
            "import socket\nclass _S(socket.socket):\n    def connect(self, *a):\n        raise OSError('network blocked by G35 oracle')\n"
            "socket.socket = _S\nsocket.create_connection = lambda *a, **k: (_ for _ in ()).throw(OSError('network blocked'))\n")
        env = {"PYTHONPATH": str(guard)}
        procs = []
        for i in range(4):
            a = cmd + ["reconcile", str(pkg), "--json", "--out", str(tmp / ("o9-out%d" % i))]
            procs.append(subprocess.Popen(a, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=dict({name: os.environ[name] for name in (
                                                                                                          'PATH', 'HOME', 'USERPROFILE', 'HOMEDRIVE', 'HOMEPATH', 'TMPDIR',
                                                                                                          'TMP', 'TEMP', 'SystemRoot', 'SYSTEMROOT', 'SystemDrive', 'COMSPEC',
                                                                                                          'ComSpec', 'PATHEXT', 'LANG', 'LC_ALL', 'LC_CTYPE', 'TZ',
                                                                                                          'PYTHONUTF8', 'PYTHONIOENCODING', 'PYTHONNOUSERSITE', 'PYTHONSAFEPATH', 'GIT_CONFIG_NOSYSTEM', 'GIT_CONFIG_GLOBAL',
                                                                                                          'GIT_CONFIG_SYSTEM', 'SSL_CERT_FILE', 'SSL_CERT_DIR', 'REQUESTS_CA_BUNDLE', 'CURL_CA_BUNDLE', 'CI',
                                                                                                          'GITHUB_ACTIONS',
                                                                                                      ) if name in os.environ}, PYTHONDONTWRITEBYTECODE="1", **env)))
        outs = [p.communicate(timeout=600) for p in procs]
        rcs = [p.returncode for p in procs]
        reps = [(tmp / ("o9-out%d" % i) / "report.json").read_bytes() if (tmp / ("o9-out%d" % i) / "report.json").is_file() else b"" for i in range(4)]
        after = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in d.rglob("*") if p.is_file()}
        ok = rcs == [1, 1, 1, 1] and len(set(reps)) == 1 and reps[0] and after == sums
        return ok, (rcs, len(set(reps)), after == sums, outs[0][1][-200:])
    check("o9 four parallel runs with network blocked give identical reports; package files byte-identical", o9)

    def o10():
        pkg, want, un, tot = random_book(77, 20000, tmp / "o10")
        t = time.time()
        rc, rep, _ = run(cmd, pkg)
        el = time.time() - t
        got = {k: fig(rep, k) for k in want}
        return rc == 0 and got == want and el < 120, (rc, round(el, 1))
    check("o10 scale: 20 000 orders (36 035 touches, 29 159 conversion events) equal construction in under 120 s", o10)

    def o11():
        d = tmp / "o11"
        t = dt.datetime(2026, 9, 10, 12, tzinfo=UTC)
        cams = [C("A")]
        o = [order("Y1", "10.00", "USD", t), order("Y2", "20.00", "USD", t)]
        tc = [touch("t1", "A", "a1", "click", t), touch("t2", "A", "a2", "click", t), touch("t3", "A", "a3", "click", t)]
        cv = [conv("e1", "Y1", "a1", t), conv("e1", "Y1", "a1", t + dt.timedelta(seconds=9)),   # same id, other body
              conv("e2", "Y2", "a2", t), conv("e3", "Y2", "a3", t)]                             # two users for one order
        rc, rep, _ = run(cmd, write_book(d, cams, [], o, tc, cv))
        un = (rep or {}).get("unattributed", {})
        ok = rc == 1 and {"conflicting_conversion_ids", "order_user_conflict"} <= set(codes(rep)) \
            and camp(rep, "A").get("conversions") == 0 and un.get("user_conflict", {}).get("USD", {}).get("value") == "20.00" \
            and un.get("no_conversion_event", {}).get("USD", {}).get("value") == "10.00"
        return ok, (rc, codes(rep), un)
    check("o11 an event id reused with another body is dropped and named; an order claimed by two users is not attributed", o11)

    def o12():
        d = tmp / "o12"
        pkg = copy_fixture("clean", d)
        (d / "finance" / "credits.csv").write_text("credit_id,invoice_id,kind,currency,amount,issued_at,loaded_at\n"
                                                  "CN2,O2,credit_note,USD,25.00,2026-09-05T10:00:00Z,2026-09-05T11:00:00Z\n"
                                                  "R2,O2,refund,USD,25.00,2026-09-05T10:00:00Z,2026-09-05T11:00:00Z\n")
        (d / "finance" / "bank.csv").write_text("currency,cash_in,cash_out\nUSD,75.00,25.00\n")
        rc, rep, _ = run(cmd, pkg)
        fs = [f for f in (rep or {}).get("findings", []) if f.get("code") == "order_value_differs_from_recognized_revenue"]
        ok = rc == 1 and fs and fs[0].get("difference") == "25.00" and fig(rep, "C-search") == ("30.00", 2, "75.00", "15.00", "2.5000") \
            and [c.get("status") for c in rep.get("creatives", [])] == ["held_unverified"]
        return ok, (rc, fs, codes(rep))
    check("o12 a credit note and refund in the CFO books (G14) is named against order value and holds the creative", o12)

    shutil.rmtree(tmp, ignore_errors=True)
    n, k = len(results), sum(results)
    print("%s %d/%d" % ("ACCEPTED" if k == n else "REJECTED", k, n))
    return 0 if k == n else 1


if __name__ == "__main__":
    sys.exit(main())
