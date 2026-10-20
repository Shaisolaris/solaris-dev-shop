#!/usr/bin/env python3
"""M37 oracle (Grok self-validation, not independent review). Written from M37.md, G37.md and privacy-inventory.md
before reading the builder's oracle. It builds synthetic packages (a G13 contract over orders.csv with a customers.csv
dimension, an inventory, requests and clocks), keeps its own model of which raw file lines hold a subject and when
records and requests fall due (days, and months clamped to the month end), and drives the real CLI. Every run goes
through an audit hook; only the documented G13 child process is allowed, and data files must be byte-identical
after every run (nothing is deleted). Usage: PY m37_oracle.py SRC OUT.json [--tool PATH]."""
import copy, datetime as dt, hashlib, json, os, random, re, shutil, subprocess, sys, tempfile
SRC = os.path.abspath(sys.argv[1]); OUT = sys.argv[2]
TOOL = os.path.join(SRC, "employees/legal-compliance/compliance-auditor/privacy_inventory.py")
if "--tool" in sys.argv: TOOL = os.path.abspath(sys.argv[sys.argv.index("--tool") + 1])
FIX = os.path.join(SRC, "examples/capabilities/G37/fixtures"); PY = sys.executable
AUD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audit"); ROWS = []; AUDIT = []; TOUCHED = []

def row(name, ok, det):
    sub = {k: bool(v[0]) for k, v in det.items() if isinstance(v, (tuple, list)) and len(v) == 2 and isinstance(v[0], bool)} if isinstance(det, dict) else {}
    ROWS.append({"row": name, "pass": bool(ok), "sub": sub, "detail": det}); print(("PASS " if ok else "FAIL ") + name + " " + json.dumps(det, default=str)[:450], flush=True)
def safe(fn):
    def g():
        try: fn()
        except Exception as e: row(fn.__name__ + " crash", False, {"crash": repr(e)})
    return g

CUST_H = ["customer_id", "region", "name", "contact", "created_at", "updated_at"]
ORD_H = ["order_id", "customer_id", "amount", "currency", "status", "event_time", "loaded_at", "updated_at"]
def cust(k, created="2026-02-01T00:00:00Z", region="west"): return [k, region, "Synthetic Person %s" % k, "contact-token-%s" % k, created, created]
def order(o, k, t="2026-09-02T10:00:00Z", amt="10.00", st="paid"): return [o, k, amt, "USD", st, t, t.replace("T10", "T11") if "T10" in t else t, t]

class Pkg:
    def __init__(s, custs=None, orders=None, requests=None, edit=None):
        s.top = tempfile.mkdtemp(prefix="m37o-"); s.d = os.path.join(s.top, "pkg"); shutil.copytree(os.path.join(FIX, "clean"), s.d)
        s.p = json.load(open(os.path.join(s.d, "package.json"))); s.inv = json.load(open(os.path.join(s.d, "inventory.json")))
        s.custs = custs if custs is not None else [cust("K1"), cust("K2", "2026-03-01T00:00:00Z", "east")]
        s.orders = orders if orders is not None else [order("A1", "K1"), order("A2", "K2", "2026-09-03T10:00:00Z", "20.00"), order("A3", "K1", "2026-09-04T10:00:00Z", "5.25")]
        s.reqs = requests if requests is not None else []
        s.ch, s.oh = list(CUST_H), list(ORD_H)
        if edit: edit(s)
    def write(s):
        with open(os.path.join(s.d, "data", "customers.csv"), "w") as f: f.write("\n".join(",".join(r) for r in [s.ch] + s.custs) + "\n")
        with open(os.path.join(s.d, "data", "orders.csv"), "w") as f: f.write("\n".join(",".join(r) for r in [s.oh] + s.orders) + "\n")
        with open(os.path.join(s.d, "requests.jsonl"), "w") as f:
            for r in s.reqs: f.write((r if isinstance(r, str) else json.dumps(r)) + "\n")
        json.dump(s.inv, open(os.path.join(s.d, "inventory.json"), "w"), indent=1); json.dump(s.p, open(os.path.join(s.d, "package.json"), "w"), indent=1)
    def data_hash(s): return {f: hashlib.sha256(open(os.path.join(s.d, "data", f), "rb").read()).hexdigest() for f in sorted(os.listdir(os.path.join(s.d, "data")))}
    def run(s, *extra, write=True):
        if write: s.write()
        h0 = s.data_hash(); log = os.path.join(s.top, "audit.log"); env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=AUD, M32_AUDIT_LOG=log)
        r = subprocess.run([PY, TOOL, "review", os.path.join(s.d, "package.json"), "--json"] + list(extra), cwd=s.top, env=env, capture_output=True, text=True, timeout=300)
        if s.data_hash() != h0: TOUCHED.append(s.top)
        if os.path.exists(log):
            for l in open(log).read().splitlines():
                if l.startswith("subprocess.Popen") and "csv_reconcile.py" in l: continue
                if l.startswith(("os.posix_spawn", "os.fork", "os.exec")) and "csv_reconcile.py" in l: continue
                AUDIT.append(l[:300])
            os.remove(log)
        try: j = json.loads(r.stdout)
        except Exception: j = {}
        s.err = r.stderr; return r.returncode, j
    def close(s): shutil.rmtree(s.top, ignore_errors=True)

