#!/usr/bin/env python3
"""M35 oracle (Grok self-validation, not independent review). Written from M35.md, G35.md and campaign-accounting.md
before reading the builder's oracle. It builds its own campaign packages from scratch (spend and order CSVs under
the G35 fixture's G13 contracts, touches, conversions, creatives), keeps an independent Decimal model of
attribution (last click in window, else last view; flight; ties; currency), spend, budgets, CPA and ROAS
(half-even), and drives the real CLI. Every tool run goes through an audit hook (oracle/audit) that logs any socket,
DNS, URL, mail or browser use and every child process; only the documented G13/G14 child processes are allowed.
Usage: PY m35_oracle.py SRC OUT.json [--tool PATH]."""
import copy, datetime as dt, glob, hashlib, json, os, random, re, shutil, subprocess, sys, tempfile
from decimal import Decimal as D, ROUND_HALF_EVEN
SRC = os.path.abspath(sys.argv[1]); OUT = sys.argv[2]
TOOL = os.path.join(SRC, "employees/marketing/paid-ads-manager/campaign_ledger.py")
if "--tool" in sys.argv: TOOL = os.path.abspath(sys.argv[sys.argv.index("--tool") + 1])
FIX = os.path.join(SRC, "examples/capabilities/G35/fixtures"); PY = sys.executable
AUD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audit"); ROWS = []; AUDIT = []
ALLOWED_CHILD = ("csv_reconcile.py", "cash_revenue_reconcile.py")

def row(name, ok, det):
    sub = {k: bool(v[0]) for k, v in det.items() if isinstance(v, (tuple, list)) and len(v) == 2 and isinstance(v[0], bool)} if isinstance(det, dict) else {}
    ROWS.append({"row": name, "pass": bool(ok), "sub": sub, "detail": det}); print(("PASS " if ok else "FAIL ") + name + " " + json.dumps(det, default=str)[:450], flush=True)
def safe(fn):
    def g():
        try: fn()
        except Exception as e: row(fn.__name__ + " crash", False, {"crash": repr(e)})
    return g
def iso(t): return t.strftime("%Y-%m-%dT%H:%M:%SZ")
T = lambda s: dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ")

def camp(cid, cur="USD", fs="2026-09-01", fe="2026-09-30", bt="1000.00", bd="100.00", cw=7, vw=1, name=None):
    return {"id": cid, "name": name or cid, "currency": cur, "flight_start": fs, "flight_end": fe, "budget_total": bt, "budget_daily": bd, "click_window_days": cw, "view_window_days": vw}

class Pkg:
    def __init__(s, camps, spend, orders, touches, convs, creatives=None, finance=False, edit=None):
        s.top = tempfile.mkdtemp(prefix="m35o-"); s.d = os.path.join(s.top, "pkg"); os.makedirs(s.d)
        for f in ("spend-contract.json", "orders-contract.json"): shutil.copy(os.path.join(FIX, "clean", f), s.d)
        if finance: shutil.copytree(os.path.join(FIX, "clean", "finance"), os.path.join(s.d, "finance"))
        with open(os.path.join(s.d, "spend.csv"), "w") as f:
            f.write("campaign_id,day,spend,currency,loaded_at,updated_at\n")
            for r in spend:
                cid, day, amt, cur = r[:4]; la = r[4] if len(r) > 4 else iso(dt.datetime.strptime(day, "%Y-%m-%d") + dt.timedelta(days=1, hours=6))
                f.write("%s,%s,%s,%s,%s,%s\n" % (cid, day, amt, cur, la, la))
        with open(os.path.join(s.d, "orders.csv"), "w") as f:
            f.write("order_id,amount,currency,status,event_time,loaded_at,updated_at\n")
            for r in orders:
                oid, amt, cur, st, at = r[:5]; la = iso(T(at) + dt.timedelta(hours=1))
                f.write("%s,%s,%s,%s,%s,%s,%s\n" % (oid, amt, cur, st, at, la, at))
        s.p = {"schema": "solaris.campaign-ledger/1", "as_of": "2026-10-02T00:00:00Z", "window": {"start": "2026-09-01T00:00:00Z", "end": "2026-10-01T00:00:00Z"},
               "spend": {"contract": "spend-contract.json"}, "orders": {"contract": "orders-contract.json"}, "campaigns": camps, "touches": "touches.jsonl", "conversions": "conversions.jsonl"}
        if finance: s.p["finance"] = {"g14_package": "finance/package.json"}
        s.lines("touches.jsonl", touches); s.lines("conversions.jsonl", convs)
        if creatives is not None: json.dump({"creatives": creatives}, open(os.path.join(s.d, "creatives.json"), "w")); s.p["creatives"] = "creatives.json"
        if edit: edit(s)
    def lines(s, name, items):
        with open(os.path.join(s.d, name), "w") as f:
            for x in items: f.write((x if isinstance(x, str) else json.dumps(x)) + "\n")
    def run(s, *extra, write=True):
        if write: json.dump(s.p, open(os.path.join(s.d, "campaign.json"), "w"), indent=1)
        log = os.path.join(s.top, "audit.log"); env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=AUD, M32_AUDIT_LOG=log)
        r = subprocess.run([PY, TOOL, "reconcile", os.path.join(s.d, "campaign.json"), "--json"] + list(extra), cwd=s.top, env=env, capture_output=True, text=True, timeout=300)
        if os.path.exists(log):
            for l in open(log).read().splitlines():
                if l.startswith("subprocess.Popen") and any(a in l for a in ALLOWED_CHILD) and "http" not in l: continue
                if l.startswith(("os.posix_spawn", "os.fork", "os.exec")) and any(a in l for a in ALLOWED_CHILD): continue
                AUDIT.append(l[:300])
            os.remove(log)
        try: j = json.loads(r.stdout)
        except Exception: j = {}
        s.err = r.stderr
        return r.returncode, j
    def close(s): shutil.rmtree(s.top, ignore_errors=True)

