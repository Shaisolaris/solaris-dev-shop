#!/usr/bin/env python3
"""G11 oracle: incident timeline, SLO / error budget and rollback decision.

Generates its own bundles from a seed (service names, windows and counts the fixtures do not
use), computes the expected values independently with decimal arithmetic, and runs
  CMD report BUNDLE --json [--out REPORT]
for every check. Exit 0 alone proves nothing: each check reads the JSON values.

Usage: incident_oracle.py [--seed N] [--quick] -- CMD...
"""
from __future__ import annotations

import argparse
import copy
import decimal
import hashlib
import json
import os
import random
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
G03 = ROOT / "employees" / "infrastructure" / "database-administrator" / "sqlite_recovery.py"
G10FIX = ROOT / "examples" / "capabilities" / "G10" / "fixtures"
CMD = []
RESULTS = []


def D(num, den, places=6):
    """Expected decimal string, computed with Decimal (independent of the tool's Fraction code)."""
    ctx = decimal.Context(prec=60, rounding=decimal.ROUND_HALF_EVEN)
    q = ctx.divide(decimal.Decimal(num), decimal.Decimal(den))
    return str(q.quantize(decimal.Decimal(1).scaleb(-places), context=ctx))


def ts(base_epoch, minutes=0, seconds=0):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(base_epoch + minutes * 60 + seconds))


def world(rng, n=120, objective="0.99", burn=5, deploy=(40, 17), impact=(43, 70), rate=0.08,
          missing=(), conflicting=(), migrates=False, events=True, late_every=3):
    """A bundle plus the truth. Counts are drawn per minute; impact minutes burn > the budget."""
    obj = decimal.Decimal(objective)
    base = 1792396800 + rng.randrange(0, 60) * 86400  # stays inside the G10 fixture certificates (valid to 2027-01-01)
    base = base + rng.randrange(0, 1440) * 60
    svc = "svc-%s-%d" % (rng.choice(["ledger", "cart", "search", "notify", "auth"]), rng.randrange(100, 999))
    tel, per = [], {}
    for i in range(n):
        total = rng.randrange(600, 1400)
        if impact and impact[0] <= i < impact[1]:
            bad = int(total * rate) + rng.randrange(0, 5)
        else:
            cap = int(decimal.Decimal(total) * (1 - obj) / 2)
            bad = rng.randrange(0, cap + 1)
        per[i] = (total - bad, total)
        if i in missing:
            continue
        rec = {"minute": ts(base, i), "good": total - bad, "total": total, "source": "lb-0"}
        if i % 7 == 0:
            rec["received_at"] = ts(base, i + 1, 400)  # late telemetry, still counted
        tel.append(rec)
        if i in conflicting:
            tel.append({"minute": ts(base, i), "good": total - bad - 1, "total": total, "source": "lb-0"})
    meas = [i for i in range(n) if i not in missing and i not in conflicting]
    good = sum(per[i][0] for i in meas)
    total = sum(per[i][1] for i in meas)
    evs, resp = [], {}
    if events and impact:
        offs = {"detected": rng.randrange(60, 400), "declared": None, "mitigated": rng.randrange(900, 1500),
                "resolved": rng.randrange(1600, 2400)}
        offs["declared"] = offs["detected"] + rng.randrange(30, 200)
        for k, o in offs.items():
            e = {"id": "%s-%s" % (svc, k), "at": ts(base, impact[0], o), "kind": k, "actor": "oncall-a", "detail": "%s by on-call" % k}
            if len(evs) % late_every == 0:
                e["received_at"] = ts(base, impact[0], o + 900)
            evs.append(e)
        resp = {"time_to_detect_s": offs["detected"], "time_to_mitigate_s": offs["mitigated"], "time_to_resolve_s": offs["resolved"]}
    b = {"schema": "solaris.incident-bundle/1", "service": svc,
         "window": {"start": ts(base), "end": ts(base, n)},
         "slo": {"objective": float(objective), "rollback_burn_rate": burn, "min_coverage": 0.9},
         "telemetry": tel, "events": evs}
    if deploy is not None:
        b["change"] = {"revision": "rel-%d" % rng.randrange(1000, 9999), "previous": "rel-%d" % rng.randrange(100, 999),
                       "deployed_at": ts(base, deploy[0], deploy[1]), "migrates_data": migrates}
    bad = total - good
    allowed = (1 - obj) * total
    truth = {"good": good, "total": total, "bad": bad, "availability": D(good, total),
             "error_budget_requests": str(allowed.quantize(decimal.Decimal("0.000001"))),
             "budget_remaining": D(allowed - bad, allowed), "burn_rate": D(decimal.Decimal(bad), decimal.Decimal(total) * (1 - obj)),
             "coverage": D(len(meas), n), "missing": sorted(missing), "conflicting": sorted(conflicting),
             "impact": (ts(base, impact[0]), ts(base, impact[1] if impact[1] <= n else n)) if impact else (None, None),
             "response": resp, "base": base, "per": per, "obj": obj, "n": n}
    return b, truth