def codes(j): return sorted({f.get("code") for f in j.get("findings", [])})
def req(rid, typ, subj, rec, jur="EU-GDPR", ver=True, closed=None):
    d = {"request_id": rid, "type": typ, "subject": subj, "received_at": rec, "identity_verified": ver, "jurisdiction": jur}
    if closed: d["closed_at"] = closed
    return d
def R(j, rid): return next((r for r in j.get("requests", []) if r.get("request_id") == rid), {})
def refs(x): return sorted((r["file"], r["line"]) for r in (x or []))
def lines_with(s, k):
    out = [("customers.csv", i + 2) for i, r in enumerate(s.custs) if r[0] == k] + [("orders.csv", i + 2) for i, r in enumerate(s.orders) if r[1] == k]
    return sorted(out)
def T(x): return dt.datetime.strptime(x, "%Y-%m-%dT%H:%M:%SZ")
def add_months(t, n):
    y, m = t.year + (t.month - 1 + n) // 12, (t.month - 1 + n) % 12 + 1
    last = (dt.date(y + (m == 12), m % 12 + 1, 1) - dt.timedelta(days=1)).day
    return t.replace(year=y, month=m, day=min(t.day, last))
def iso_eq(a, b):
    try: return dt.datetime.fromisoformat(a.replace("Z", "+00:00")) == dt.datetime.fromisoformat(b.replace("Z", "+00:00"))
    except Exception: return False
PERSONAL = {"customers.csv": {"customer_id", "region", "name", "contact"}, "orders.csv": {"customer_id", "amount", "event_time"}}

@safe
def r01():
    res = {}; k = Pkg(requests=[req("R1", "access", "K1", "2026-09-10T09:00:00Z", closed="2026-09-20T09:00:00Z")]); rc, j = k.run(); r = R(j, "R1")
    res["complete"] = (rc == 0 and j.get("status") == "complete" and not j.get("findings"), (rc, j.get("status"), codes(j)))
    res["records_exact"] = (refs(r.get("records")) == lines_with(k, "K1") == [("customers.csv", 2), ("orders.csv", 2), ("orders.csv", 4)], refs(r.get("records")))
    res["due_one_month"] = (iso_eq(r.get("due", ""), "2026-10-10T09:00:00Z"), r.get("due"))
    ap = r.get("access_package") or []; res["access_personal_fields_only"] = (bool(ap) and all(set(x.get("values", {})) <= PERSONAL[x["file"]] for x in ap) and all(set(x.get("values", {})) == PERSONAL[x["file"]] for x in ap), [sorted(x.get("values", {})) for x in ap])
    qr = json.dumps(j.get("qualified_review")); res["every_clock_in_qualified_review"] = ("EU-GDPR" in qr and "US-CA-CCPA" in qr, j.get("qualified_review"))
    res["not_legal_advice_and_read_only"] = ("not legal advice" in (j.get("not_legal_advice") or "").lower() and "nothing was deleted" in (j.get("read_only") or ""), None)
    k.close(); row("R01 clean control: complete, R1 finds exactly customers line 2 and orders lines 2 and 4, due 2026-10-10T09:00Z, the access package holds the personal fields only, every clock goes to qualified review, not legal advice", all(v[0] for v in res.values()), res)