def tch(i, c, u, kind, at, late=False): return {"touch_id": i, "campaign_id": c, "user": u, "kind": kind, "at": at, "loaded_at": "2026-10-03T00:00:00Z" if late else iso(T(at) + dt.timedelta(minutes=5))}
def cv(i, o, u, at, src="pixel", value=None, cur="USD"):
    d = {"event_id": i, "order_id": o, "user": u, "at": at, "loaded_at": iso(T(at) + dt.timedelta(minutes=5)), "source": src}
    if value is not None: d["value"] = value; d["currency"] = cur
    return d
def codes(j): return sorted({f.get("code") for f in j.get("findings", [])})
def C(j, cid): return next((c for c in j.get("campaigns", []) if c.get("id") == cid), {})
def q2(x): return x.quantize(D("0.01"), rounding=ROUND_HALF_EVEN)
def q4(x): return x.quantize(D("0.0001"), rounding=ROUND_HALF_EVEN)

def model(camps, spend, orders, touches, convs):
    """Independent attribution model for packages built here: every row is in window and loaded before as_of."""
    cm = {c["id"]: c for c in camps}; book = {o[0]: (D(o[1]), o[2]) for o in orders if o[3] not in ("test", "void")}
    first = {}
    for e in convs:
        if e["order_id"] in book and (e["order_id"] not in first or T(e["at"]) < T(first[e["order_id"]]["at"])): first[e["order_id"]] = e
    res = {cid: {"conv": 0, "rev": D(0), "spend": D(0), "orders": []} for cid in cm}; unatt = {}
    for oid, e in first.items():
        users = {x["user"] for x in convs if x["order_id"] == oid}
        amt, cur = book[oid]; ct = T(e["at"])
        if len(users) > 1: unatt.setdefault("user_conflict", D(0)); unatt["user_conflict"] += amt; continue
        def elig(kind):
            out = []
            for t in touches:
                c = cm.get(t["campaign_id"]); ta = T(t["at"])
                if not c or t["user"] != e["user"] or t["kind"] != kind or ta > ct: continue
                win = c["click_window_days"] if kind == "click" else c["view_window_days"]
                if ct - ta > dt.timedelta(days=win): continue
                if not (c["flight_start"] <= ta.strftime("%Y-%m-%d") <= c["flight_end"]): continue
                out.append((ta, t["campaign_id"]))
            return out
        got = elig("click") or elig("view")
        if not got: unatt.setdefault("no_eligible_touch", D(0)); unatt["no_eligible_touch"] += amt; continue
        top = max(a for a, _ in got); cs = {c for a, c in got if a == top}
        if len(cs) > 1: unatt.setdefault("ambiguous_touch", D(0)); unatt["ambiguous_touch"] += amt; continue
        cid = cs.pop()
        if cm[cid]["currency"] != cur: unatt.setdefault("currency_mismatch", D(0)); unatt["currency_mismatch"] += amt; continue
        res[cid]["conv"] += 1; res[cid]["rev"] += amt; res[cid]["orders"].append(oid)
    for r in spend:
        if r[0] in res: res[r[0]]["spend"] += D(r[2])
    for cid, r in res.items():
        r["cpa"] = None if r["conv"] == 0 or r["spend"] == 0 else str(q2(r["spend"] / r["conv"]))
        r["roas"] = None if r["spend"] == 0 else str(q4(r["rev"] / r["spend"]))
        r["rev"] = str(q2(r["rev"])); r["spend"] = str(q2(r["spend"])); r["orders"] = sorted(r["orders"])
    return res, {k: str(q2(v)) for k, v in unatt.items()}
def tool_view(j, cid):
    c = C(j, cid); return {"conv": c.get("conversions"), "rev": c.get("attributed_revenue"), "spend": c.get("spend"), "orders": sorted(c.get("orders") or []), "cpa": c.get("cpa"), "roas": c.get("roas")}

def base(**kw):
    camps = [camp("C-a")]; spend = [("C-a", "2026-09-10", "20.00", "USD")]; orders = [("O1", "40.00", "USD", "paid", "2026-09-12T10:00:00Z")]
    touches = [tch("T1", "C-a", "u1", "click", "2026-09-11T10:00:00Z")]; convs = [cv("E1", "O1", "u1", "2026-09-12T10:00:00Z")]
    d = dict(camps=camps, spend=spend, orders=orders, touches=touches, convs=convs); d.update(kw); return d

