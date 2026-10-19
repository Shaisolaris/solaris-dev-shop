#!/usr/bin/env python3
"""privacy_inventory.py: synthetic data inventory, retention review and data-subject request handling (G37).

Maps every field that actually exists in a local data drop (read through the data engineer's G13
csv_reconcile.py contracts, including columns G13 ignores) to an inventory entry, finds records past their
configured retention, traces access / deletion / correction requests to the exact records they touch, and
lists every point that needs a qualified human reviewer. It plans; it never deletes, exports, sends or
contacts anyone, and it is not legal advice. Exit 0 no findings, 1 findings named, 2 invalid (nothing written).
Reference: privacy-inventory.md next to this file.
"""
import argparse
import calendar
import csv
import datetime as dt
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

SCHEMA = "solaris.privacy-inventory/1"
REPORT_SCHEMA = "solaris.privacy-inventory-report/1"
HERE = Path(__file__).resolve().parent
G13 = HERE.parent.parent / "data" / "data-engineer" / "csv_reconcile.py"
CATEGORIES = ("identifier", "contact", "financial", "location", "behavioral", "free_text", "special_category", "not_personal")
PERSONAL = set(CATEGORIES) - {"not_personal"}
REQUEST_TYPES = ("access", "deletion", "correction")
TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2}(\.\d{1,9})?)?(Z|[+-]\d{2}(:?\d{2})?)?)?$")
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$")
PKG_KEYS = {"schema", "as_of", "contracts", "inventory", "requests", "clocks"}
REQ_FIELDS = ("request_id", "type", "subject", "received_at", "identity_verified", "jurisdiction")
NOT_ADVICE = ("Not legal advice. Retention periods, response clocks and lawful bases are the values configured "
              "in this package; a qualified reviewer confirms them for each jurisdiction before anyone acts.")


class Invalid(Exception):
    pass


def need(c, m):
    if not c:
        raise Invalid(m)


def _no_dupes(pairs):
    out = {}
    for k, v in pairs:
        if k in out:
            raise Invalid("duplicate JSON key %r" % k)
        out[k] = v
    return out


def _no_float(s):
    raise Invalid("numbers with a fraction are refused here (%s)" % s)


def load_json(p, where):
    need(p.is_file() and p.stat().st_size < 4 * 1024 * 1024, "%s: a JSON file under 4 MiB" % where)
    try:
        return json.loads(p.read_text(encoding="utf-8"), object_pairs_hook=_no_dupes, parse_float=_no_float)
    except UnicodeDecodeError:
        raise Invalid("%s: not UTF-8" % where) from None
    except json.JSONDecodeError as exc:
        raise Invalid("%s: not JSON (%s)" % (where, exc.msg)) from None
    except RecursionError:
        raise Invalid("%s: JSON nested too deeply" % where) from None


def inside(base, rel, where):
    need(isinstance(rel, str) and rel and not os.path.isabs(rel), "%s: a relative path inside the package folder" % where)
    p = Path(os.path.realpath(base / rel))
    need(p == base or base in p.parents, "%s: %r leaves the package folder" % (where, rel))
    need(p.is_file(), "%s: %r is not a file" % (where, rel))
    return p


def ts(s):
    """ISO date or date-time; no offset = UTC. Returns None when it does not parse."""
    if not isinstance(s, str) or not TS_RE.match(s.strip()):
        return None
    s = s.strip().replace(" ", "T").replace("Z", "+00:00")
    if len(s) == 10:
        s += "T00:00:00"
    m = re.match(r"^(.*[T]\d{2}:\d{2}(?::\d{2})?)(\.\d+)?([+-]\d{2})(:?)(\d{2})?$", s)
    if m:
        frac = (m.group(2) or "")[:7]
        s = m.group(1) + frac + m.group(3) + ":" + (m.group(5) or "00")
    try:
        t = dt.datetime.fromisoformat(s)
    except ValueError:
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=dt.timezone.utc)
    return t.astimezone(dt.timezone.utc)