@safe
def r02():
    res = {}
    def f(edit):
        k = Pkg(edit=edit); rc, j = k.run(); k.close(); return rc, j
    def addcol(s): s.ch.append("phone"); s.custs = [r + ["tok-%s" % r[0]] for r in s.custs]
    rc, j = f(addcol); res["new_column_unmapped"] = ("unmapped_field" in codes(j) and "phone" in json.dumps(j.get("findings")), codes(j))
    def dropname(s): del s.inv["tables"]["customers.csv"]["fields"]["name"]
    rc, j = f(dropname); uf = [x for x in j.get("findings", []) if x.get("code") == "unmapped_field"]
    res["g13_ignored_column_unmapped_and_marked"] = (bool(uf) and "name" in json.dumps(uf) and "ignored_by_g13" in json.dumps(uf) and '"ignored_by_g13": true' in json.dumps(uf).lower(), uf)
    rc, j = f(lambda s: s.inv["tables"]["customers.csv"]["fields"].update(fax={"category": "contact", "purpose": "x", "basis": "y"})); res["stale_entry"] = ("stale_inventory_entry" in codes(j), codes(j))
    rc, j = f(lambda s: s.inv["tables"]["customers.csv"]["fields"]["region"].pop("purpose")); res["personal_without_purpose"] = (rc == 1 and bool(codes(j)), codes(j))
    rc, j = f(lambda s: s.inv["tables"]["customers.csv"]["fields"]["region"].pop("basis")); res["personal_without_basis"] = (rc == 1 and bool(codes(j)), codes(j))
    rc, j = f(lambda s: s.inv["tables"]["customers.csv"]["fields"]["region"].update(flows=["crm-x"])); res["flow_to_undeclared_system"] = (rc == 1 and bool(codes(j)), codes(j))
    rc, j = f(lambda s: s.inv["tables"]["customers.csv"].pop("retention")); res["personal_table_without_retention"] = (rc in (1, 2) and (rc == 2 or bool(codes(j))), (rc, codes(j)))
    rc, j = f(lambda s: s.inv["tables"]["customers.csv"].pop("subject_key")); res["personal_table_without_subject_key"] = (rc in (1, 2) and (rc == 2 or bool(codes(j))), (rc, codes(j)))
    rc, j = f(lambda s: s.inv["tables"]["customers.csv"]["fields"]["region"].update(category="sensitive")); res["unknown_category_refused"] = (rc == 2, rc)
    row("R02 inventory against the data: a new column and a G13-ignored column are unmapped (the latter marked); a stale entry, a personal field without purpose or basis, an undeclared flow target, a personal table without retention or subject key are named; an unknown category is refused", all(v[0] for v in res.values()), res)