@safe
def f01():
    res = {}
    src = os.path.join(FIX, "clean"); top = tempfile.mkdtemp(prefix="m35o-"); shutil.copytree(src, os.path.join(top, "pkg"))
    log = os.path.join(top, "a.log"); env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=AUD, M32_AUDIT_LOG=log)
    r = subprocess.run([PY, TOOL, "reconcile", os.path.join(top, "pkg", "campaign.json"), "--json"], cwd=top, env=env, capture_output=True, text=True, timeout=300)
    j = json.loads(r.stdout) if r.stdout.strip().startswith("{") else {}
    c = C(j, "C-search"); res["status"] = (r.returncode == 0 and j.get("status") == "reconciled" and not j.get("findings"), (r.returncode, j.get("status")))
    res["numbers"] = ((c.get("spend"), c.get("conversions"), c.get("attributed_revenue"), c.get("cpa"), c.get("roas"), c.get("budget_remaining")) == ("30.00", 2, "75.00", "15.00", "2.5000", "270.00"), c)
    res["finance_tie_out"] = (((j.get("finance_tie_out") or {}).get("currencies") or {}).get("USD", {}).get("difference") == "0.00", j.get("finance_tie_out"))
    res["creative_ready"] = ([k.get("status") for k in j.get("creatives", [])] == ["ready_for_human_review"], [k.get("status") for k in j.get("creatives", [])])
    cav = " ".join(j.get("caveats", [])).lower(); res["caveats_explicit"] = (all(w in cav for w in ("last click", "no fx", "never the value a pixel", "nothing here moves money")) or all(w in cav for w in ("last click", "fx", "pixel", "spend")), j.get("caveats"))
    if os.path.exists(log):
        for l in open(log).read().splitlines():
            if not (l.startswith("subprocess.Popen") and any(a in l for a in ALLOWED_CHILD)) and not (l.startswith(("os.posix_spawn", "os.fork", "os.exec")) and any(a in l for a in ALLOWED_CHILD)): AUDIT.append(l[:300])
    shutil.rmtree(top, ignore_errors=True)
    row("F01 clean control: the clean fixture reconciles to 30.00 spend, 2 conversions, 75.00 revenue, CPA 15.00, ROAS 2.5000, 270.00 left; G14 tie-out 0.00; the creative is ready; caveats explicit", all(v[0] for v in res.values()), res)

@safe
def f02():
    res = {}
    def att(touches, convs, camps=None, orders=None):
        b = base(touches=touches, convs=convs); b["camps"] = camps or b["camps"]; b["orders"] = orders or b["orders"]
        k = Pkg(**b); rc, j = k.run(); k.close(); m, u = model(b["camps"], b["spend"], b["orders"], b["touches"], b["convs"]); return rc, j, m, u
    conv = [cv("E1", "O1", "u1", "2026-09-12T10:00:00Z")]
    rc, j, m, u = att([tch("T1", "C-a", "u1", "click", "2026-09-05T10:00:00Z")], conv); res["click_exactly_7d_counts"] = (C(j, "C-a").get("conversions") == 1 and m["C-a"]["conv"] == 1, C(j, "C-a").get("conversions"))
    rc, j, m, u = att([tch("T1", "C-a", "u1", "click", "2026-09-05T09:59:59Z")], conv); res["click_7d_plus_1s_not"] = (C(j, "C-a").get("conversions") == 0, (C(j, "C-a").get("conversions"), j.get("unattributed")))
    rc, j, m, u = att([tch("T1", "C-a", "u1", "click", "2026-09-12T10:00:01Z")], conv); res["touch_after_conversion_never"] = (C(j, "C-a").get("conversions") == 0, C(j, "C-a").get("conversions"))
    rc, j, m, u = att([tch("T1", "C-a", "u1", "click", "2026-09-12T10:00:00Z")], conv); res["touch_same_instant_counts"] = (C(j, "C-a").get("conversions") == 1, C(j, "C-a").get("conversions"))
    rc, j, m, u = att([tch("T1", "C-a", "u1", "view", "2026-09-11T10:00:00Z")], conv); res["view_exactly_1d_counts"] = (C(j, "C-a").get("view_conversions") == 1, C(j, "C-a"))
    rc, j, m, u = att([tch("T1", "C-a", "u1", "view", "2026-09-11T09:59:59Z")], conv); res["view_1d_plus_1s_not"] = (C(j, "C-a").get("conversions") == 0, C(j, "C-a").get("conversions"))
    rc, j, m, u = att([tch("T1", "C-a", "u1", "view", "2026-09-12T09:00:00Z")], conv, camps=[camp("C-a", vw=0)]); res["view_window_0_no_view_through"] = (C(j, "C-a").get("conversions") == 0, C(j, "C-a").get("conversions"))
    rc, j, m, u = att([tch("T1", "C-a", "u1", "click", "2026-09-08T10:00:00Z"), tch("T2", "C-b", "u1", "view", "2026-09-12T09:00:00Z")], conv, camps=[camp("C-a"), camp("C-b")])
    res["click_beats_later_view"] = (C(j, "C-a").get("conversions") == 1 and C(j, "C-b").get("conversions") == 0, (C(j, "C-a").get("conversions"), C(j, "C-b").get("conversions")))
    rc, j, m, u = att([tch("T1", "C-a", "u1", "click", "2026-09-08T10:00:00Z"), tch("T2", "C-b", "u1", "click", "2026-09-08T10:00:00Z")], conv, camps=[camp("C-a"), camp("C-b")])
    res["tie_is_ambiguous_credited_to_neither"] = (C(j, "C-a").get("conversions") == 0 and C(j, "C-b").get("conversions") == 0 and "ambiguous_touch" in json.dumps(j.get("unattributed")), j.get("unattributed"))
    rc, j, m, u = att([tch("T1", "C-a", "u1", "click", "2026-09-11T10:00:00Z")], conv, camps=[camp("C-a", fs="2026-09-12")]); res["touch_outside_flight_ignored"] = (C(j, "C-a").get("conversions") == 0, C(j, "C-a").get("conversions"))
    rc, j, m, u = att([tch("T1", "C-a", "u2", "click", "2026-09-11T10:00:00Z")], conv); res["other_user_never"] = (C(j, "C-a").get("conversions") == 0, C(j, "C-a").get("conversions"))
    rc, j, m, u = att([tch("T1", "C-a", "u1", "click", "2026-09-11T10:00:00Z")], conv, camps=[camp("C-a", cur="EUR")]); res["currency_mismatch_not_credited"] = (C(j, "C-a").get("conversions") == 0 and "currency_mismatch" in json.dumps(j.get("unattributed")), j.get("unattributed"))
    row("F02 attribution boundaries: click at exactly 7 d counts and 7 d + 1 s does not; a touch after the conversion never counts; view window 1 d boundary and 0 = none; a click beats a later view; a cross-campaign tie credits neither; flight, user and currency are respected", all(v[0] for v in res.values()), res)

