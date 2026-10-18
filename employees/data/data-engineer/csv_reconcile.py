#!/usr/bin/env python3
"""Reconciled metrics from dirty CSV files (Solaris data-engineer).

A contract (JSON, schema "solaris.csv-reconcile/1") names the fact file, its grain (the columns
that identify one event), column types, required columns, the duplicate rule, an optional
dimension file joined on a key, the reporting window, the as-of cutoff and the metrics.
The tool reads the files locally, never imputes a value, never counts a duplicate twice,
never fans out a join, and accounts for every row it did not use.

Order of operations (each row lands in exactly one bucket):
  parse -> rejected (malformed / bad value) | grain column missing
  -> loaded after as_of (late; not part of this as-of view)
  -> duplicates on the grain: exact copies collapsed; differing versions resolved by the
     declared rule (latest by a column, or reject all versions); ties unresolved.
     This happens BEFORE status and window, so a newer "void" version cancels an order.
  -> the surviving version: missing required value | excluded status | outside window
  -> join to the dimension: matched | unmatched (orphan) | ambiguous key; never fanned out
  -> metrics (nulls in a metric column are skipped and counted, never treated as 0)

Same files + same contract give the same bytes. Nothing runs in a warehouse.

Usage:
  csv_reconcile.py reconcile CONTRACT.json [--json] [--out REPORT] [--rejects REJECTS.csv]
Exit codes: 0 every row accounted and nothing excluded for quality, controls match;
            1 reconciled with quality exclusions, late rows, orphans or control mismatch;
            2 invalid contract or input (nothing written).
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import os
import re
import secrets
import stat
import sys
from decimal import Context, Decimal, Inexact, InvalidOperation, localcontext
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
except ImportError:  # pragma: no cover
    ZoneInfo = None

CONTRACT_SCHEMA = "solaris.csv-reconcile/1"
REPORT_SCHEMA = "solaris.csv-reconcile-report/1"
TYPES = ("str", "decimal", "int", "timestamp")
AGGS = ("sum", "count", "count_distinct", "min", "max")
MAX_FILE_BYTES = 512 * 1024 * 1024
MAX_ROWS = 5_000_000
MAX_FIELD = 4096
DEFAULT_NULLS = ("", "NULL", "null")
DEC_RE = re.compile(r"^[+-]?[0-9]{1,20}(\.[0-9]{1,10})?$")  # bounded so every sum stays exact
NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")
UNMATCHED, AMBIGUOUS = "(unmatched)", "(ambiguous)"


class Invalid(Exception):
    pass


# -- contract -----------------------------------------------------------------------

def _need(cond: bool, msg: str) -> None:
    if not cond:
        raise Invalid(msg)


def _safe_file(base: Path, rel: Any, where: str) -> Path:
    _need(isinstance(rel, str) and rel and not os.path.isabs(rel) and "\x00" not in rel,
          f"{where}: must be a relative file name inside the contract folder")
    p = base / rel
    real = Path(os.path.realpath(p))
    _need(os.path.commonpath([str(real), str(base)]) == str(base), f"{where}: {rel!r} points outside the contract folder")
    try:
        st = os.lstat(p)
    except FileNotFoundError:
        raise Invalid(f"{where}: {rel} does not exist") from None
    _need(not stat.S_ISLNK(st.st_mode), f"{where}: {rel} is a symlink; pass the real file")
    _need(stat.S_ISREG(st.st_mode), f"{where}: {rel} is not a regular file")
    _need(st.st_size <= MAX_FILE_BYTES, f"{where}: {rel} is larger than {MAX_FILE_BYTES} bytes")
    return p


def _time_const(v: Any, where: str, tz) -> dt.datetime:
    _need(isinstance(v, str), f"{where}: expected an ISO 8601 time")
    t = _parse_time(v, tz)
    _need(t is not None, f"{where}: {v!r} is not an ISO 8601 time")
    return t


def _policy(v: Any, where: str, cols: Dict[str, str]) -> Tuple[str, Optional[str]]:
    if v in (None, "reject"):
        return "reject", None
    _need(isinstance(v, str) and v.startswith("latest:"), f"{where}: use \"reject\" or \"latest:<column>\"")
    col = v.split(":", 1)[1]
    _need(col in cols and cols[col] in ("timestamp", "int", "decimal"), f"{where}: {col!r} must be a declared timestamp/int/decimal column")
    return "latest", col


def _table(t: Any, where: str, base: Path) -> Dict[str, Any]:
    _need(isinstance(t, dict), f"{where}: expected an object")
    cols = t.get("columns")
    _need(isinstance(cols, dict) and cols, f"{where}.columns: declare every column you use with a type")
    for c, ty in cols.items():
        _need(isinstance(c, str) and NAME_RE.match(c), f"{where}.columns: {c!r} is not a plain column name")
        _need(ty in TYPES, f"{where}.columns.{c}: type must be one of {', '.join(TYPES)}")
    aliases = t.get("header_aliases", {})
    _need(isinstance(aliases, dict) and all(isinstance(k, str) and v in cols for k, v in aliases.items()),
          f"{where}.header_aliases: map raw header text to a declared column")
    nulls = t.get("null_tokens", list(DEFAULT_NULLS))
    _need(isinstance(nulls, list) and all(isinstance(x, str) for x in nulls), f"{where}.null_tokens: list of strings")
    required = t.get("required", [])
    _need(isinstance(required, list) and all(c in cols for c in required), f"{where}.required: declared columns only")
    thousands = t.get("thousands_separator")
    _need(thousands in (None, ",", " ", "_", "'"), f"{where}.thousands_separator: one of , space _ '")
    delim = t.get("delimiter", ",")
    _need(delim in (",", ";", "\t", "|"), f"{where}.delimiter: one of , ; tab |")
    return {"path": _safe_file(base, t.get("file"), f"{where}.file"), "file": t.get("file"), "columns": dict(cols),
            "aliases": {k.strip().lower(): v for k, v in aliases.items()}, "nulls": set(nulls),
            "required": list(required), "thousands": thousands, "delimiter": delim,
            "upper": [c for c in t.get("uppercase", []) if c in cols]}


def load_contract(path: str) -> Dict[str, Any]:
    p = Path(path)
    try:
        st = os.lstat(p)
    except FileNotFoundError:
        raise Invalid(f"{p.name}: no such contract") from None
    _need(stat.S_ISREG(st.st_mode) and st.st_size < 1024 * 1024, f"{p.name}: contract must be a regular file under 1 MiB")
    base = Path(os.path.realpath(p.parent))
    try:
        c = json.loads(p.read_text(encoding="utf-8"), object_pairs_hook=_no_dupes, parse_constant=_no_const)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Invalid(f"{p.name}: not UTF-8 JSON ({exc.__class__.__name__})") from None
    _need(isinstance(c, dict) and c.get("schema") == CONTRACT_SCHEMA, f"contract: schema must be {CONTRACT_SCHEMA!r}")
    tzname = c.get("timezone")
    _need(isinstance(tzname, str) and tzname, "contract.timezone: required (the zone assumed for timestamps without an offset)")
    try:
        tz = dt.timezone.utc if tzname.upper() == "UTC" else ZoneInfo(tzname)
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        raise Invalid(f"contract.timezone: unknown zone {tzname!r}") from None
    facts = _table(c.get("facts"), "facts", base)
    grain = c["facts"].get("grain")
    _need(isinstance(grain, list) and grain and all(g in facts["columns"] for g in grain), "facts.grain: one or more declared columns")
    facts["grain"] = list(grain)
    facts["required"] = sorted(set(facts["required"]) | set(grain), key=list(facts["columns"]).index)
    facts["policy"] = _policy(c["facts"].get("duplicate_policy"), "facts.duplicate_policy", facts["columns"])
    st_col = c["facts"].get("status_column")
    excl = c["facts"].get("exclude_status", [])
    _need(st_col is None or st_col in facts["columns"], "facts.status_column: a declared column")
    _need(isinstance(excl, list) and all(isinstance(x, str) for x in excl), "facts.exclude_status: list of strings")
    facts["status"] = (st_col, set(excl))
    loaded = c["facts"].get("loaded_at_column")
    _need(loaded is None or facts["columns"].get(loaded) == "timestamp", "facts.loaded_at_column: a declared timestamp column")
    facts["loaded_at"] = loaded
    win = c.get("window")
    _need(isinstance(win, dict), "contract.window: {column, start, end} is required")
    _need(facts["columns"].get(win.get("column")) == "timestamp", "window.column: a declared timestamp column of the facts")
    window = {"column": win["column"], "start": _time_const(win.get("start"), "window.start", tz),
              "end": _time_const(win.get("end"), "window.end", tz)}
    _need(window["start"] < window["end"], "window: start must be before end")
    as_of = _time_const(c["as_of"], "as_of", tz) if c.get("as_of") is not None else None
    _need(as_of is None or loaded is not None, "as_of needs facts.loaded_at_column to judge lateness")
    dim = None
    if c.get("dimension") is not None:
        dim = _table(c["dimension"], "dimension", base)
        key = c["dimension"].get("key")
        fk = c["dimension"].get("fact_key", key)
        _need(key in dim["columns"] and fk in facts["columns"], "dimension.key / fact_key: declared columns")
        attrs = c["dimension"].get("attributes", [])
        _need(isinstance(attrs, list) and attrs and all(a in dim["columns"] and a != key for a in attrs), "dimension.attributes: declared columns")
        _need(not set(attrs) & set(facts["columns"]), "dimension.attributes must not reuse fact column names")
        dim.update(key=key, fact_key=fk, attributes=list(attrs),
                   policy=_policy(c["dimension"].get("duplicate_policy"), "dimension.duplicate_policy", dim["columns"]))
        dim["required"] = sorted(set(dim["required"]) | {key})
        _need(os.path.realpath(dim["path"]) != os.path.realpath(facts["path"]), "dimension.file must differ from facts.file")
    known = set(facts["columns"]) | (set(dim["attributes"]) if dim else set())
    metrics = c.get("metrics")
    _need(isinstance(metrics, list) and metrics, "contract.metrics: at least one metric")
    ms, names = [], set()
    for i, m in enumerate(metrics):
        _need(isinstance(m, dict), f"metrics[{i}]: expected an object")
        name, agg, col, by = m.get("name"), m.get("agg"), m.get("column"), m.get("by", [])
        _need(isinstance(name, str) and NAME_RE.match(name) and name not in names, f"metrics[{i}].name: unique plain name")
        _need(agg in AGGS, f"metrics[{i}].agg: one of {', '.join(AGGS)}")
        _need(col in facts["columns"], f"metrics[{i}].column: a declared fact column")
        _need(agg not in ("sum", "min", "max") or facts["columns"][col] in ("decimal", "int"), f"metrics[{i}]: {agg} needs a numeric column")
        _need(isinstance(by, list) and all(b in known for b in by), f"metrics[{i}].by: fact columns or dimension attributes")
        names.add(name)
        ms.append({"name": name, "agg": agg, "column": col, "by": list(by)})
    controls = None
    if c.get("controls") is not None:
        ct = c["controls"]
        _need(isinstance(ct, dict), "controls: expected an object")
        controls = {"path": _safe_file(base, ct.get("file"), "controls.file"), "file": ct.get("file"),
                    "sum_column": ct.get("sum_column")}
        _need(controls["sum_column"] is None or facts["columns"].get(controls["sum_column"]) == "decimal",
              "controls.sum_column: a declared decimal fact column")
    return {"base": base, "tz": tz, "tzname": tzname, "facts": facts, "dimension": dim, "window": window,
            "as_of": as_of, "metrics": ms, "controls": controls, "contract_sha256": hashlib.sha256(p.read_bytes()).hexdigest()}


def _no_dupes(pairs):
    out = {}
    for k, v in pairs:
        if k in out:
            raise Invalid(f"contract: duplicate key {k!r}")
        out[k] = v
    return out


def _no_const(name):
    raise Invalid(f"contract: non-finite number {name}")


# -- parsing ------------------------------------------------------------------------

def _parse_time(s: str, tz) -> Optional[dt.datetime]:
    s = s.strip()
    try:
        if len(s) == 10:
            d = dt.date.fromisoformat(s)
            t = dt.datetime(d.year, d.month, d.day)
        else:
            iso = s.replace(" ", "T", 1) if "T" not in s else s
            if iso.endswith(("Z", "z")):
                iso = iso[:-1] + "+00:00"  # Python 3.9/3.10 fromisoformat does not accept Z
            t = dt.datetime.fromisoformat(iso)
    except ValueError:
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=tz)
    return t.astimezone(dt.timezone.utc)


def _parse_dec(s: str, thousands: Optional[str]) -> Optional[Decimal]:
    s = s.strip()
    if thousands and thousands in s:
        intpart = s.split(".")[0].lstrip("+-")
        groups = intpart.split(thousands)
        if not (1 <= len(groups[0]) <= 3 and all(len(g) == 3 for g in groups[1:])):
            return None
        s = s.replace(thousands, "")
    if not DEC_RE.match(s):
        return None
    try:
        return Decimal(s)
    except InvalidOperation:  # pragma: no cover
        return None


def read_table(t: Dict[str, Any], tz) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    """Return (good rows, rejected rows, file facts). Raises Invalid for a broken file/header."""
    fd = os.open(t["path"], os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(fd, "rb") as fh:
        _need(stat.S_ISREG(os.fstat(fh.fileno()).st_mode), f"{t['file']}: not a regular file")
        raw = fh.read(MAX_FILE_BYTES + 1)
    _need(len(raw) <= MAX_FILE_BYTES, f"{t['file']}: larger than {MAX_FILE_BYTES} bytes")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise Invalid(f"{t['file']}: not UTF-8 (byte {exc.start})") from None
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=t["delimiter"], strict=True)
    try:
        header = next(reader)
    except StopIteration:
        raise Invalid(f"{t['file']}: empty file (no header)") from None
    except csv.Error as exc:
        raise Invalid(f"{t['file']}: unreadable header ({exc})") from None
    lower = {c.lower(): c for c in t["columns"]}
    names = []
    for h in header:
        k = h.strip().lower()
        names.append(t["aliases"].get(k) or lower.get(k) or h.strip())
    seen = [n for n in names if n in t["columns"]]
    dupe = sorted({n for n in seen if seen.count(n) > 1})
    _need(not dupe, f"{t['file']}: header maps more than one column to {dupe}")
    missing = [c for c in t["columns"] if c not in names]
    _need(not missing, f"{t['file']}: header lacks declared column(s) {missing} (schema drift; nothing reconciled)")
    idx = {c: names.index(c) for c in t["columns"]}
    extra = sorted(h.strip() for h, n in zip(header, names) if n not in t["columns"])
    good, rejected = [], []
    blank = 0
    line = 1
    while True:
        try:
            rec = next(reader)
        except StopIteration:
            break
        except csv.Error as exc:
            rejected.append({"file": t["file"], "line": reader.line_num, "reason": "malformed_csv", "detail": str(exc)[:80]})
            line = reader.line_num
            continue
        line = reader.line_num
        if not rec:
            blank += 1  # an empty line is not a record; counted, not hidden
            continue
        if len(good) + len(rejected) >= MAX_ROWS:
            raise Invalid(f"{t['file']}: more than {MAX_ROWS} rows")
        if len(rec) != len(header):
            rejected.append({"file": t["file"], "line": line, "reason": "field_count", "detail": f"{len(rec)} fields, header has {len(header)}"})
            continue
        row: Dict[str, Any] = {"_line": line}
        bad = None
        for c, ty in t["columns"].items():
            v = rec[idx[c]]
            if len(v) > MAX_FIELD:
                bad = ("field_too_long", c)
                break
            v = v.strip()
            if v in t["nulls"]:
                row[c] = None
                continue
            if ty == "str":
                row[c] = v.upper() if c in t["upper"] else v
            elif ty == "decimal":
                d = _parse_dec(v, t["thousands"])
                if d is None:
                    bad = ("bad_decimal", c)
                    break
                row[c] = d
            elif ty == "int":
                if not re.match(r"^[+-]?\d{1,18}$", v):
                    bad = ("bad_int", c)
                    break
                row[c] = int(v)
            else:
                tv = _parse_time(v, tz)
                if tv is None:
                    bad = ("bad_timestamp", c)
                    break
                row[c] = tv
                if not re.search(r"(Z|[+-]\d\d:?\d\d)$", v):
                    row.setdefault("_naive", []).append(c)
        if bad:
            rejected.append({"file": t["file"], "line": line, "reason": bad[0], "detail": bad[1]})
            continue
        good.append(row)
    return good, rejected, {"file": t["file"], "sha256": hashlib.sha256(raw).hexdigest(),
                            "data_rows": len(good) + len(rejected), "ignored_columns": extra,
                            "blank_lines_skipped": blank}


def _content(row: Dict[str, Any], cols) -> Tuple:
    return tuple((c, _canon(row.get(c))) for c in cols)


def _canon(v: Any) -> str:
    if v is None:
        return "\x00null"
    if isinstance(v, dt.datetime):
        return v.isoformat()
    if isinstance(v, Decimal):
        return format(v.normalize(), "f")  # 10.50 and 10.5 are the same value
    return str(v)


def _dedup(rows: List[Dict[str, Any]], key_cols: List[str], cols, policy) -> Tuple[Dict[Tuple, Dict[str, Any]], Dict[str, int], List[Dict[str, Any]]]:
    """Resolve duplicates on key_cols. Returns (kept by key, counts, dropped rows with reasons)."""
    groups: Dict[Tuple, List[Dict[str, Any]]] = {}
    for r in rows:
        groups.setdefault(tuple(_canon(r[c]) for c in key_cols), []).append(r)
    kept, dropped = {}, []
    n = {"exact_copies": 0, "superseded_versions": 0, "keys_unresolved": 0, "rows_unresolved": 0}
    for k in sorted(groups):
        g = groups[k]
        distinct: Dict[Tuple, Dict[str, Any]] = {}
        for r in sorted(g, key=lambda r: r["_line"]):
            sig = _content(r, cols)
            if sig in distinct:
                n["exact_copies"] += 1
                dropped.append(dict(r, _reason="duplicate_exact"))
            else:
                distinct[sig] = r
        vers = list(distinct.values())
        if len(vers) == 1:
            kept[k] = vers[0]
            continue
        mode, col = policy
        if mode == "latest":
            vals = [v[col] for v in vers]
            if any(x is None for x in vals):
                best = None
            else:
                top = max(vals)
                winners = [v for v in vers if v[col] == top]
                best = winners[0] if len(winners) == 1 else None
            if best is not None:
                kept[k] = best
                for v in vers:
                    if v is not best:
                        n["superseded_versions"] += 1
                        dropped.append(dict(v, _reason="duplicate_superseded"))
                continue
        n["keys_unresolved"] += 1
        n["rows_unresolved"] += len(vers)
        dropped.extend(dict(v, _reason="duplicate_conflict_unresolved") for v in vers)
    return kept, n, dropped


def _fmt(v: Any) -> Any:
    if isinstance(v, Decimal):
        return format(v, "f")
    if isinstance(v, dt.datetime):
        return v.isoformat()
    return v


def reconcile(contract_path: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]], Dict[str, Any]]:
    # 60 significant digits with Inexact trapped: a sum that would round raises instead of drifting.
    with localcontext(Context(prec=60, traps=[Inexact, InvalidOperation])):
        try:
            return _reconcile(contract_path)
        except Inexact:  # pragma: no cover - needs more than 5 million rows at the digit limit
            raise Invalid("a total would need rounding; refusing to report an inexact number") from None


def _reconcile(contract_path: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]], Dict[str, Any]]:
    C = load_contract(contract_path)
    F, Dm, tz = C["facts"], C["dimension"], C["tz"]
    rows, rejected, ffile = read_table(F, tz)
    excluded: List[Dict[str, Any]] = [dict(r) for r in rejected]
    cov = {"rows_read": ffile["data_rows"], "rejected": {}, "missing_required": {}, "late_after_as_of": 0,
           "excluded_status": 0, "outside_window": 0}
    for r in rejected:
        cov["rejected"][r["reason"]] = cov["rejected"].get(r["reason"], 0) + 1
    naive_ts = sum(1 for r in rows if r.get("_naive"))
    def missing(r, cols):
        miss = [c for c in cols if r.get(c) is None]
        if miss:
            cov["missing_required"][miss[0]] = cov["missing_required"].get(miss[0], 0) + 1
            excluded.append({"file": F["file"], "line": r["_line"], "reason": "missing_required", "detail": miss[0]})
        return bool(miss)

    # 1) rows without a grain cannot be versioned; rows loaded after as_of are not in this view
    known = []
    for r in rows:
        if missing(r, F["grain"]):
            continue
        if C["as_of"] is not None and r.get(F["loaded_at"]) is not None and r[F["loaded_at"]] > C["as_of"]:
            cov["late_after_as_of"] += 1
            excluded.append({"file": F["file"], "line": r["_line"], "reason": "late_after_as_of", "detail": F["loaded_at"]})
            continue
        known.append(r)
    # 2) one version per grain, BEFORE status/window: a newer "void" version cancels the order,
    #    and a newer version with a missing value is not papered over by an older one
    kept, dup, dropped = _dedup(known, F["grain"], list(F["columns"]), F["policy"])
    excluded += [{"file": F["file"], "line": r["_line"], "reason": r["_reason"], "detail": ",".join(F["grain"])} for r in dropped]
    # 3) the surviving version must be complete, wanted and inside the window
    stage = []
    for r in (kept[k] for k in sorted(kept)):
        if missing(r, F["required"]):
            continue
        stc, excl = F["status"]
        if stc and r.get(stc) in excl:
            cov["excluded_status"] += 1
            excluded.append({"file": F["file"], "line": r["_line"], "reason": "excluded_status", "detail": str(r[stc])})
            continue
        t = r.get(C["window"]["column"])
        if t is None or not (C["window"]["start"] <= t < C["window"]["end"]):
            cov["outside_window"] += 1
            excluded.append({"file": F["file"], "line": r["_line"], "reason": "outside_window" if t is not None else "missing_window_time",
                             "detail": C["window"]["column"]})
            continue
        stage.append(r)
    facts = stage
    cov["duplicates"] = dup
    cov["loaded_at_missing_included"] = sum(1 for r in facts if F["loaded_at"] and r.get(F["loaded_at"]) is None) if C["as_of"] else 0
    dim_info = None
    if Dm:
        drows, drej, dfile = read_table(Dm, tz)
        dmiss = [r for r in drows if any(r.get(c) is None for c in Dm["required"])]
        drows = [r for r in drows if not any(r.get(c) is None for c in Dm["required"])]
        dkept, ddup, ddropped = _dedup(drows, [Dm["key"]], list(Dm["columns"]), Dm["policy"])
        excluded += [{"file": Dm["file"], "line": r["_line"], "reason": "missing_required", "detail": "dimension"} for r in dmiss]
        excluded += [{"file": Dm["file"], "line": r["_line"], "reason": r["_reason"], "detail": Dm["key"]} for r in ddropped]
        ambiguous_keys = {r_key for r_key in {tuple([_canon(r[Dm["key"]])]) for r in ddropped if r["_reason"] == "duplicate_conflict_unresolved"}}
        join = {"matched": 0, "unmatched": 0, "ambiguous": 0, "fact_key_missing": 0}
        for r in facts:
            fk = r.get(Dm["fact_key"])
            if fk is None:
                join["fact_key_missing"] += 1
                state, src = UNMATCHED, None
            else:
                k = (_canon(fk),)
                if k in dkept:
                    state, src = "matched", dkept[k]
                elif k in ambiguous_keys:
                    state, src = AMBIGUOUS, None
                else:
                    state, src = UNMATCHED, None
            if state == "matched":
                join["matched"] += 1
            elif state == AMBIGUOUS:
                join["ambiguous"] += 1
            elif fk is not None:
                join["unmatched"] += 1
            for a in Dm["attributes"]:
                r[a] = (src.get(a) if src.get(a) is not None else "(null)") if src else state
        dim_info = {"file": dfile, "rows_read": dfile["data_rows"], "rejected": len(drej), "missing_required": len(dmiss),
                    "duplicates": ddup, "join": join, "fan_out_prevented": True}
        excluded += [dict(r) for r in drej]
    metrics = {}
    for m in C["metrics"]:
        groups: Dict[Tuple, Dict[str, Any]] = {}
        nulls = 0
        for r in facts:
            g = tuple(_canon(r.get(b)) if r.get(b) is not None else "(null)" for b in m["by"])
            v = r.get(m["column"])
            acc = groups.setdefault(g, {"rows": 0, "nulls": 0, "vals": []})
            acc["rows"] += 1
            if v is None:
                acc["nulls"] += 1
                nulls += 1
                continue
            acc["vals"].append(v)
        out = []
        for g in sorted(groups):
            acc = groups[g]
            vals = acc["vals"]
            if m["agg"] == "sum":
                val = _fmt(sum(vals, Decimal(0)) if vals else None)
            elif m["agg"] == "count":
                val = len(vals)
            elif m["agg"] == "count_distinct":
                val = len({_canon(x) for x in vals})
            elif m["agg"] == "min":
                val = _fmt(min(vals)) if vals else None
            else:
                val = _fmt(max(vals)) if vals else None
            out.append({"group": dict(zip(m["by"], g)), "value": val, "rows": acc["rows"], "null_values_skipped": acc["nulls"]})
        metrics[m["name"]] = {"agg": m["agg"], "column": m["column"], "by": m["by"], "groups": out, "null_values_skipped": nulls}
    controls = None
    if C["controls"]:
        controls = _controls(C, ffile, rows, rejected)
    accounted = (len(rejected) + sum(cov["missing_required"].values()) + cov["late_after_as_of"] + cov["excluded_status"]
                 + cov["outside_window"] + dup["exact_copies"] + dup["superseded_versions"] + dup["rows_unresolved"] + len(facts))
    cov["included"] = len(facts)
    cov["accounted"] = accounted
    cov["all_rows_accounted"] = accounted == cov["rows_read"]
    eligible = len(facts) + dup["rows_unresolved"] + sum(cov["missing_required"].values()) + len(rejected)
    cov["quality_coverage"] = f"{len(facts)}/{eligible}" if eligible else "0/0"
    naive = _naive(C, F, Dm, rows, rejected, drows if Dm else None)
    gaps = []
    for name, cond in (("rejected_rows", rejected), ("missing_required", cov["missing_required"]),
                       ("unresolved_duplicates", dup["rows_unresolved"]), ("late_rows", cov["late_after_as_of"]),
                       ("unmatched_or_missing_join_key", dim_info and (dim_info["join"]["unmatched"] or dim_info["join"]["fact_key_missing"])),
                       ("ambiguous_dimension_key", dim_info and dim_info["join"]["ambiguous"]),
                       ("control_mismatch", controls and not controls["match"]),
                       ("null_metric_values", any(m["null_values_skipped"] for m in metrics.values()))):
        if cond:
            gaps.append(name)
    quality_gaps = bool(gaps)
    notes = []
    if naive_ts:
        notes.append(f"{naive_ts} fact rows had timestamps without an offset; read as {C['tzname']} as the contract declares")
    if ffile["ignored_columns"]:
        notes.append(f"undeclared columns ignored: {ffile['ignored_columns']}")
    if cov["loaded_at_missing_included"]:
        notes.append(f"{cov['loaded_at_missing_included']} included rows have no {F['loaded_at']}; lateness could not be judged for them")
    if not cov["all_rows_accounted"]:  # pragma: no cover - defensive; would be a bug
        notes.append("BUG: some rows are not accounted for")
    report = {
        "schema": REPORT_SCHEMA, "contract_sha256": C["contract_sha256"], "inputs": [ffile] + ([dim_info["file"]] if dim_info else [])
        + ([controls["file_facts"]] if controls else []),
        "grain": F["grain"], "window": {"column": C["window"]["column"], "start": C["window"]["start"].isoformat(), "end": C["window"]["end"].isoformat()},
        "as_of": C["as_of"].isoformat() if C["as_of"] else None, "timezone_for_naive_times": C["tzname"],
        "status": "reconciled_with_gaps" if quality_gaps else "reconciled", "gaps": gaps,
        "metrics": metrics, "coverage": cov, "dimension": dim_info, "controls": controls, "naive_comparison": naive,
        "notes": notes,
        "execution": "local stdlib Python over the supplied CSV files; no warehouse, database or network was used",
        "imputation": "none: missing values are excluded and counted, never filled",
    }
    if controls:
        controls.pop("file_facts", None)
    return report, sorted(excluded, key=lambda e: (e["file"], e["line"], e["reason"])), C


def _controls(C, ffile, rows, rejected) -> Dict[str, Any]:
    ct = C["controls"]
    raw = ct["path"].read_bytes()
    try:
        text = raw.decode("utf-8-sig")
        recs = list(csv.DictReader(io.StringIO(text, newline="")))
    except (UnicodeDecodeError, csv.Error) as exc:
        raise Invalid(f"{ct['file']}: unreadable control file ({exc.__class__.__name__})") from None
    mine = [r for r in recs if (r.get("file") or "").strip() == C["facts"]["file"]]
    _need(len(mine) == 1, f"{ct['file']}: expected exactly one control row for {C['facts']['file']}")
    r = mine[0]
    try:
        exp_rows = int((r.get("rows") or "").strip())
    except ValueError:
        raise Invalid(f"{ct['file']}: rows must be an integer") from None
    out = {"file": ct["file"], "expected_rows": exp_rows, "actual_rows": ffile["data_rows"]}
    ok = exp_rows == ffile["data_rows"]
    if ct["sum_column"]:
        exp = _parse_dec((r.get("sum") or "").strip(), None)
        _need(exp is not None, f"{ct['file']}: sum must be a plain decimal")
        act = sum((x[ct["sum_column"]] for x in rows if x.get(ct["sum_column"]) is not None), Decimal(0))
        out.update(expected_sum=_fmt(exp), actual_sum_of_parsed=_fmt(act), unparsed_rows=len(rejected))
        ok = ok and exp == act and not rejected
    out["match"] = ok
    out["file_facts"] = {"file": ct["file"], "sha256": hashlib.sha256(raw).hexdigest()}
    return out


def _naive(C, F, Dm, rows, rejected, drows) -> Dict[str, Any]:
    """What a plain SUM / JOIN would report, for contrast only. Never used as a result."""
    amount = next((m["column"] for m in C["metrics"] if m["agg"] == "sum"), None)
    if amount is None:
        return {"note": "no sum metric to contrast"}
    cur = next((c for m in C["metrics"] for c in m["by"] if c in F["columns"] and F["columns"][c] == "str"), None)
    def key(r):
        return _canon(r.get(cur)) if cur else "(all)"
    plain: Dict[str, Decimal] = {}
    for r in rows:
        if r.get(amount) is not None:
            plain[key(r)] = plain.get(key(r), Decimal(0)) + r[amount]
    out = {"column": amount, "split_by": cur, "sum_every_parsed_row": {k: _fmt(v) for k, v in sorted(plain.items())},
           "rows_in_that_sum": sum(1 for r in rows if r.get(amount) is not None)}
    if Dm and drows is not None:
        mult: Dict[str, int] = {}
        for d in drows:
            mult[_canon(d[Dm["key"]])] = mult.get(_canon(d[Dm["key"]]), 0) + 1
        joined: Dict[str, Decimal] = {}
        n = 0
        for r in rows:
            k = r.get(Dm["fact_key"])
            m = mult.get(_canon(k), 0) if k is not None else 0
            if r.get(amount) is not None and m:
                joined[key(r)] = joined.get(key(r), Decimal(0)) + r[amount] * m
                n += m
        out["sum_after_inner_join"] = {k: _fmt(v) for k, v in sorted(joined.items())}
        out["rows_after_inner_join"] = n
    return out


# -- output -------------------------------------------------------------------------

def render(rep: Dict[str, Any]) -> str:
    c = rep["coverage"]
    lines = [f"reconcile: {rep['status']}  (grain {', '.join(rep['grain'])}; window {rep['window']['start']} .. {rep['window']['end']}"
             + (f"; as of {rep['as_of']}" if rep["as_of"] else "") + ")"]
    for name, m in rep["metrics"].items():
        for g in m["groups"]:
            gs = ", ".join(f"{k}={v}" for k, v in g["group"].items()) or "all"
            lines.append(f"  {name} [{gs}] = {g['value']}  ({g['rows']} rows" + (f", {g['null_values_skipped']} null skipped" if g["null_values_skipped"] else "") + ")")
    lines.append(f"  rows read {c['rows_read']}, included {c['included']}, all accounted: {'yes' if c['all_rows_accounted'] else 'NO'}")
    d = c["duplicates"]
    lines.append(f"  excluded: rejected {sum(c['rejected'].values())} {dict(sorted(c['rejected'].items())) or ''}, missing required {sum(c['missing_required'].values())}, "
                 f"late {c['late_after_as_of']}, status {c['excluded_status']}, outside window {c['outside_window']}, "
                 f"exact copies {d['exact_copies']}, superseded {d['superseded_versions']}, unresolved {d['rows_unresolved']} rows/{d['keys_unresolved']} keys")
    if rep["dimension"]:
        j = rep["dimension"]["join"]
        lines.append(f"  join: matched {j['matched']}, unmatched {j['unmatched']}, ambiguous {j['ambiguous']}, key missing {j['fact_key_missing']}; "
                     f"dimension copies {rep['dimension']['duplicates']['exact_copies']}, conflicting keys {rep['dimension']['duplicates']['keys_unresolved']} (no fan-out)")
    if rep["controls"]:
        k = rep["controls"]
        lines.append(f"  control {k['file']}: rows {k['actual_rows']}/{k['expected_rows']}" + (f", sum {k['actual_sum_of_parsed']}/{k['expected_sum']}" if "expected_sum" in k else "")
                     + f" -> {'match' if k['match'] else 'MISMATCH'}")
    n = rep["naive_comparison"]
    if "sum_every_parsed_row" in n:
        lines.append(f"  naive SUM({n['column']}) over every parsed row: {n['sum_every_parsed_row']} ({n['rows_in_that_sum']} rows) - not a result")
        if "sum_after_inner_join" in n:
            lines.append(f"  naive SUM after an inner join: {n['sum_after_inner_join']} ({n['rows_after_inner_join']} rows) - not a result")
    lines += [f"  note: {x}" for x in rep["notes"]]
    lines.append(f"  {rep['execution']}")
    return "\n".join(lines) + "\n"


def _check_target(out: Path, protect: List[Path]) -> Path:
    out = Path(os.path.abspath(out))
    _need(not out.is_symlink() and (not out.exists() or out.is_file()), f"{out.name}: exists and is not a regular file; not replaced")
    _need(out.parent.is_dir(), f"{out.name}: its folder does not exist")
    for p in protect:
        _need(not (out.exists() and os.path.samefile(out, p)), f"{out.name}: would overwrite an input")
    return out


def _write_atomic(out: Path, data: bytes) -> None:
    tmp = out.parent / f".{out.name}.{secrets.token_hex(6)}.tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o644)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, out)
    except BaseException:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="csv_reconcile.py", description="Reconciled metrics from dirty CSV files.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("reconcile", help="reconcile the files named by a contract")
    r.add_argument("contract")
    r.add_argument("--json", action="store_true")
    r.add_argument("--out", help="write the JSON report here (atomic)")
    r.add_argument("--rejects", help="write every excluded row (file, line, reason) as CSV here (atomic)")
    a = ap.parse_args(argv)
    try:
        rep, excluded, C = reconcile(a.contract)
        data = (json.dumps(rep, indent=2, sort_keys=True) + "\n").encode("utf-8")
        protect = [Path(a.contract), C["facts"]["path"]] + ([C["dimension"]["path"]] if C["dimension"] else []) + ([C["controls"]["path"]] if C["controls"] else [])
        targets = []
        if a.rejects:
            buf = io.StringIO()
            w = csv.writer(buf, lineterminator="\n")
            w.writerow(["file", "line", "reason", "detail"])
            for e in excluded:
                w.writerow([e["file"], e["line"], e["reason"], e.get("detail", "")])
            targets.append((_check_target(Path(a.rejects), protect), buf.getvalue().encode("utf-8")))
        if a.out:
            targets.append((_check_target(Path(a.out), protect), data))
        _need(len({t for t, _ in targets}) == len(targets), "--out and --rejects name the same file")
        for t, payload in targets:  # every target checked before anything is written
            _write_atomic(t, payload)
    except OSError as exc:
        exc = Invalid(f"file error: {exc.strerror or exc.__class__.__name__}")
        sys.stdout.write(json.dumps({"schema": REPORT_SCHEMA, "status": "invalid", "error": str(exc)}, sort_keys=True) + "\n"
                         if a.json else f"invalid: {exc}\n")
        return 2
    except Invalid as exc:
        sys.stdout.write(json.dumps({"schema": REPORT_SCHEMA, "status": "invalid", "error": str(exc)}, sort_keys=True) + "\n"
                         if a.json else f"invalid: {exc}\nnothing written\n")
        return 2
    sys.stdout.write(data.decode("utf-8") if a.json else render(rep))
    return 1 if rep["status"] == "reconciled_with_gaps" else 0


if __name__ == "__main__":
    sys.exit(main())