@safe
def r03():
    res = {}
    def due(created, hold=False, orders=None):
        k = Pkg(custs=[cust("K1", created), cust("K2", "2026-03-01T00:00:00Z", "east")], orders=orders); rc, j = k.run(); ret = {x["table"]: x for x in j.get("retention", [])}; k.close(); return rc, j, ret
    rc, j, ret = due("2024-10-02T00:00:00Z"); d = ret.get("customers.csv", {}).get("due", []); res["exact_boundary_due"] = (len(d) == 1 and "2" in json.dumps(d), d)
    obl = [o for o in j.get("obligations", []) if o.get("kind") == "retention"] or [o for o in j.get("obligations", []) if "retention" in json.dumps(o)]
    res["due_record_is_an_obligation_for_the_data_engineer"] = (bool(obl) and "data-engineer" in json.dumps(obl), obl)
    rc, j, ret = due("2024-10-02T00:00:01Z"); res["one_second_later_not_due"] = (ret.get("customers.csv", {}).get("due") == [], ret.get("customers.csv", {}).get("due"))
    rc, j, ret = due("not-a-date"); c = ret.get("customers.csv", {}); res["unreadable_anchor_named_not_guessed"] = (c.get("unreadable_lines") == 1 and c.get("due") == [] and rc == 1, (rc, c.get("unreadable_lines"), c.get("due"), codes(j)))
    rc, j, ret = due("2026-02-01T00:00:00Z", orders=[order("A1", "K1", "2018-09-02T10:00:00Z"), order("A2", "K2", "2026-09-03T10:00:00Z")])
    o = ret.get("orders.csv", {}); qr = json.dumps(j.get("qualified_review"))
    res["held_old_order_outside_g13_window_still_due_and_to_qualified_review"] = (len(o.get("due", [])) == 1 and ("hold" in qr.lower() or "orders.csv" in qr), (o.get("due"), j.get("qualified_review")))
    row("R03 retention: anchor + days at exactly as_of is due and one second later is not; due records become a data-engineer obligation; an unreadable anchor is named and not guessed; a held table's old record (outside the G13 metric window) is still due and goes to qualified review", all(v[0] for v in res.values()), res)

@safe
def r04():
    res = {}
    def one(r, now=None):
        k = Pkg(requests=[r]); 
        if now: k.p["as_of"] = now
        rc, j = k.run(); k.close(); return rc, j, R(j, r["request_id"])
    rc, j, r = one(req("Q1", "access", "K1", "2026-01-31T09:00:00Z", closed="2026-02-27T09:00:00Z")); res["jan31_plus_1_month_is_feb28"] = (iso_eq(r.get("due", ""), "2026-02-28T09:00:00Z"), r.get("due"))
    rc, j, r = one(req("Q1", "access", "K1", "2026-03-31T09:00:00Z", closed="2026-04-01T09:00:00Z")); res["mar31_plus_1_month_is_apr30"] = (iso_eq(r.get("due", ""), "2026-04-30T09:00:00Z"), r.get("due"))
    rc, j, r = one(req("Q1", "access", "K1", "2026-08-01T09:00:00Z", jur="US-CA-CCPA", closed="2026-09-15T09:00:00Z")); res["ccpa_45_days_closed_on_due_is_on_time"] = (iso_eq(r.get("due", ""), "2026-09-15T09:00:00Z") and "closed_late" not in codes(j), (r.get("due"), codes(j)))
    rc, j, r = one(req("Q1", "access", "K1", "2026-08-01T09:00:00Z", jur="US-CA-CCPA", closed="2026-09-15T09:00:01Z")); res["closed_one_second_late"] = ("closed_late" in codes(j) and rc == 1, codes(j))
    rc, j, r = one(req("Q1", "access", "K1", "2026-08-01T09:00:00Z")); res["open_past_due_overdue"] = ("overdue_request" in codes(j), codes(j))
    rc, j, r = one(req("Q1", "access", "K1", "2026-09-20T09:00:00Z")); res["open_not_yet_due_fine"] = ("overdue_request" not in codes(j) and rc == 0, (rc, codes(j)))
    rc, j, r = one(req("Q1", "access", "K1", "2026-09-20T09:00:00Z", jur="BR-LGPD")); res["unknown_jurisdiction_clock_and_review_item"] = ("unknown_jurisdiction_clock" in codes(j) and "BR-LGPD" in json.dumps(j.get("qualified_review")), (codes(j), j.get("qualified_review")))
    row("R04 request clocks: months clamp to the month end (Jan 31 -> Feb 28, Mar 31 -> Apr 30); 45 days closed on the due instant is on time and one second later is closed_late; open past due is overdue; no clock is named and sent to qualified review", all(v[0] for v in res.values()), res)