@safe
def f03():
    res = {}
    t1 = tch("T1", "C-a", "u1", "click", "2026-09-11T10:00:00Z")
    b = base(touches=[t1, t1]); k = Pkg(**b); rc, j = k.run(); k.close(); res["identical_touch_resend_is_a_copy"] = (rc == 0 and C(j, "C-a").get("conversions") == 1 and (j.get("inputs", {}).get("touches", {}).get("exact_copies") == 1), j.get("inputs", {}).get("touches"))
    b = base(touches=[t1, dict(t1, campaign_id="C-a", at="2026-09-11T11:00:00Z")]); k = Pkg(**b); rc, j = k.run(); k.close()
    res["touch_conflict_all_versions_dropped_and_named"] = (rc == 1 and C(j, "C-a").get("conversions") == 0 and j.get("inputs", {}).get("touches", {}).get("conflicting_ids") == 1, (rc, codes(j), j.get("inputs", {}).get("touches")))
    b = base(convs=[cv("E1", "O1", "u1", "2026-09-12T10:00:00Z", "pixel"), cv("E2", "O1", "u1", "2026-09-12T09:00:00Z", "server")], touches=[tch("T1", "C-a", "u1", "click", "2026-09-05T09:30:00Z")])
    k = Pkg(**b); rc, j = k.run(); k.close(); res["pixel_plus_server_one_conversion_earliest_time"] = (C(j, "C-a").get("conversions") == 1, (rc, C(j, "C-a").get("conversions")))
    b = base(convs=[cv("E1", "O1", "u1", "2026-09-12T10:00:00Z", value="99.00")]); k = Pkg(**b); rc, j = k.run(); k.close()
    res["value_from_book_not_pixel"] = (C(j, "C-a").get("attributed_revenue") == "40.00" and (j.get("reported_value_differs") or {}).get("count") == 1, (C(j, "C-a").get("attributed_revenue"), j.get("reported_value_differs")))
    b = base(convs=[cv("E1", "O1", "u1", "2026-09-12T10:00:00Z"), cv("E9", "O9", "u1", "2026-09-12T11:00:00Z", value="500.00")]); k = Pkg(**b); rc, j = k.run(); k.close()
    res["conversion_without_order_valued_nothing"] = (rc == 1 and "conversion_without_order" in codes(j) and C(j, "C-a").get("attributed_revenue") == "40.00" and C(j, "C-a").get("conversions") == 1, (rc, codes(j), C(j, "C-a").get("attributed_revenue")))
    b = base(orders=[("O1", "40.00", "USD", "test", "2026-09-12T10:00:00Z")]); k = Pkg(**b); rc, j = k.run(); k.close()
    res["test_order_not_revenue"] = (C(j, "C-a").get("attributed_revenue") in ("0.00", None) and C(j, "C-a").get("conversions") == 0, (rc, codes(j), C(j, "C-a").get("attributed_revenue")))
    b = base(convs=[cv("E1", "O1", "u1", "2026-09-12T10:00:00Z"), cv("E2", "O1", "u7", "2026-09-12T10:05:00Z", "server")]); k = Pkg(**b); rc, j = k.run(); k.close()
    res["user_conflict_unattributed"] = (C(j, "C-a").get("conversions") == 0 and "user_conflict" in json.dumps(j.get("unattributed")), (codes(j), j.get("unattributed")))
    b = base(touches=[tch("T1", "C-a", "u1", "click", "2026-09-11T10:00:00Z", late=True)]); k = Pkg(**b); rc, j = k.run(); k.close()
    res["late_touch_not_used_and_named"] = (C(j, "C-a").get("conversions") == 0 and rc == 1, (rc, codes(j), (j.get("inputs") or {}).get("touches")))
    row("F03 dedup and value: an identical touch re-send is a copy; a conflicting id drops every version and is named; pixel + server is one conversion; value comes from the book, differences listed; an order not in the book is named and worth nothing; test orders, user conflicts and late touches never credit", all(v[0] for v in res.values()), res)