def run(bundle_path, out=None, env=None):
    args = CMD + ["report", str(bundle_path), "--json"] + (["--out", str(out)] if out else [])
    p = subprocess.run(args, capture_output=True, text=True, timeout=300, env=env)
    try:
        rep = json.loads(p.stdout) if p.returncode == 0 else None
    except ValueError:
        rep = None
    return p.returncode, rep, p.stdout


def put(d, name, b):
    p = Path(d) / name
    p.write_text(json.dumps(b, indent=1))
    return p


def check(name, fn):
    try:
        ok, msg = fn()
    except Exception as exc:  # a crashing tool fails the check, never the oracle
        ok, msg = False, "%s: %s" % (type(exc).__name__, str(exc)[:200])
    RESULTS.append((name, ok, msg))
    print("%s %s: %s" % ("PASS" if ok else "FAIL", name, msg))


def g(rep, *path):
    cur = rep
    for k in path:
        if not isinstance(cur, dict) or k not in cur:
            return None
        cur = cur[k]
    return cur


def slo_ok(rep, t):
    s = g(rep, "slo") or {}
    want = {k: t[k] for k in ("good", "total", "bad", "availability", "error_budget_requests", "budget_remaining", "burn_rate", "coverage")}
    got = {k: s.get(k) for k in want}
    return got == want, got, want


def dec_of(rep):
    return g(rep, "decision", "decision")


def names_scope(rep, b):
    r = g(rep, "decision", "reason") or ""
    w = "%s/%s" % (b["window"]["start"], b["window"]["end"])
    return b["service"] in r and w in r and b["change"]["revision"] in r and g(rep, "decision", "window") == w \
        and g(rep, "decision", "service") == b["service"]


def stable_view(rep):
    return json.dumps({k: rep.get(k) for k in ("slo", "timeline", "decision", "impact", "missing_telemetry", "response", "labels")}, sort_keys=True)