@safe
def r05():
    res = {}
    k = Pkg(requests=[req("U1", "access", "K1", "2026-09-20T09:00:00Z", ver=False), req("D1", "deletion", "K2", "2026-09-20T09:00:00Z"), req("C1", "correction", "K1", "2026-09-20T09:00:00Z")]); rc, j = k.run()
    u = R(j, "U1"); blob = json.dumps(u)
    res["unverified_looks_nothing_up"] = (not u.get("records") and not u.get("access_package") and "Synthetic Person K1" not in blob and "contact-token-K1" not in blob, u)
    d = R(j, "D1"); dl = json.dumps(d)
    def part(key): return refs(d.get(key)) if isinstance(d.get(key), list) else None
    res["deletion_split_delete_vs_retain_pending_review"] = (part("delete") == [("customers.csv", 3)] and part("retain_pending_review") == [("orders.csv", 3)], {k2: d.get(k2) for k2 in ("delete", "retain_pending_review")})
    res["deletion_propagates_to_systems"] = ("warehouse" in json.dumps(d.get("propagate_to")) and "cfo-books" in json.dumps(d.get("propagate_to")), d.get("propagate_to"))
    c = R(j, "C1"); res["correction_lists_personal_fields"] = ("name" in json.dumps(c) and "contact" in json.dumps(c) and "order_id" not in json.dumps(c.get("fields", c)), {k2: c.get(k2) for k2 in c if k2 not in ("access_package",)})
    res["data_files_unchanged"] = (not TOUCHED, TOUCHED[:2])
    k.close(); row("R05 requests: an unverified request looks nothing up; deletion splits into delete (customers) and retain_pending_review (held orders) and names the systems to propagate to; correction lists the personal fields; no data file changes", all(v[0] for v in res.values()), res)

@safe
def r06():
    res = {}
    a = req("R1", "access", "K1", "2026-09-10T09:00:00Z")
    k = Pkg(requests=[a, a]); rc, j = k.run(); k.close(); res["exact_resend_collapses"] = (len([r for r in j.get("requests", []) if r.get("request_id") == "R1"]) == 1 and rc == 0, (rc, len(j.get("requests", []))))
    k = Pkg(requests=[a, dict(a, subject="K2")]); rc, j = k.run(); k.close(); res["same_id_other_body_refused_and_named"] = (rc in (1, 2) and (rc == 2 or "K2" not in json.dumps(R(j, "R1"))), (rc, codes(j)))
    for name, subj in (("lowercase", "k1"), ("trailing_space", "K1 "), ("prefix", "K"), ("other", "K9")):
        k = Pkg(requests=[req("S1", "access", subj, "2026-09-20T09:00:00Z")]); rc, j = k.run(); k.close(); res["exact_key_only_" + name] = (not R(j, "S1").get("records"), refs(R(j, "S1").get("records")))
    def free(s):
        s.custs[1][3] = "contact-token-K2"; s.custs[1][2] = "Synthetic Person K1 (spouse)"
    k = Pkg(requests=[req("S1", "access", "K1", "2026-09-20T09:00:00Z")], edit=free); rc, j = k.run(); k.close(); res["no_free_text_search"] = (refs(R(j, "S1").get("records")) == [("customers.csv", 2), ("orders.csv", 2), ("orders.csv", 4)], refs(R(j, "S1").get("records")))
    k = Pkg(requests=[req("S1", "access", "K1", "2026-09-20T09:00:00Z")], orders=[order("A1", "K1"), order("A2", "K1", "2026-09-03T10:00:00Z", st="test"), order("A3", "K1", "2026-05-03T10:00:00Z")]); rc, j = k.run(); k.close()
    res["access_finds_test_status_and_out_of_window_rows"] = (refs(R(j, "S1").get("records")) == [("customers.csv", 2), ("orders.csv", 2), ("orders.csv", 3), ("orders.csv", 4)], refs(R(j, "S1").get("records")))
    row("R06 request integrity: an exact re-send collapses, the same id with another body is refused or named; the subject matches by exact key only (no case, space or prefix match, no free-text search); access finds every held line including excluded-status and out-of-window rows", all(v[0] for v in res.values()), res)