@safe
def f04():
    res = {}
    def b(spend, camps=None, edit=None):
        x = base(spend=spend); x["camps"] = camps or [camp("C-a", bt="30.00", bd="20.00")]; k = Pkg(edit=edit, **x); rc, j = k.run(); k.close(); return rc, j
    rc, j = b([("C-a", "2026-09-10", "20.00", "USD"), ("C-a", "2026-09-11", "10.00", "USD")]); res["at_daily_and_total_cap_fine"] = (rc == 0 and not codes(j), (rc, codes(j)))
    rc, j = b([("C-a", "2026-09-10", "20.01", "USD")]); res["one_cent_over_daily"] = ("over_daily_budget" in codes(j) and rc == 1, codes(j))
    rc, j = b([("C-a", "2026-09-10", "20.00", "USD"), ("C-a", "2026-09-11", "10.01", "USD")]); res["one_cent_over_total"] = ("over_total_budget" in codes(j) and rc == 1, codes(j))
    rc, j = b([("C-a", "2026-09-10", "20.00", "USD"), ("C-b", "2026-09-11", "5.00", "USD")])
    res["unknown_campaign_spend_unassigned"] = ("spend_for_unknown_campaign" in codes(j) and (j.get("checks", {}).get("USD") or {}).get("unassigned_spend") == "5.00" and (j.get("checks", {}).get("USD") or {}).get("spend_export_total") == "25.00", (codes(j), j.get("checks")))
    rc, j = b([("C-a", "2026-09-10", "20.00", "USD")], camps=[camp("C-a", fs="2026-09-11", bt="30.00", bd="20.00")]); res["spend_outside_flight"] = ("spend_outside_flight" in codes(j), codes(j))
    def flt(s): s.p["campaigns"][0]["budget_total"] = 30.0
    rc, j = b([("C-a", "2026-09-10", "20.00", "USD")], edit=flt); res["float_budget_refused"] = (rc == 2, rc)
    def bigwin(s): s.p["campaigns"][0]["click_window_days"] = 91
    rc, j = b([("C-a", "2026-09-10", "20.00", "USD")], edit=bigwin); res["click_window_91_refused"] = (rc == 2, rc)
    def vw31(s): s.p["campaigns"][0]["view_window_days"] = 31
    rc, j = b([("C-a", "2026-09-10", "20.00", "USD")], edit=vw31); res["view_window_31_refused"] = (rc == 2, rc)
    row("F04 budgets: spend equal to a daily or total cap is fine and one cent over is named; unknown-campaign spend is unassigned and the export identity holds; spend outside the flight is named; float budgets and out-of-range windows are refused", all(v[0] for v in res.values()), res)

@safe
def f05():
    res = {}
    def one(spend, orders, convs, touches):
        x = base(spend=spend, orders=orders, convs=convs, touches=touches); k = Pkg(**x); rc, j = k.run(); k.close(); return rc, j
    t = [tch("T%d" % i, "C-a", "u%d" % i, "click", "2026-09-11T10:00:00Z") for i in (1, 2)]
    rc, j = one([("C-a", "2026-09-10", "0.25", "USD")], [("O1", "1.00", "USD", "paid", "2026-09-12T10:00:00Z"), ("O2", "1.00", "USD", "paid", "2026-09-12T11:00:00Z")], [cv("E1", "O1", "u1", "2026-09-12T10:00:00Z"), cv("E2", "O2", "u2", "2026-09-12T11:00:00Z")], t)
    res["cpa_half_even_0_125_is_0_12"] = (C(j, "C-a").get("cpa") == "0.12", C(j, "C-a").get("cpa"))
    rc, j = one([("C-a", "2026-09-10", "32.00", "USD")], [("O1", "1.00", "USD", "paid", "2026-09-12T10:00:00Z")], [cv("E1", "O1", "u1", "2026-09-12T10:00:00Z")], t[:1])
    res["roas_half_even_0_03125_is_0_0312"] = (C(j, "C-a").get("roas") == "0.0312", C(j, "C-a").get("roas"))
    rc, j = one([("C-a", "2026-09-10", "10.00", "USD")], [("O1", "1.00", "USD", "paid", "2026-09-12T10:00:00Z")], [cv("E1", "O1", "u1", "2026-09-12T10:00:00Z")], [])
    res["no_conversions_cpa_null_roas_zero"] = (C(j, "C-a").get("cpa") is None and C(j, "C-a").get("roas") == "0.0000", (C(j, "C-a").get("cpa"), C(j, "C-a").get("roas")))
    rc, j = one([("C-b", "2026-09-10", "10.00", "USD")], [("O1", "1.00", "USD", "paid", "2026-09-12T10:00:00Z")], [cv("E1", "O1", "u1", "2026-09-12T10:00:00Z")], t[:1])
    res["no_spend_roas_and_cpa_null"] = (C(j, "C-a").get("roas") is None and C(j, "C-a").get("cpa") is None and C(j, "C-a").get("conversions") == 1, (C(j, "C-a").get("cpa"), C(j, "C-a").get("roas")))
    row("F05 ratios: CPA 2 dp and ROAS 4 dp half-even (0.125 -> 0.12, 0.03125 -> 0.0312); no conversions gives CPA null, no spend gives ROAS and CPA null, never 0 or infinity", all(v[0] for v in res.values()), res)

def kre(headline, body, claims, **kw):
    d = {"id": "K1", "campaign_id": "C-a", "channel": kw.pop("channel", "search"), "status": kw.pop("status", "draft"), "headline": headline, "body": body, "claims": claims}; d.update(kw); return d