def make_snapshot(d, broken=False):
    """Real dataset and a real G03 snapshot (the data a migrating change needs restored)."""
    ds = Path(d) / "data"
    ds.mkdir()
    con = sqlite3.connect(str(ds / "app.db"))
    con.execute("create table orders(id integer primary key, total_cents integer)")
    con.executemany("insert into orders(total_cents) values (?)", [(i * 125,) for i in range(1, 40)])
    con.commit()
    con.close()
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    p = subprocess.run([sys.executable, str(G03), "snapshot", str(ds), "--out", str(Path(d) / "snap")], capture_output=True, text=True, env=env)
    if p.returncode != 0:
        raise RuntimeError("G03 snapshot failed: " + p.stdout + p.stderr)
    sid = json.loads((Path(d) / "snap" / "manifest.json").read_text())["snapshot_id"]
    if broken:
        f = Path(d) / "snap" / "app.db"
        raw = bytearray(f.read_bytes())
        raw[len(raw) // 2] ^= 0xFF
        f.write_bytes(bytes(raw))
    return sid


def tree_digest(d):
    h = hashlib.sha256()
    for root, dirs, files in sorted(os.walk(d)):
        dirs.sort()
        for f in sorted(files):
            p = os.path.join(root, f)
            h.update(p.encode() + b"\0" + open(p, "rb").read())
    return h.hexdigest()


def main():
    global CMD
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=1811)
    ap.add_argument("--quick", action="store_true", help="skip the 30-day scale check")
    ap.add_argument("cmd", nargs=argparse.REMAINDER)
    a = ap.parse_args()
    CMD = a.cmd[1:] if a.cmd[:1] == ["--"] else a.cmd
    if not CMD:
        ap.error("give the tool command after --")
    rng = random.Random(a.seed)
    tmp = tempfile.mkdtemp(prefix="g11-oracle-")

    def o1():
        b, t = world(rng, impact=None, events=False)
        rc, rep, _ = run(put(tmp, "o1.json", b))
        ok, got, want = slo_ok(rep, t)
        ok = ok and rc == 0 and g(rep, "slo", "status") == "met" and dec_of(rep) == "do_not_rollback" and names_scope(rep, b) \
            and g(rep, "impact", "start") is None and g(rep, "missing_telemetry", "minutes") == 0 and g(rep, "labels") == []
        return ok, "clean control: exact SLO, met, no impact, no rollback" if ok else "got %s want %s decision %s" % (got, want, dec_of(rep))
    check("o1 clean control", o1)

    reg_b, reg_t = world(rng)

    def o2():
        rc, rep, _ = run(put(tmp, "o2.json", reg_b))
        ok, got, want = slo_ok(rep, reg_t)
        imp = (g(rep, "impact", "start"), g(rep, "impact", "end"))
        resp = g(rep, "response")
        ok = ok and rc == 0 and g(rep, "slo", "status") == "breached" and imp == reg_t["impact"] and resp == reg_t["response"] \
            and dec_of(rep) == "rollback" and names_scope(rep, reg_b) and "code only" in (g(rep, "decision", "reason") or "")
        return ok, "deploy regression: exact SLO, impact %s..%s, response %s, rollback naming service/window/revision" % (imp + (resp,)) if ok \
            else "got %s want %s impact %s/%s resp %s/%s decision %s" % (got, want, imp, reg_t["impact"], resp, reg_t["response"], dec_of(rep))
    check("o2 regression after a change", o2)

    def o3():
        rc1, rep1, out1 = run(put(tmp, "o3a.json", reg_b))
        b2 = copy.deepcopy(reg_b)
        r2 = random.Random(a.seed + 3)
        b2["telemetry"] = b2["telemetry"] + copy.deepcopy(b2["telemetry"])
        b2["events"] = b2["events"] + [dict(e, received_at=e.get("received_at", e["at"])) for e in copy.deepcopy(b2["events"])]
        r2.shuffle(b2["telemetry"])
        r2.shuffle(b2["events"])
        rc2, rep2, _ = run(put(tmp, "o3b.json", b2))
        rc3, _, out3 = run(put(tmp, "o3a.json", reg_b))
        ok = rc1 == rc2 == rc3 == 0 and stable_view(rep1) == stable_view(rep2) and out1 == out3 \
            and g(rep2, "import", "telemetry_duplicates") == len(reg_b["telemetry"]) and g(rep2, "import", "event_duplicates") == len(reg_b["events"])
        return ok, "re-import doubled and shuffled: same SLO, timeline and decision; duplicates counted; rerun byte-identical" if ok else \
            "views differ or duplicates miscounted (%s)" % (g(rep2, "import"),)
    check("o3 repeated import stable", o3)

    def o4():
        miss = set(range(10, 13)) | {90}
        b, t = world(rng, missing=miss)
        rc, rep, _ = run(put(tmp, "o4.json", b))
        ok, got, want = slo_ok(rep, t)
        rng_ = g(rep, "missing_telemetry", "ranges") or []
        base = t["base"]
        want_r = [{"start": ts(base, 10), "end": ts(base, 13), "minutes": 3}, {"start": ts(base, 90), "end": ts(base, 91), "minutes": 1}]
        kinds = [x.get("kind") for x in g(rep, "timeline") or []]
        # gap after the change: 30 of the 80 post-change minutes missing -> no decision
        b2, _ = world(rng, missing=set(range(60, 90)))
        rc2, rep2, _ = run(put(tmp, "o4b.json", b2))
        # whole window under-covered -> status insufficient, not met or breached
        b3, _ = world(rng, missing=set(range(0, 20)), impact=None, events=False, deploy=None)
        rc3, rep3, _ = run(put(tmp, "o4c.json", b3))
        ok = ok and rc == rc2 == rc3 == 0 and rng_ == want_r and kinds.count("telemetry_missing") == 2 and dec_of(rep) == "rollback" \
            and dec_of(rep2) == "insufficient_evidence" and names_scope(rep2, b2) and g(rep3, "slo", "status") == "insufficient_telemetry" \
            and g(rep3, "decision") is None
        return ok, "gaps labelled with exact ranges and left out of the SLO; post-change gap gives no decision; low coverage is insufficient" if ok \
            else "slo %s/%s ranges %s decisions %s %s status %s" % (got, want, rng_, dec_of(rep), dec_of(rep2), g(rep3, "slo", "status"))
    check("o4 missing telemetry labelled", o4)

    def o5():
        b, t = world(rng, conflicting={5, 6})
        rc, rep, _ = run(put(tmp, "o5.json", b))
        ok, got, want = slo_ok(rep, t)
        cr = g(rep, "missing_telemetry", "conflicting_ranges")
        base = t["base"]
        out = Path(tmp) / "o5-report.json"
        rcg, _, _ = run(put(tmp, "o5-good.json", reg_b), out=out)
        before = out.read_bytes()
        bad = copy.deepcopy(reg_b)
        e = dict(bad["events"][0], detail="a different account of the same event")
        bad["events"].append(e)
        rcb, _, _ = run(put(tmp, "o5-bad.json", bad), out=out)
        ok = ok and rc == 0 and cr == [{"start": ts(base, 5), "end": ts(base, 7), "minutes": 2}] and rcg == 0 and rcb == 2 and out.read_bytes() == before
        return ok, "conflicting minutes labelled and left out; an event id with two contents is refused (exit 2), previous report kept" if ok \
            else "slo %s/%s conflicting %s rc %s/%s" % (got, want, cr, rcg, rcb)
    check("o5 conflicting evidence", o5)

    def o6():
        d = Path(tempfile.mkdtemp(dir=tmp))
        (d / "traces").mkdir()
        dns = json.loads((G10FIX / "02-dns-nxdomain.json").read_text())
        app = json.loads((G10FIX / "09-app-upstream-503.json").read_text())
        b, t = world(rng)
        during = ts(t["base"], 50)
        dns["captured_at"] = app["captured_at"] = during
        (d / "traces" / "edge-dns.json").write_text(json.dumps(dns))
        (d / "traces" / "edge-app.json").write_text(json.dumps(app))
        b1 = dict(b, diagnoses=["traces/edge-dns.json"])
        b2 = dict(b, diagnoses=["traces/edge-app.json"])
        b3 = dict(b, diagnoses=["traces/edge-dns.json"])
        dns_before = dict(dns, captured_at=ts(t["base"], 20))
        (d / "traces" / "old-dns.json").write_text(json.dumps(dns_before))
        b3["diagnoses"] = ["traces/old-dns.json"]
        rc1, r1, _ = run(put(d, "b1.json", b1))
        rc2, r2, _ = run(put(d, "b2.json", b2))
        rc3, r3, _ = run(put(d, "b3.json", b3))
        reason = g(r1, "decision", "reason") or ""
        tl = [x for x in g(r1, "timeline") or [] if x.get("kind") == "diagnosis"]
        ok = rc1 == rc2 == rc3 == 0 and dec_of(r1) == "do_not_rollback" and "dns layer" in reason and names_scope(r1, b1) \
            and dec_of(r2) == "rollback" and dec_of(r3) == "rollback" and len(tl) == 1 and tl[0].get("at") == during \
            and (g(r1, "diagnoses") or [{}])[0].get("layer") == "dns"
        return ok, "G10 dns fault during the impact blocks a code rollback; G10 application fault and a dns trace from before the impact do not" if ok \
            else "decisions %s %s %s reasons %r %r" % (dec_of(r1), dec_of(r2), dec_of(r3), reason, g(r2, "decision", "reason"))
    check("o6 G10 diagnosis in the decision", o6)

    def o7():
        b, _ = world(rng, deploy=(60, 5), impact=(43, 80))
        rc, rep, _ = run(put(tmp, "o7.json", b))
        ok = rc == 0 and dec_of(rep) == "do_not_rollback" and "before" in (g(rep, "decision", "reason") or "") and names_scope(rep, b)
        b2, _ = world(rng, deploy=(60, 5), impact=(65, 80), missing=set(range(55, 65)))
        rc2, rep2, _ = run(put(tmp, "o7b.json", b2))
        ok = ok and rc2 == 0 and dec_of(rep2) == "insufficient_evidence" and g(rep2, "impact", "start_bound") == "at_or_before"
        b3, _ = world(rng, rate=0.015)
        rc3, rep3, _ = run(put(tmp, "o7c.json", b3))
        ok = ok and rc3 == 0 and g(rep3, "impact", "start") is not None and dec_of(rep3) == "do_not_rollback" \
            and "below the rollback threshold" in (g(rep3, "decision", "reason") or "") and names_scope(rep3, b3)
        return ok, "impact before the change: no rollback; impact start hidden by a gap spanning the change: no decision; slow burn after the change below the threshold: no rollback" if ok else \
            "decisions %s %s %s" % (dec_of(rep), dec_of(rep2), dec_of(rep3))
    check("o7 impact before the change", o7)

    def o8():
        outs = []
        for kind in ("none", "broken", "good"):
            d = Path(tempfile.mkdtemp(dir=tmp))
            b, _ = world(rng, migrates=True)
            sid = None
            if kind != "none":
                sid = make_snapshot(d, broken=(kind == "broken"))
                b["change"]["data"] = {"snapshot": "snap", "databases": ["app.db"]}
            rc, rep, _ = run(put(d, "b.json", b))
            outs.append((kind, rc, dec_of(rep), g(rep, "decision", "reason") or "", sid, names_scope(rep, b) if rep else False))
        ok = outs[0][1:3] == (0, "rollback_blocked") and outs[1][1:3] == (0, "rollback_blocked") and outs[2][1:3] == (0, "rollback") \
            and outs[2][4] in outs[2][3] and all(o[5] for o in outs)
        return ok, "migrating change: no snapshot and a damaged snapshot block the rollback; a G03-verified snapshot is named in the rollback" if ok \
            else str([(o[0], o[1], o[2], o[3][:90]) for o in outs])
    check("o8 data rollback needs a verified G03 snapshot", o8)

    def o9():
        rc, rep, _ = run(put(tmp, "o9.json", reg_b))
        late_ids = {e["id"] for e in reg_b["events"] if "received_at" in e}
        tl = {x.get("id"): x for x in g(rep, "timeline") or [] if x.get("source") == "event"}
        late_tel = sum(1 for r in reg_b["telemetry"] if "received_at" in r)
        ok = rc == 0 and late_ids and all(tl.get(i, {}).get("late") is True for i in late_ids) \
            and all(x.get("late") is False for i, x in tl.items() if i not in late_ids) and g(rep, "import", "telemetry_late") == late_tel \
            and slo_ok(rep, reg_t)[0]
        ats = [x.get("at") for x in g(rep, "timeline") or [] if x.get("at")]
        ok = ok and ats == sorted(ats)
        return ok, "late events labelled, late telemetry counted and still scored, timeline in time order" if ok else "late labels wrong"
    check("o9 late and out-of-order records", o9)

    def o10():
        out = Path(tmp) / "o10-report.json"
        out.write_text("previous\n")
        bads = []
        b = copy.deepcopy(reg_b); b["telemetry"][0]["good"] = b["telemetry"][0]["total"] + 1; bads.append(b)
        b = copy.deepcopy(reg_b); b["window"]["end"] = b["window"]["start"]; bads.append(b)
        b = copy.deepcopy(reg_b); b["telemetry"][1]["minute"] = b["telemetry"][1]["minute"].replace("Z", ""); bads.append(b)
        b = copy.deepcopy(reg_b); b["slo"]["objective"] = 1.0; bads.append(b)
        b = copy.deepcopy(reg_b); b["diagnoses"] = ["../outside.json"]; bads.append(b)
        b = copy.deepcopy(reg_b); b["extra_evidence"] = []; bads.append(b)
        rcs = [run(put(tmp, "o10-%d.json" % i, x), out=out)[0] for i, x in enumerate(bads)]
        p = Path(tmp) / "o10-dupkey.json"
        p.write_text('{"service": "svc-shadow",' + json.dumps(reg_b)[1:])  # otherwise valid; two values for one key
        rcs.append(run(p, out=out)[0])
        kept = out.read_text() == "previous\n"
        rc, rep, _ = run(put(tmp, "o10-good.json", reg_b), out=out)
        recovered = rc == 0 and json.loads(out.read_text()).get("slo", {}).get("total") == reg_t["total"]
        ok = rcs == [2] * 7 and kept and recovered
        return ok, "seven invalid bundles exit 2 with the previous report kept; the next valid run writes it" if ok else "rcs %s kept %s recovered %s" % (rcs, kept, recovered)
    check("o10 invalid input and recovery", o10)

    def o11():
        r = random.Random(a.seed + 11)
        b, t = world(r, n=43200, deploy=(40000, 30), impact=(40010, 40100), missing=set(range(1000, 1300)), events=True)
        b["telemetry"] = b["telemetry"] * 2
        r.shuffle(b["telemetry"])
        p = put(tmp, "o11.json", b)
        t0 = time.time()
        rc, rep, out = run(p)
        el = time.time() - t0
        ok, got, want = slo_ok(rep, t)
        procs = [subprocess.Popen(CMD + ["report", str(p), "--json"], stdout=subprocess.PIPE) for _ in range(4)]
        outs = [pr.communicate(timeout=300)[0].decode() for pr in procs]
        ok = ok and rc == 0 and all(o == out for o in outs) and dec_of(rep) == "rollback" and el < 60
        return ok, "30-day window (43200 minutes, %d records, doubled and shuffled): exact SLO in %.1fs; 4 parallel runs identical" % (len(b["telemetry"]), el) \
            if ok else "slo %s/%s rc %s %.1fs" % (got, want, rc, el)
    if not a.quick:  # --quick leaves the check out entirely; it never counts as a pass
        check("o11 operational scale", o11)

    def o12():
        guard = Path(tempfile.mkdtemp(dir=tmp))
        (guard / "sitecustomize.py").write_text(
            "import socket\n"
            "def _deny(*a, **k):\n    raise RuntimeError('network use denied by the G11 oracle')\n"
            "socket.socket = _deny\nsocket.create_connection = _deny\nsocket.getaddrinfo = _deny\n")
        d = Path(tempfile.mkdtemp(dir=tmp))
        (d / "traces").mkdir()
        app = json.loads((G10FIX / "09-app-upstream-503.json").read_text())
        b, _ = world(rng)
        app["captured_at"] = b["window"]["start"]
        (d / "traces" / "t.json").write_text(json.dumps(app))
        b["diagnoses"] = ["traces/t.json"]
        p = put(d, "b.json", b)
        before = tree_digest(d)
        env = dict(os.environ, PYTHONPATH=str(guard), PYTHONDONTWRITEBYTECODE="1")
        rc, rep, _ = run(p, env=env)
        ok = rc == 0 and tree_digest(d) == before and dec_of(rep) == "rollback" and \
            all(k in json.dumps(rep) for k in ("read_only",))
        return ok, "runs under a socket-denying guard and leaves the bundle folder byte-identical" if ok else "rc %s changed %s" % (rc, tree_digest(d) != before)
    check("o12 offline and read-only", o12)

    def o13():
        # telemetry split across two load balancers: each minute's value is the sum over distinct sources
        base = 1792396800 + rng.randrange(0, 60) * 86400
        n = 30

        def bundle(tel):
            return {"schema": "solaris.incident-bundle/1", "service": "svc-split-lb", "events": [],
                    "window": {"start": ts(base, 0), "end": ts(base, n)},
                    "slo": {"objective": 0.99, "rollback_burn_rate": 5, "min_coverage": 0.9}, "telemetry": tel}
        # A: shares differ in the only error minute (lb-a 500 bad of 500); summed it breaches the SLO
        tel = []
        for i in range(n):
            tel.append({"minute": ts(base, i), "good": 0 if i == 17 else 500, "total": 500, "source": "lb-a"})
            tel.append({"minute": ts(base, i), "good": 500, "total": 500, "source": "lb-b"})
        tel.append(dict(tel[0]))  # an exact re-delivery from lb-a counts once
        rng.shuffle(tel)
        rca, ra, _ = run(put(tmp, "o13a.json", bundle(tel)))
        sa = g(ra, "slo") or {}
        oka = rca == 0 and sa.get("total") == 30000 and sa.get("bad") == 500 and sa.get("availability") == D(29500, 30000) \
            and sa.get("status") == "breached" and g(ra, "missing_telemetry", "conflicting_minutes") == 0 \
            and g(ra, "import", "telemetry_duplicates") == 1
        # B: two sources with equal counts are two reports, not one (totals not halved)
        tel = [{"minute": ts(base, i), "good": 490, "total": 500, "source": s_} for i in range(n) for s_ in ("lb-a", "lb-b")]
        rcb, rb, _ = run(put(tmp, "o13b.json", bundle(tel)))
        sb = g(rb, "slo") or {}
        okb = rcb == 0 and sb.get("total") == 30000 and sb.get("good") == 29400 and g(rb, "missing_telemetry", "conflicting_minutes") == 0
        # C: one source reporting two different counts for a minute is a genuine conflict
        tel = [{"minute": ts(base, i), "good": 500, "total": 500, "source": s_} for i in range(n) for s_ in ("lb-a", "lb-b")]
        tel.append({"minute": ts(base, 4), "good": 450, "total": 500, "source": "lb-b"})
        rcc, rc_, _ = run(put(tmp, "o13c.json", bundle(tel)))
        sc = g(rc_, "slo") or {}
        okc = rcc == 0 and g(rc_, "missing_telemetry", "conflicting_minutes") == 1 and sc.get("total") == 29000
        ok = oka and okb and okc
        return ok, "split load balancers summed (the only error minute breaches); equal counts from two sources both count; " \
            "one source with two counts is a conflict" if ok else "A %s %s B %s C %s" % (oka, {k: sa.get(k) for k in ("total", "bad", "status")}, okb, okc)
    check("o13 per-source telemetry summed", o13)

    def o14():
        # silent sources: one of two load balancers stops reporting (M11 r2 O09), a declared source that never
        # reports, source-name spelling, and the rollback decision when a source is silent after a change
        base = 1792396800 + rng.randrange(0, 60) * 86400
        n = 60

        def bundle(tel, **kw):
            b = {"schema": "solaris.incident-bundle/1", "service": "svc-split-lb", "events": [],
                 "window": {"start": ts(base, 0), "end": ts(base, n)},
                 "slo": {"objective": 0.99, "rollback_burn_rate": 5, "min_coverage": 0.4}, "telemetry": tel}
            b.update(kw)
            return b
        full = lambda srcs: [{"minute": ts(base, i), "good": 500, "total": 500, "source": s_} for i in range(n) for s_ in srcs]
        bad = []
        # A: lb-b silent for minutes 10-39: 30 partial minutes left out, per-source gap reported, met blocked
        tel = [r for r in full(("lb-a", "lb-b")) if not (r["source"] == "lb-b" and ts(base, 10) <= r["minute"] < ts(base, 40))]
        rc, r, _ = run(put(tmp, "o14a.json", bundle(tel)))
        ps = {x.get("source"): x for x in g(r, "sources", "per_source") or []}
        if not (rc == 0 and g(r, "slo", "status") == "insufficient_telemetry" and g(r, "slo", "total") == 30000
                and g(r, "missing_telemetry", "partial_minutes") == 30 and (ps.get("lb-b") or {}).get("coverage") == "0.500000"
                and (ps.get("lb-a") or {}).get("coverage") == "1.000000" and g(r, "sources", "basis") == "inferred"
                and any("lb-b" in x and "cannot be reported as met" in x for x in g(r, "labels") or [])):
            bad.append(("A silent half hour", rc, g(r, "slo", "status"), g(r, "missing_telemetry", "partial_minutes")))
        # B: control, both report every minute: met, nothing partial
        rc, r, _ = run(put(tmp, "o14b.json", bundle(full(("lb-a", "lb-b")))))
        if not (rc == 0 and g(r, "slo", "status") == "met" and g(r, "missing_telemetry", "partial_minutes") == 0):
            bad.append(("B control", rc, g(r, "slo", "status")))
        # C: a declared source that never reports makes every minute partial
        rc, r, _ = run(put(tmp, "o14c.json", bundle(full(("lb-a", "lb-b")), telemetry_sources=["lb-a", "lb-b", "lb-c"])))
        ps = {x.get("source"): x for x in g(r, "sources", "per_source") or []}
        if not (rc == 0 and g(r, "slo", "status") == "insufficient_telemetry" and (ps.get("lb-c") or {}).get("coverage") == "0.000000"
                and g(r, "sources", "basis") == "declared"):
            bad.append(("C declared never reports", rc, g(r, "slo", "status")))
        # D: names trimmed and case-folded against the declared list; two spellings of one name are refused;
        # an undeclared source is refused
        tel = [dict(x, source={"lb-a": " LB-A", "lb-b": "lb-B "}[x["source"]]) for x in full(("lb-a", "lb-b"))]
        rc1, r1, _ = run(put(tmp, "o14d1.json", bundle(tel, telemetry_sources=["lb-a", "LB-b"])))
        tel2 = full(("lb-a",)) + [dict(x, source="LB-A ") for x in full(("lb-a",))[:1]]
        rc2, _, _ = run(put(tmp, "o14d2.json", bundle(tel2)))
        rc3, _, _ = run(put(tmp, "o14d3.json", bundle(full(("lb-a", "lb-z")), telemetry_sources=["lb-a"])))
        if not (rc1 == 0 and g(r1, "slo", "status") == "met" and g(r1, "slo", "total") == 60000 and rc2 == 2 and rc3 == 2):
            bad.append(("D names", rc1, g(r1, "slo", "status"), rc2, rc3))
        # E: change in the window, no budget burned, lb-b silent after the change: no do_not_rollback
        tel = [r_ for r_ in full(("lb-a", "lb-b")) if not (r_["source"] == "lb-b" and r_["minute"] >= ts(base, 50))]
        b = bundle(tel, change={"revision": "rel-2", "previous": "rel-1", "deployed_at": ts(base, 30), "migrates_data": False})
        rc, r, _ = run(put(tmp, "o14e.json", b))
        if not (rc == 0 and dec_of(r) == "insufficient_evidence" and "silent" in (g(r, "decision", "reason") or "")):
            bad.append(("E decision", rc, dec_of(r)))
        ok = not bad
        return ok, "a silent load balancer, a declared source that never reports, name spelling and a silent source after a change are labelled, block met or the rollback call, and are refused when ambiguous" if ok else "%s" % bad
    check("o14 expected sources and per-source coverage", o14)

    passed = sum(1 for _, ok, _ in RESULTS if ok)
    print("%s: %d/%d checks passed (seed %d)" % ("ACCEPTED" if passed == len(RESULTS) else "REJECTED", passed, len(RESULTS), a.seed))
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