@safe
def r07():
    res = {}
    k = Pkg(requests=[req("R1", "access", "K1", "2026-09-10T09:00:00Z")]); out = os.path.join(k.top, "out"); rc1, _ = k.run("--out", out)
    files = sorted(os.listdir(out)) if os.path.isdir(out) else []; res["out_writes_report_and_handoff"] = (rc1 in (0, 1) and files == ["handoff.md", "report.json"], (rc1, files))
    ho = open(os.path.join(out, "handoff.md")).read() if "handoff.md" in files else ""; rep1 = open(os.path.join(out, "report.json"), "rb").read() if "report.json" in files else b""
    low = (ho + rep1.decode("utf-8", "replace")).lower()
    claims = [w for w in ("is compliant", "are compliant", "fully compliant", "certified", "we certify", "legally sufficient", "identity confirmed", "identity was verified by", "we verified the identity", "gdpr compliant", "ccpa compliant") if w in low]
    res["no_compliance_or_identity_claim"] = (not claims, claims)
    res["handoff_says_not_legal_advice"] = ("not legal advice" in ho.lower(), None)
    k.p["mystery"] = 1; rc2, _ = k.run("--out", out); rep2 = open(os.path.join(out, "report.json"), "rb").read()
    res["invalid_keeps_earlier_report"] = (rc2 == 2 and rep1 == rep2, rc2)
    del k.p["mystery"]; inside = os.path.join(k.d, "rep"); rc3, _ = k.run("--out", inside); res["out_inside_package_refused"] = (rc3 == 2 and not os.path.exists(inside), rc3)
    k.close()
    def bad(edit):
        q = Pkg(edit=edit); rc, _ = q.run(); q.close(); return rc
    res["clock_without_source_refused"] = (bad(lambda s: s.p["clocks"]["EU-GDPR"].pop("source")) == 2, None)
    res["path_escape_refused"] = (bad(lambda s: s.p.update(requests="../requests.jsonl")) == 2, None)
    # authoring fix (disclosed): a bad request line is a named rejected row (exit 1), not an invalid package; the doc does
    # not say which, so either is accepted. A received_at without an offset is recorded as OBS in O10, not scored.
    def badrow(r):
        q = Pkg(requests=[r]); rc, j = q.run(); q.close(); return rc == 2 or (rc == 1 and "rejected_request_rows" in codes(j) and not R(j, r["request_id"]).get("records")), (rc, codes(j))
    res["unknown_request_type_refused_or_rejected"] = badrow(req("N1", "export", "K1", "2026-09-10T09:00:00Z"))
    res["non_boolean_identity_verified_rejected"] = badrow(dict(req("N1", "access", "K1", "2026-09-10T09:00:00Z"), identity_verified="yes"))
    row("R07 output and recovery: --out writes report.json and handoff.md; nothing claims compliance, certification or identity verification; the handoff says not legal advice; an invalid run keeps the earlier report; --out inside the package, a clock without a source, a path escape are refused; an unknown request type or a non-boolean identity_verified is rejected and named", all(v[0] for v in res.values()), res)