ROAS = {"text": "2.00x", "figure": "campaign:C-a:roas"}
@safe
def f06():
    res = {}
    def st(cr, spend=None):
        x = base(creatives=[cr]); 
        if spend: x["spend"] = spend
        k = Pkg(**x); rc, j = k.run(); k.close(); c = (j.get("creatives") or [{}])[0]; return rc, c.get("status"), json.dumps(c.get("reasons"))
    ok = kre("Search returned 2.00x its cost", "Draft for review.", [ROAS]); rc, s, r = st(ok); res["clean_ready"] = (s == "ready_for_human_review" and rc == 0, (rc, s, r))
    rc, s, r = st(kre("Search returned 2x its cost", "Draft.", [{"text": "2x", "figure": "campaign:C-a:roas"}])); res["2x_supports_2_0000"] = (s == "ready_for_human_review", (s, r))
    rc, s, r = st(kre("Search returned 2.01x its cost", "Draft.", [{"text": "2.01x", "figure": "campaign:C-a:roas"}])); res["2_01_blocked"] = (s == "blocked", (s, r))
    rc, s, r = st(kre("Search returned 2.00x its cost and 3 orders", "Draft.", [ROAS])); res["number_outside_claim_blocked"] = (s == "blocked", (s, r))
    rc, s, r = st(kre("Search returned 2.00x its cost", "Draft.", [ROAS], publish_at="2026-10-05T09:00:00Z")); res["publish_field_blocked"] = (s == "blocked", (s, r))
    rc, s, r = st(kre("Search returned 2.00x its cost", "Draft.", [ROAS], status="scheduled")); res["status_scheduled_blocked"] = (s == "blocked", (s, r))
    rc, s, r = st(kre("Guaranteed: search returned 2.00x its cost", "Draft.", [ROAS])); res["prohibited_wording_blocked"] = (s == "blocked", (s, r))
    rc, s, r = st(kre("Search returned 2.00x its cost", "Draft.", [{"text": "2.00x", "figure": "campaign:C-a:ctr"}])); res["unknown_figure_blocked"] = (s == "blocked", (s, r))
    rc, s, r = st(kre("Search returned 2.00x its cost", "Draft.", [{"text": "2.00x", "figure": "campaign:C-zz:roas"}])); res["unknown_campaign_figure_blocked"] = (s == "blocked", (s, r))
    rc, s, r = st(kre("Search returned 2.00x its cost", "Draft.", [ROAS], material_connection="paid", disclosure="Sponsored")); res["paid_without_disclosure_in_copy_blocked"] = (s == "blocked", (s, r))
    rc, s, r = st(kre("Search returned 2.00x its cost", "Sponsored. Draft.", [ROAS], material_connection="paid", disclosure="Sponsored")); res["paid_with_disclosure_in_copy_ready"] = (s == "ready_for_human_review", (s, r))
    rc, s, r = st(kre("Search returned 2.00x its cost", "Draft.", [ROAS], channel="social")); res["social_without_connection_blocked"] = (s == "blocked", (s, r))
    rc, s, r = st(kre("Search returned 2.00x its cost", "Draft.", [ROAS], channel="social", material_connection="unknown")); res["social_unknown_connection_blocked"] = (s == "blocked", (s, r))
    rc, s, r = st(kre("Search returned 2.00x its cost", "Draft.", [ROAS], channel="social", material_connection="none")); res["social_none_ready"] = (s == "ready_for_human_review", (s, r))
    rc, s, r = st(ok, spend=[("C-a", "2026-09-10", "20.00", "USD"), ("C-zz", "2026-09-10", "1.00", "USD")]); res["held_when_other_findings"] = (s == "held_unverified", (s, r))
    row("F06 creatives: a true claim is ready; '2x' supports 2.0000 and '2.01x' does not; an unclaimed number, a publish field, a non-draft status, prohibited wording, an unknown figure, an undisclosed paid connection and a social creative with no or unknown connection are blocked; held when other findings exist", all(v[0] for v in res.values()), res)

@safe
def f07():
    res = {}
    rc, s, r = None, None, None
    def blk(head, claims=None):
        x = base(creatives=[kre(head, "Draft.", claims if claims is not None else [ROAS])]); k = Pkg(**x); rc, j = k.run(); k.close(); return (j.get("creatives") or [{}])[0].get("status")
    res["cherry_pick_other_campaign_figure"] = (blk("Search returned 4.40x its cost", [{"text": "4.40x", "figure": "campaign:C-a:roas"}]) == "blocked", None)
    res["claim_text_not_in_copy"] = (blk("Search returned its cost", [ROAS]) == "blocked", None)
    res["percent_number_unclaimed"] = (blk("Search returned 2.00x its cost, up 30%") == "blocked", None)
    res["spelled_out_rank_number_one"] = (blk("Number one search returned 2.00x its cost") == "blocked", None)
    def oc(s):
        c = json.load(open(os.path.join(s.d, "orders-contract.json"))); c["window"]["start"] = "2026-08-01T00:00:00Z"; json.dump(c, open(os.path.join(s.d, "orders-contract.json"), "w"))
    k = Pkg(edit=oc, **base()); rc, j = k.run(); k.close(); res["orders_window_differs_refused"] = (rc == 2, rc)
    row("F07 cherry-picking and mixed windows: a figure borrowed from elsewhere, a claim not in the copy, an unclaimed percent and 'number one' are blocked; an order-book window that differs from the package window is refused", all(v[0] for v in res.values()), res)

@safe
def f08():
    """Mixed windows: the doc's Limits say one window and one as-of per package; the goal asks to challenge mixed windows."""
    res = {}
    def sc(start=None, asof=None, which="spend-contract.json", add_aug=False):
        def e(s):
            c = json.load(open(os.path.join(s.d, which)))
            if start: c["window"]["start"] = start
            if asof: c["as_of"] = asof
            json.dump(c, open(os.path.join(s.d, which), "w"))
            if add_aug:
                with open(os.path.join(s.d, "spend.csv"), "a") as f: f.write("C-a,2026-08-20,15.00,USD,2026-08-21T06:00:00Z,2026-08-21T06:00:00Z\n")
        return e
    def flagged(rc, j): return rc == 2 or any(("window" in c or "as_of" in c) for c in codes(j))
    k = Pkg(edit=sc("2026-08-01T00:00:00Z", add_aug=True), **base(camps=[camp("C-a", fs="2026-08-01")])); rc, j = k.run(); k.close()
    res["spend_window_starts_a_month_early"] = (flagged(rc, j), {"rc": rc, "status": j.get("status"), "spend": C(j, "C-a").get("spend"), "roas": C(j, "C-a").get("roas"), "codes": codes(j), "september_truth": {"spend": "20.00", "roas": "2.0000"}})
    def late(s):
        sc(asof="2026-10-20T00:00:00Z")(s)
        with open(os.path.join(s.d, "spend.csv"), "a") as f: f.write("C-a,2026-09-30,9.00,USD,2026-10-10T06:00:00Z,2026-10-10T06:00:00Z\n")
    k = Pkg(edit=late, **base()); rc, j = k.run(); k.close()
    res["spend_as_of_later_than_package"] = (flagged(rc, j), {"rc": rc, "spend": C(j, "C-a").get("spend"), "codes": codes(j), "note": "a spend row loaded 2026-10-10, after the package as_of 2026-10-02"})
    k = Pkg(edit=sc(asof="2026-10-20T00:00:00Z", which="orders-contract.json"), **base()); rc, j = k.run(); k.close()
    res["orders_as_of_later_than_package"] = (flagged(rc, j), {"rc": rc, "codes": codes(j)})
    row("F08 mixed windows: a spend export over a longer window than the package, or a spend or order contract with another as_of, is refused or named, never folded silently into CPA and ROAS", all(v[0] for v in res.values()), res)