def add_months(t, n):
    y, m = divmod(t.month - 1 + n, 12)
    y, m = t.year + y, m + 1
    return t.replace(year=y, month=m, day=min(t.day, calendar.monthrange(y, m)[1]))


def due_from(t, clock):
    return add_months(t, clock["months"]) if "months" in clock else t + dt.timedelta(days=clock["days"])


def g13(contract):
    need(G13.is_file(), "csv_reconcile.py (G13) is missing")
    r = subprocess.run([sys.executable, str(G13), "reconcile", str(contract), "--json"], capture_output=True, text=True,
                       env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    if r.returncode not in (0, 1):
        last = (r.stderr.strip() or r.stdout.strip() or "no output").splitlines()[-1]
        raise Invalid("csv_reconcile.py refused %s: %s" % (contract.name, last[:300]))
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        raise Invalid("csv_reconcile.py printed no JSON for %s" % contract.name) from None


def tables_of(contract, rep):
    """Every table a G13 contract reads, with the canonical name of every header column actually present."""
    c = load_json(contract, contract.name)
    out = []
    for part in ("facts", "dimension"):
        t = c.get(part)
        if not isinstance(t, dict):
            continue
        aliases = {k.strip().lower(): v for k, v in t.get("header_aliases", {}).items()}
        cols = dict(t.get("columns", {}))
        p = Path(os.path.realpath(contract.parent / t["file"]))
        raw = p.read_bytes().decode("utf-8-sig")
        rows = list(csv.reader(io.StringIO(raw, newline="")))
        need(rows, "%s: empty file" % t["file"])
        header = []
        for h in rows[0]:
            k = h.strip()
            name = aliases.get(k.lower(), k)
            hit = next((cname for cname in cols if cname.lower() == name.lower()), name)
            header.append(hit)
        info = next((i for i in rep.get("inputs", []) if i.get("file") == t["file"]), {})
        out.append({"file": t["file"], "path": p, "contract": contract.name, "header": header, "declared": cols,
                    "rows": rows[1:], "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                    "g13_ignored": info.get("ignored_columns", []), "g13_status": rep.get("status")})
    return out


def load(path):
    p = Path(path)
    c = load_json(p, p.name)
    need(isinstance(c, dict) and c.get("schema") == SCHEMA, "package: schema must be %r" % SCHEMA)
    extra = sorted(set(c) - PKG_KEYS)
    need(not extra, "package: unknown keys %s (schema drift)" % extra)
    base = Path(os.path.realpath(p.parent))
    P = {"base": base, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
    P["as_of"] = ts(c.get("as_of"))
    need(P["as_of"] is not None and isinstance(c["as_of"], str) and ("Z" in c["as_of"] or "+" in c["as_of"][10:]),
         "as_of: a timestamp with Z or an offset")
    need(isinstance(c.get("contracts"), list) and c["contracts"], "contracts: a non-empty list of G13 contracts")
    P["contracts"] = [inside(base, x, "contracts[%d]" % i) for i, x in enumerate(c["contracts"])]
    P["inventory"] = load_json(inside(base, c.get("inventory"), "inventory"), "inventory")
    P["requests"] = inside(base, c["requests"], "requests") if c.get("requests") is not None else None
    clocks = c.get("clocks", {})
    need(isinstance(clocks, dict), "clocks: {jurisdiction: {days|months, source}}")
    for j, k in clocks.items():
        need(isinstance(k, dict) and set(k) in ({"days", "source"}, {"months", "source"}), "clocks.%s: {days or months, source}" % j)
        n = k.get("days", k.get("months"))
        need(type(n) is int and 1 <= n <= 366, "clocks.%s: a whole number of days (1-366) or months" % j)
        need(isinstance(k["source"], str) and k["source"].strip(), "clocks.%s.source: say where the value comes from" % j)
    P["clocks"] = clocks
    inv = P["inventory"]
    need(isinstance(inv, dict) and set(inv) <= {"systems", "tables"}, "inventory: {systems, tables}")
    need(isinstance(inv.get("systems"), list) and isinstance(inv.get("tables"), dict), "inventory: systems list and tables object")
    for s in inv["systems"]:
        need(isinstance(s, dict) and isinstance(s.get("id"), str) and ID_RE.match(s["id"]), "inventory.systems: objects with a plain id")
    for name, t in inv["tables"].items():
        need(isinstance(t, dict) and isinstance(t.get("fields"), dict), "inventory.tables.%s: {fields, ...}" % name)
        for f, e in t["fields"].items():
            need(isinstance(e, dict) and e.get("category") in CATEGORIES, "inventory.tables.%s.fields.%s.category: one of %s" % (name, f, ", ".join(CATEGORIES)))
        r = t.get("retention")
        if r is not None:
            need(isinstance(r, dict) and type(r.get("days")) is int and r["days"] >= 1 and isinstance(r.get("anchor"), str),
                 "inventory.tables.%s.retention: {days, anchor, basis, hold_for_review?}" % name)
    return P


def build(P):
    F, review, obligations = [], [], []
    inv = P["inventory"]
    systems = {s["id"] for s in inv["systems"]}
    tables = []
    for c in P["contracts"]:
        tables += tables_of(c, g13(c))
    seen_files = {}
    for t in tables:
        need(t["file"] not in seen_files, "table %s is read by two contracts" % t["file"])
        seen_files[t["file"]] = t
    ob_n = [0]

    def ob(kind, **kw):
        ob_n[0] += 1
        o = dict(id="OB-%03d" % ob_n[0], kind=kind, **kw)
        obligations.append(o)
        return o

    map_rows = []
    for t in tables:
        it = inv["tables"].get(t["file"])
        if it is None:
            F.append({"code": "table_not_inventoried", "table": t["file"]})
            ob("inventory_gap", refs=[{"file": t["file"]}], owner="compliance-auditor", review="operational")
            continue
        present = set(t["header"])
        for f in t["header"]:
            e = it["fields"].get(f)
            if e is None:
                F.append({"code": "unmapped_field", "table": t["file"], "field": f,
                          "ignored_by_g13": f in t["g13_ignored"]})
                ob("inventory_gap", refs=[{"file": t["file"], "field": f}], owner="compliance-auditor", review="operational")
                continue
            row = {"table": t["file"], "field": f, "category": e["category"], "purpose": e.get("purpose"),
                   "basis": e.get("basis"), "flows": e.get("flows", []), "declared_in_g13": f in t["declared"]}
            map_rows.append(row)
            if e["category"] in PERSONAL and not (e.get("purpose") and e.get("basis")):
                F.append({"code": "personal_field_without_purpose_or_basis", "table": t["file"], "field": f})
            if e["category"] in ("special_category", "free_text"):
                review.append({"why": "%s field %s.%s: handling needs a qualified reviewer" % (e["category"], t["file"], f),
                               "refs": [{"file": t["file"], "field": f}]})
            for fl in e.get("flows", []):
                if fl not in systems:
                    F.append({"code": "flow_to_undeclared_system", "table": t["file"], "field": f, "system": fl})
        for f in sorted(set(it["fields"]) - present):
            F.append({"code": "stale_inventory_entry", "table": t["file"], "field": f})
        personal = [f for f in t["header"] if it["fields"].get(f, {}).get("category") in PERSONAL]
        if personal and it.get("retention") is None:
            F.append({"code": "personal_table_without_retention", "table": t["file"]})
        if personal and not it.get("subject_key"):
            F.append({"code": "personal_table_without_subject_key", "table": t["file"]})
        if it.get("subject_key") and it["subject_key"] not in present:
            F.append({"code": "subject_key_not_in_data", "table": t["file"], "field": it["subject_key"]})
        t["inv"] = it
    for name in sorted(set(inv["tables"]) - set(seen_files)):
        F.append({"code": "inventoried_table_not_in_data", "table": name})
    # retention
    retention = []
    for t in tables:
        it = t.get("inv")
        if not it or not it.get("retention"):
            continue
        r = it["retention"]
        if r["anchor"] not in t["header"]:
            F.append({"code": "retention_anchor_not_in_data", "table": t["file"], "anchor": r["anchor"]})
            continue
        ai = t["header"].index(r["anchor"])
        ki = t["header"].index(it["subject_key"]) if it.get("subject_key") in t["header"] else None
        due, bad = [], []
        for n, row in enumerate(t["rows"], 2):
            if not row or all(not x.strip() for x in row):
                continue
            a = ts(row[ai]) if ai < len(row) else None
            if a is None:
                bad.append(n)
                continue
            if a + dt.timedelta(days=r["days"]) <= P["as_of"]:
                due.append({"line": n, "subject": row[ki] if ki is not None and ki < len(row) else None,
                            "anchor": row[ai], "expired_on": (a + dt.timedelta(days=r["days"])).date().isoformat()})
        if bad:
            F.append({"code": "retention_anchor_unreadable", "table": t["file"], "lines": bad[:50], "count": len(bad)})
        hold = bool(r.get("hold_for_review"))
        if due:
            o = ob("retention", refs=[{"file": t["file"], "line": d["line"]} for d in due], owner="data-engineer",
                   review="qualified" if hold else "operational", action="review for deletion; nothing deleted by this tool")
            if hold:
                review.append({"why": "%s: %d record(s) past %d days but marked hold_for_review (%s)" % (
                    t["file"], len(due), r["days"], r.get("basis", "no basis given")), "refs": o["refs"][:20], "obligation": o["id"]})
        retention.append({"table": t["file"], "days": r["days"], "anchor": r["anchor"], "basis": r.get("basis"),
                          "hold_for_review": hold, "due": due, "unreadable_lines": len(bad)})
    # requests
    reqs = []
    if P["requests"] is not None:
        reqs = requests(P, tables, F, review, ob)
    for j, k in sorted(P["clocks"].items()):
        review.append({"why": "response clock for %s is configured as %s %s (source: %s); confirm before relying on it" % (
            j, k.get("days", k.get("months")), "days" if "days" in k else "month(s)", k["source"])})
    rep = {"schema": REPORT_SCHEMA, "package_sha256": P["sha256"], "as_of": P["as_of"].isoformat(),
           "tables": [{"file": t["file"], "contract": t["contract"], "sha256": t["sha256"], "rows": len([r for r in t["rows"] if r]),
                       "fields": t["header"], "g13_ignored": t["g13_ignored"], "g13_status": t["g13_status"]} for t in tables],
           "inventory_map": map_rows, "retention": retention, "requests": reqs, "obligations": obligations,
           "qualified_review": review, "findings": F, "not_legal_advice": NOT_ADVICE,
           "read_only": "local files only; nothing was deleted, exported, sent or changed"}
    rep["status"] = "complete" if not F else "complete_with_findings"
    return rep


def requests(P, tables, F, review, ob):
    lines = P["requests"].read_text(encoding="utf-8").splitlines()
    seen, conflicts, bad = {}, set(), []
    for n, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            o = json.loads(line, object_pairs_hook=_no_dupes)
        except (ValueError, Invalid):
            bad.append(n)
            continue
        if not isinstance(o, dict) or any(k not in o for k in REQ_FIELDS) or o["type"] not in REQUEST_TYPES \
                or not isinstance(o["identity_verified"], bool) or ts(o["received_at"]) is None \
                or (o.get("closed_at") is not None and ts(o["closed_at"]) is None):
            bad.append(n)
            continue
        k = o["request_id"]
        o["_line"] = n
        if k in conflicts:
            continue
        if k in seen:
            if {a: b for a, b in seen[k].items() if a != "_line"} != {a: b for a, b in o.items() if a != "_line"}:
                conflicts.add(k)
                del seen[k]
            continue
        seen[k] = o
    if bad:
        F.append({"code": "rejected_request_rows", "lines": bad[:50], "count": len(bad)})
    if conflicts:
        F.append({"code": "conflicting_request_ids", "ids": sorted(conflicts)})
    out = []
    for k in sorted(seen, key=lambda x: (ts(seen[x]["received_at"]), x)):
        o = seen[k]
        rec = {"request_id": k, "type": o["type"], "line": o["_line"], "jurisdiction": o["jurisdiction"],
               "received_at": ts(o["received_at"]).isoformat()}
        clock = P["clocks"].get(o["jurisdiction"])
        if clock is None:
            F.append({"code": "unknown_jurisdiction_clock", "request_id": k, "jurisdiction": o["jurisdiction"]})
            review.append({"why": "request %s: no response clock configured for %r" % (k, o["jurisdiction"]), "refs": [{"line": o["_line"]}]})
            rec["due"] = None
        else:
            rec["due"] = due_from(ts(o["received_at"]), clock).isoformat()
        closed = ts(o["closed_at"]) if o.get("closed_at") else None
        rec["closed_at"] = closed.isoformat() if closed else None
        if rec["due"] and closed is None and P["as_of"] > ts(rec["due"]):
            F.append({"code": "overdue_request", "request_id": k, "due": rec["due"]})
        if rec["due"] and closed is not None and closed > ts(rec["due"]):
            F.append({"code": "closed_late", "request_id": k, "due": rec["due"], "closed_at": rec["closed_at"]})
        if not o["identity_verified"]:
            rec["status"] = "awaiting_identity_verification"
            rec["note"] = "nothing about the subject is looked up or shown until identity is verified"
            o_ = ob("request", refs=[{"line": o["_line"]}], owner="compliance-auditor", review="operational",
                    action="verify identity", due=rec["due"])
            rec["obligation"] = o_["id"]
            out.append(rec)
            continue
        hits = []
        for t in tables:
            it = t.get("inv")
            if not it or it.get("subject_key") not in t["header"]:
                continue
            ki = t["header"].index(it["subject_key"])
            for n, row in enumerate(t["rows"], 2):
                if ki < len(row) and row[ki].strip() == o["subject"]:
                    hits.append((t, n, row))
        rec["records"] = [{"file": t["file"], "line": n} for t, n, _ in hits]
        if not hits:
            rec["status"] = "no_records_found"
        elif o["type"] == "access":
            rec["status"] = "access_package_ready_for_review"
            rec["access_package"] = [{"file": t["file"], "line": n,
                                      "values": {f: (row[i] if i < len(row) else "") for i, f in enumerate(t["header"])
                                                 if t["inv"]["fields"].get(f, {}).get("category") in PERSONAL}}
                                     for t, n, row in hits]
        elif o["type"] == "deletion":
            plan, keep = [], []
            for t, n, row in hits:
                r = t["inv"].get("retention") or {}
                (keep if r.get("hold_for_review") else plan).append({"file": t["file"], "line": n})
            flows = sorted({fl for t, _, _ in hits for e in t["inv"]["fields"].values() for fl in e.get("flows", [])})
            rec.update(status="deletion_plan_ready_for_review", delete=plan, retain_pending_review=keep, propagate_to=flows)
            if keep:
                review.append({"why": "deletion request %s conflicts with retention on %d record(s); a qualified reviewer decides" % (k, len(keep)),
                               "refs": keep[:20], "request": k})
        else:
            rec["status"] = "correction_ready_for_review"
            rec["fields"] = sorted({f for t, _, _ in hits for f in t["header"] if t["inv"]["fields"].get(f, {}).get("category") in PERSONAL})
        o_ = ob("request", refs=rec["records"][:50] or [{"line": o["_line"]}], owner="compliance-auditor",
                review="qualified" if rec.get("retain_pending_review") else "operational", action=rec["status"], due=rec["due"])
        rec["obligation"] = o_["id"]
        out.append(rec)
    return out


def handoff(rep):
    L = ["# Privacy inventory handoff (INTERNAL DRAFT for legal-advisor and a qualified reviewer)", "", rep["not_legal_advice"], "",
         "Status: **%s** as of %s. Nothing was deleted, exported or sent." % (rep["status"], rep["as_of"]), "",
         "## Tables", ""]
    for t in rep["tables"]:
        L.append("- %s (%d rows, sha256 %s...): %s" % (t["file"], t["rows"], t["sha256"][:12], ", ".join(t["fields"])))
    L += ["", "## Findings"] + (["- %s %s" % (f["code"], json.dumps({k: v for k, v in f.items() if k != "code"}, sort_keys=True)[:240])
                                  for f in rep["findings"]] or ["- none"])
    L += ["", "## Needs a qualified reviewer"] + ["- " + r["why"] for r in rep["qualified_review"]]
    L += ["", "## Obligations"] + ["- %s %s owner %s, review %s%s" % (o["id"], o["kind"], o["owner"], o["review"],
                                    (", due " + o["due"]) if o.get("due") else "") for o in rep["obligations"]]
    L += ["", "## Requests"] + ["- %s %s: %s (due %s)" % (r["request_id"], r["type"], r["status"], r["due"]) for r in rep["requests"]]
    return "\n".join(L) + "\n"


def write_out(out, rep, P):
    o = Path(os.path.realpath(out))
    need(not (o == P["base"] or P["base"] in o.parents), "--out must be outside the package folder")
    tmps = []
    try:
        o.mkdir(parents=True, exist_ok=True)
        for name, text in (("report.json", json.dumps(rep, indent=1, sort_keys=True) + "\n"), ("handoff.md", handoff(rep))):
            fd, tmp = tempfile.mkstemp(dir=str(o), prefix="." + name + ".")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(text)
                f.flush()
                os.fsync(f.fileno())
            tmps.append((tmp, o / name))
        for tmp, dst in tmps:
            os.replace(tmp, str(dst))
    except OSError as exc:
        for tmp, _ in tmps:
            if os.path.exists(tmp):
                os.unlink(tmp)
        raise Invalid("--out cannot be written (%s)" % exc.__class__.__name__) from None


def summary(rep):
    L = ["privacy-inventory: %s (as of %s)" % (rep["status"], rep["as_of"])]
    for t in rep["tables"]:
        L.append("  table %s: %d rows, %d fields" % (t["file"], t["rows"], len(t["fields"])))
    for r in rep["retention"]:
        L.append("  retention %s: %d past %d days%s" % (r["table"], len(r["due"]), r["days"], " (hold for review)" if r["hold_for_review"] else ""))
    for r in rep["requests"]:
        L.append("  request %s %s: %s, due %s" % (r["request_id"], r["type"], r["status"], r["due"]))
    for f in rep["findings"]:
        L.append("  finding %s" % f["code"])
    L.append("  qualified review items: %d; obligations: %d" % (len(rep["qualified_review"]), len(rep["obligations"])))
    L.append("  " + rep["read_only"])
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Synthetic privacy inventory, retention and request tracing; plans only.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("review")
    r.add_argument("package")
    r.add_argument("--json", action="store_true")
    r.add_argument("--out", help="folder for report.json and handoff.md (written atomically)")
    a = ap.parse_args(argv)
    try:
        P = load(a.package)
        rep = build(P)
        if a.out:
            write_out(a.out, rep, P)
    except Invalid as exc:
        print("invalid: %s (nothing written)" % exc, file=sys.stderr)
        return 2
    except (OSError, UnicodeDecodeError, csv.Error) as exc:
        print("invalid: %s (nothing written)" % exc.__class__.__name__, file=sys.stderr)
        return 2
    print(json.dumps(rep, indent=1, sort_keys=True) if a.json else summary(rep))
    return 0 if rep["status"] == "complete" else 1


if __name__ == "__main__":
    sys.exit(main())