@safe
def r08():
    rnd = random.Random(3737); bad = []
    for seed in range(12):
        ks = ["K%d" % i for i in range(rnd.randint(2, 6))]; custs = [cust(k, "2026-0%d-01T00:00:00Z" % rnd.randint(1, 8)) for k in ks]
        orders = [order("A%d" % i, rnd.choice(ks + ["K99"]), "2026-09-%02dT10:00:00Z" % rnd.randint(1, 29), "%d.00" % rnd.randint(1, 90), rnd.choice(["paid", "paid", "test"])) for i in range(rnd.randint(1, 15))]
        rq = []
        for i in range(rnd.randint(1, 5)):
            rec = dt.datetime(2026, rnd.randint(6, 9), rnd.randint(1, 28), 9); jur = rnd.choice(["EU-GDPR", "US-CA-CCPA"]); cl = None
            if rnd.random() < 0.6: cl = (rec + dt.timedelta(days=rnd.randint(1, 60))).strftime("%Y-%m-%dT%H:%M:%SZ")
            rq.append(req("Q%d" % i, rnd.choice(["access", "deletion", "correction"]), rnd.choice(ks), rec.strftime("%Y-%m-%dT%H:%M:%SZ"), jur, closed=cl))
        k = Pkg(custs=custs, orders=orders, requests=rq); rc, j = k.run(); probs = []
        asof = T("2026-10-02T00:00:00Z")
        for r in rq:
            t = R(j, r["request_id"]); rec = T(r["received_at"]); due = add_months(rec, 1) if r["jurisdiction"] == "EU-GDPR" else rec + dt.timedelta(days=45)
            if not iso_eq(t.get("due", ""), due.strftime("%Y-%m-%dT%H:%M:%SZ")): probs.append((r["request_id"], "due", t.get("due"), str(due)))
            want = lines_with(k, r["subject"])
            got = refs(t.get("records")) if t.get("records") is not None else sorted(refs(t.get("delete")) + refs(t.get("retain_pending_review")))
            if got != want: probs.append((r["request_id"], "records", got, want))
            late = r.get("closed_at") and T(r["closed_at"]) > due; over = not r.get("closed_at") and due < asof
            if bool(late) != any(f.get("code") == "closed_late" and r["request_id"] in json.dumps(f) for f in j.get("findings", [])): probs.append((r["request_id"], "closed_late"))
            if bool(over) != any(f.get("code") == "overdue_request" and r["request_id"] in json.dumps(f) for f in j.get("findings", [])): probs.append((r["request_id"], "overdue"))
        k.close()
        if probs or rc not in (0, 1): bad.append({"seed": seed, "rc": rc, "probs": probs[:4], "err": k.err[-200:] if rc == 2 else ""})
    row("R08 seeded soak: 12 random packages; every request's due time, matched lines (by file and line) and late/overdue findings equal my model", not bad, {"bad": bad[:2]})

@safe
def o10():
    k = Pkg(requests=[req("N1", "access", "K1", "2026-09-10T09:00:00")]); rc, j = k.run(); r = R(j, "N1"); k.close()
    row("O10 OBS: a request received_at without an offset (the doc requires an offset only for as_of)", True, {"rc": rc, "status": j.get("status"), "due": r.get("due"), "codes": codes(j)})

@safe
def r09():
    src = open(TOOL).read(); imports = [m for m in ("socket", "urllib", "http.client", "requests", "smtplib", "webbrowser", "ftplib", "ssl") if re.search(r"^\s*(import|from)\s+%s\b" % re.escape(m), src, re.M)]
    dels = [m for m in ("os.remove", "os.unlink", "shutil.rmtree", ".unlink(") if m in src]
    row("R09 nothing is deleted, exported or sent: no network import, no audited network/process event other than G13, and every data file byte-identical after every run of this oracle", not imports and not AUDIT and not TOUCHED, {"imports": imports, "delete_calls_in_source": dels, "audit_hits": AUDIT[:5], "data_changed_in": TOUCHED[:3]})

for f in (r01, r02, r03, r04, r05, r06, r07, r08, o10, r09): f()
json.dump({"tool": TOOL, "python": sys.version.split()[0], "rows": ROWS}, open(OUT, "w"), indent=1, default=str)
n = sum(r["pass"] for r in ROWS); print("M37 ORACLE %d/%d core %s" % (n, len(ROWS), "PASS" if n == len(ROWS) else "FAIL"))