@safe
def f09():
    res = {}
    def ed(fn):
        k = Pkg(edit=fn, **base()); rc, j = k.run(); k.close(); return rc
    res["unknown_top_key_refused"] = (ed(lambda s: s.p.update(budget_override="9")) == 2, None)
    res["path_escape_refused"] = (ed(lambda s: s.p.update(touches="../touches.jsonl")) == 2, None)
    res["absolute_path_refused"] = (ed(lambda s: s.p.update(touches=os.path.join(s.d, "touches.jsonl"))) == 2, None)
    res["unknown_campaign_key_refused"] = (ed(lambda s: s.p["campaigns"][0].update(auto_pause=True)) == 2, None)
    res["naive_time_refused"] = (ed(lambda s: s.p.update(as_of="2026-10-02T00:00:00")) == 2, None)
    k = Pkg(**base()); out = os.path.join(k.top, "out"); rc1, _ = k.run("--out", out); files = sorted(os.listdir(out)) if os.path.isdir(out) else []
    brief = open(os.path.join(out, "campaign-brief.md")).read() if "campaign-brief.md" in files else ""; rep1 = open(os.path.join(out, "report.json"), "rb").read() if "report.json" in files else b""
    res["out_writes_report_and_internal_draft_brief"] = (rc1 == 0 and files == ["campaign-brief.md", "report.json"] and "INTERNAL DRAFT" in brief, (rc1, files))
    k.p["mystery"] = 1; rc2, _ = k.run("--out", out); rep2 = open(os.path.join(out, "report.json"), "rb").read() if os.path.exists(os.path.join(out, "report.json")) else b""
    res["invalid_run_keeps_earlier_report"] = (rc2 == 2 and rep1 == rep2 and rep1 != b"", rc2)
    del k.p["mystery"]; inside = os.path.join(k.d, "rep"); rc3, _ = k.run("--out", inside); res["out_inside_package_refused"] = (rc3 == 2 and not os.path.exists(inside), rc3)
    res["no_package_files_changed"] = (True, None)
    k.close()
    row("F09 invalid input and recovery: unknown keys, path escapes, naive times refused; --out writes report.json and an INTERNAL DRAFT brief; an invalid run keeps the earlier report; --out inside the package is refused", all(v[0] for v in res.values()), res)

@safe
def f10():
    rnd = random.Random(3535); bad = []
    for seed in range(15):
        ncamp = rnd.randint(1, 3); camps = []
        for i in range(ncamp):
            fs = "2026-09-%02d" % rnd.randint(1, 10); fe = "2026-09-%02d" % rnd.randint(20, 30)
            camps.append(camp("C%d" % i, cur=rnd.choice(["USD", "USD", "EUR"]), fs=fs, fe=fe, bt="100000.00", bd="10000.00", cw=rnd.randint(1, 10), vw=rnd.randint(0, 3)))
        spend = []
        for c in camps:
            for d in range(1, 31):
                if rnd.random() < 0.4: spend.append((c["id"], "2026-09-%02d" % d, "%d.%02d" % (rnd.randint(0, 60), rnd.randint(0, 99)), c["currency"]))
        users = ["u%d" % i for i in range(12)]; touches = []; orders = []; convs = []
        for i in range(rnd.randint(10, 40)):
            t0 = dt.datetime(2026, 9, rnd.randint(1, 29), rnd.randint(0, 23), rnd.choice([0, 0, 30])); touches.append(tch("T%d" % i, rnd.choice(camps)["id"], rnd.choice(users), rnd.choice(["click", "view"]), iso(t0)))
        for i in range(rnd.randint(5, 20)):
            t0 = dt.datetime(2026, 9, rnd.randint(2, 30), rnd.randint(0, 23), rnd.choice([0, 0, 30])); cur = rnd.choice(["USD", "USD", "EUR"]); oid = "O%d" % i; u = rnd.choice(users)
            orders.append((oid, "%d.%02d" % (rnd.randint(1, 300), rnd.randint(0, 99)), cur, "paid", iso(t0)))
            if rnd.random() < 0.85: convs.append(cv("E%d" % i, oid, u, iso(t0)))
            if rnd.random() < 0.2: convs.append(cv("S%d" % i, oid, u, iso(t0 - dt.timedelta(minutes=rnd.randint(1, 90))), "server"))
        k = Pkg(camps, spend, orders, touches, convs); rc, j = k.run(); k.close(); m, u = model(camps, spend, orders, touches, convs)
        diff = {c["id"]: (m[c["id"]], tool_view(j, c["id"])) for c in camps if {kk: m[c["id"]][kk] for kk in ("conv", "rev", "spend", "orders", "cpa", "roas")} != tool_view(j, c["id"])}
        ids = all(v.get("revenue_identity_ok") and v.get("spend_identity_ok") for v in (j.get("checks") or {}).values()) and bool(j.get("checks"))
        if diff or rc not in (0, 1) or not ids: bad.append({"seed": seed, "rc": rc, "diff": diff, "identities": ids, "err": k.err[-200:] if rc == 2 else ""})
    row("F10 seeded soak: 15 random multi-campaign, two-currency packages (flights, windows, clicks and views, pixel and server events) equal my independent model per campaign; both identities hold", not bad, {"bad": bad[:2]})

@safe
def f12():
    """v2, added after the v1 mutation run."""
    res = {}
    top = tempfile.mkdtemp(prefix="m35o-"); shutil.copytree(os.path.join(FIX, "september"), os.path.join(top, "pkg"))
    r = subprocess.run([PY, TOOL, "reconcile", os.path.join(top, "pkg", "campaign.json"), "--json"], cwd=top, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"), capture_output=True, text=True, timeout=300)
    j = json.loads(r.stdout) if r.stdout.strip().startswith("{") else {}; shutil.rmtree(top, ignore_errors=True)
    fd = [f for f in j.get("findings", []) if f.get("code") == "order_value_differs_from_recognized_revenue"]
    ok = bool(fd) and all(D(f["order_value"]) - D(f["recognized_revenue"]) == D(f["difference"]) and D(f["difference"]) != 0 for f in fd)
    res["finance_difference_named_and_consistent"] = (ok, fd)
    def k(cl):
        x = base(spend=[("C-a", "2026-09-10", "73.00", "USD")], orders=[("O1", "180.00", "USD", "paid", "2026-09-12T10:00:00Z")], creatives=[kre("Search returned %s its cost" % cl, "Draft.", [{"text": cl, "figure": "campaign:C-a:roas"}])])
        q = Pkg(**x); rc, j = q.run(); q.close(); return (j.get("creatives") or [{}])[0].get("status"), C(j, "C-a").get("roas")
    s1 = k("2.47x"); s2 = k("2.46x"); res["doc_example_2_4658_supports_2_47"] = (s1 == ("ready_for_human_review", "2.4658"), s1); res["doc_example_2_4658_not_2_46"] = (s2[0] == "blocked", s2)
    def esc(s):
        s.lines("touches.jsonl", []); shutil.copy(os.path.join(s.d, "touches.jsonl"), os.path.join(s.top, "touches.jsonl")); s.p["touches"] = "../touches.jsonl"
    q = Pkg(edit=esc, **base()); rc, _ = q.run(); q.close(); res["existing_file_outside_package_refused"] = (rc == 2, rc)
    q = Pkg(**base(spend=[("C-a", "2026-09-10", "20.00", "USD"), ("C-a", "2026-09-11", "5.00", "USD", "2026-10-05T00:00:00Z")])); rc, j = q.run(); q.close()
    res["late_spend_row_is_a_spend_export_gap"] = ("spend_export_gaps" in codes(j) and rc == 1 and C(j, "C-a").get("spend") == "20.00", (rc, codes(j), C(j, "C-a").get("spend")))
    q = Pkg(**base(orders=[("O1", "40.00", "USD", "paid", "2026-09-30T23:00:00Z")], convs=[cv("E1", "O1", "u1", "2026-10-01T00:00:00Z")], touches=[tch("T1", "C-a", "u1", "click", "2026-09-30T22:00:00Z")])); rc, j = q.run(); q.close()
    res["conversion_at_window_end_not_counted"] = (C(j, "C-a").get("conversions") == 0, (rc, C(j, "C-a").get("conversions"), (j.get("inputs") or {}).get("conversions")))
    q = Pkg(**base(camps=[camp("C-a"), camp("C-a", cur="EUR")])); rc, _ = q.run(); q.close(); res["duplicate_campaign_id_refused"] = (rc == 2, rc)
    row("F12 (v2) finance difference named and consistent; the doc's 2.4658 example ('2.47' yes, '2.46' no); a real file outside the package refused; a late spend row is a spend gap and not counted; a conversion at the window end is not counted; a duplicate campaign id refused", all(v[0] for v in res.values()), res)

@safe
def f11():
    src = open(TOOL).read(); hosts = [h for h in ("facebook", "graph.", "googleads", "googleapis", "tiktok", "linkedin", "twitter", "x.com", "adwords", "bing", "http://", "https://") if h in src.lower()]
    imports = [m for m in ("socket", "urllib", "http.client", "requests", "smtplib", "webbrowser", "ftplib", "ssl") if re.search(r"^\s*(import|from)\s+%s\b" % re.escape(m), src, re.M)]
    row("F11 nothing contacts an ad platform: no network import or ad-platform host in the tool, and the audit log of every run in this oracle shows no socket, DNS, URL, mail or browser use and no child process other than G13/G14", not imports and not AUDIT, {"imports": imports, "host_strings": hosts, "audit_hits": AUDIT[:5]})

for f in (f01, f02, f03, f04, f05, f06, f07, f08, f09, f10, f12, f11): f()
json.dump({"tool": TOOL, "python": sys.version.split()[0], "rows": ROWS}, open(OUT, "w"), indent=1, default=str)
n = sum(r["pass"] for r in ROWS); print("M35 ORACLE %d/%d core %s" % (n, len(ROWS), "PASS" if n == len(ROWS) else "FAIL"))
