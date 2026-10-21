#!/usr/bin/env python3
"""Product choice from conflicting evidence (G33): ICP, dimensions, sourced claims, contrary evidence, ranges.

Reads one decision package (JSON, schema solaris.evidence-decision/1): the question, owner, as_of date and
ideal customer profile (ICP); the options; weighted comparison dimensions; the sources (interview transcripts,
saved snapshots of external pages, or a G13 reconciled metric); and claims, each scoring one option on one
dimension from one source. The tool:

- checks every claim against its source: the quote must appear in the pinned snapshot (sha256), a number in a
  claim must equal a whole number stated in its quote (18 does not match 18,000), a G13 metric claim must equal a rerun of the G13 reconciliation, and a score
  derived from a metric scale must match; any failure blocks the decision (no fabricated evidence);
- excludes claims about another segment than the ICP, and mutable external claims older than their max age
  at as_of (listed under verify_before_use); G13 metrics with quality gaps count at low confidence only;
- scores each option per dimension as a confidence-weighted mean with the full range of the evidence, treats a
  dimension with no evidence as unknown (0 to 5, never 0), lists contrary evidence (claims on the other side of
  the scale midpoint from the cell mean) and conflicts;
- names a preferred option only when its lowest possible total beats every other option's highest possible
  total; otherwise it reports no robust choice and the cells whose evidence would decide it.

It never estimates market size or adoption: numbers come only from quoted sources or G13. Exact decimals.

Usage:
  evidence_decision.py decide PACKAGE [--json] [--out FILE]
  evidence_decision.py verify RESULT PACKAGE
Exit codes: 0 a robust preferred option; 1 no robust choice, or blocked by evidence findings (listed);
2 invalid package, nothing written. verify: 0 identical, 1 different, 2 invalid. Python 3.9+, stdlib only,
local files only; nothing is fetched, sent or published.
"""
import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import os
import re
import sys
import tempfile
from decimal import Decimal, InvalidOperation
from pathlib import Path

SCHEMA = "solaris.evidence-decision/1"
REPORT = "solaris.evidence-decision-report/1"
ID = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,63}$")
SHA = re.compile(r"^[0-9a-f]{64}$")
CONF = {"low": Decimal(1), "medium": Decimal(2), "high": Decimal(3)}
KINDS = ("interview", "external", "g13")
LO, HI, MID = Decimal(0), Decimal(5), Decimal("2.5")
G13 = Path(__file__).resolve().parents[2] / "data" / "data-engineer" / "csv_reconcile.py"
NUM = re.compile(r"\d+(?:[.,]\d+)*%?")
# in a quote a percent sign may follow a space ("18 %", French and German style); it still makes the number a percent
QNUM = re.compile(r"\d+(?:[.,]\d+)*(?:[ \u00a0\u202f]?%)?")


def _num(tok):
    """A numeric token as (Decimal, is_percent); thousands commas dropped. None if not a plain number."""
    tok = tok.strip()
    if not NUM.fullmatch(tok):
        return None
    pct = tok.endswith("%")
    body = tok.rstrip("%")
    if "," in body and "." not in body and not re.fullmatch(r"\d{1,3}(?:,\d{3})+", body):
        return None  # "40,0" is not a thousands-grouped number; refuse rather than guess
    try:
        return Decimal(body.replace(",", "")), pct
    except InvalidOperation:
        return None


def _value_in_quote(value, quote):
    """A numeric value must equal a whole number the quote states (18 never matches 18,000; 4 never 40).
    Values the scorer would read as a number but that are not plain numbers (1,5, +18, -5) never match.
    Other non-numeric values keep the substring rule."""
    want = _num(value)
    if want is None:
        try:
            Decimal(value.replace(",", "").rstrip("%"))
        except (InvalidOperation, AttributeError):
            return value in quote
        # the scorer would read it as a number (1,5 / +18 / -5) but it is not a plain number: a substring match
        # could be a fragment of a larger number, so it never matches (fails closed)
        return False
    return any(_num(re.sub(r"[ \u00a0\u202f]%$", "%", m.group(0))) == want for m in QNUM.finditer(quote))


class Invalid(Exception):
    pass


def _str(d, k, w):
    v = d.get(k) if isinstance(d, dict) else None
    if not isinstance(v, str) or not v.strip():
        raise Invalid("%s.%s is required (non-empty text)" % (w, k))
    return v


def _date(v, w):
    try:
        return dt.date.fromisoformat(v) if isinstance(v, str) else None
    except ValueError:
        return None


def _need_date(v, w):
    d = _date(v, w)
    if d is None:
        raise Invalid("%s must be a YYYY-MM-DD date" % w)
    return d


def _dec(v, w, lo=None, hi=None):
    if not isinstance(v, str):
        raise Invalid("%s must be a decimal string" % w)
    try:
        d = Decimal(v)
    except InvalidOperation:
        raise Invalid("%s is not a decimal: %r" % (w, v))
    if not d.is_finite() or (lo is not None and d < lo) or (hi is not None and d > hi):
        raise Invalid("%s must be between %s and %s" % (w, lo, hi))
    return d


def _ids(lst, w, seen):
    if not isinstance(lst, list) or not lst:
        raise Invalid("%s must be a non-empty list" % w)
    out = {}
    for i, x in enumerate(lst):
        k = x.get("id") if isinstance(x, dict) else None
        if not isinstance(k, str) or not ID.match(k):
            raise Invalid("%s[%d].id must be a short identifier" % (w, i))
        if k in seen:
            raise Invalid("duplicate id %r" % k)
        seen.add(k); out[k] = x
    return out


def _norm(s):
    return " ".join(s.split()).casefold()


def load(path):
    try:
        raw = Path(path).read_bytes()
        d = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as ex:
        raise Invalid("package unreadable: %s" % ex.__class__.__name__)
    if not isinstance(d, dict) or d.get("schema") != SCHEMA:
        raise Invalid("package schema must be %s" % SCHEMA)
    base = Path(path).resolve().parent
    dec = d.get("decision")
    for k in ("question", "owner", "as_of"):
        _str(dec, k, "decision")
    as_of = _need_date(dec["as_of"], "decision.as_of")
    icp = dec.get("icp")
    _str(icp, "segment", "decision.icp"); _str(icp, "definition", "decision.icp")
    seen = set()
    P = {"d": d, "base": base, "as_of": as_of, "icp": icp["segment"], "sha": hashlib.sha256(raw).hexdigest()}
    P["options"] = _ids(d.get("options"), "options", seen)
    P["dims"] = _ids(d.get("dimensions"), "dimensions", seen)
    tot = Decimal(0)
    for k, x in P["dims"].items():
        x["_w"] = _dec(x.get("weight"), "dimensions.%s.weight" % k, Decimal(0), Decimal(1))
        tot += x["_w"]
        if "quantity" in x and not isinstance(x["quantity"], bool):
            raise Invalid("dimensions.%s.quantity must be true or false" % k)
        sc = x.get("metric_scale")
        if sc is not None:
            th = sc.get("thresholds") if isinstance(sc, dict) else None
            if not isinstance(th, list) or len(th) != 5:
                raise Invalid("dimensions.%s.metric_scale.thresholds must list 5 ascending values" % k)
            x["_th"] = [_dec(t, "dimensions.%s.metric_scale" % k) for t in th]
            if x["_th"] != sorted(x["_th"]) or len(set(x["_th"])) != 5:
                raise Invalid("dimensions.%s.metric_scale.thresholds must be strictly ascending" % k)
    if tot != 1:
        raise Invalid("dimension weights must sum to exactly 1 (they sum to %s)" % tot)
    P["sources"] = _ids(d.get("sources"), "sources", seen)
    for k, s in P["sources"].items():
        w = "sources.%s" % k
        if s.get("kind") not in KINDS:
            raise Invalid("%s.kind must be one of %s" % (w, ", ".join(KINDS)))
        _str(s, "title", w)
        if s["kind"] == "g13":
            _str(s, "contract", w); _str(s, "metric", w)
            if not isinstance(s.get("group", {}), dict):
                raise Invalid("%s.group must be an object" % w)
            continue
        snap = s.get("snapshot")
        if not isinstance(snap, dict) or not isinstance(snap.get("sha256"), str) or not SHA.match(snap["sha256"]):
            raise Invalid("%s.snapshot needs path and sha256" % w)
        rel = snap.get("path")
        if not isinstance(rel, str) or not rel or os.path.isabs(rel) or ".." in Path(rel).parts:
            raise Invalid("%s.snapshot.path must be relative inside the package folder" % w)
        got = _need_date(s.get("retrieved_at"), w + ".retrieved_at")
        if got > as_of:
            raise Invalid("%s was retrieved after decision.as_of" % w)
        s["_got"] = got
        if s["kind"] == "external":
            _str(s, "url", w)
            if not isinstance(s.get("mutable"), bool):
                raise Invalid("%s.mutable must be true or false" % w)
            if s["mutable"]:
                m = s.get("max_age_days")
                if type(m) is not int or m < 0:
                    raise Invalid("%s.max_age_days must be a whole number for a mutable source" % w)
    P["claims"] = _ids(d.get("claims"), "claims", seen)
    for k, c in P["claims"].items():
        w = "claims.%s" % k
        if c.get("option") not in P["options"]:
            raise Invalid("%s names unknown option %r" % (w, c.get("option")))
        if c.get("dimension") not in P["dims"]:
            raise Invalid("%s names unknown dimension %r" % (w, c.get("dimension")))
        _str(c, "segment", w)
        if c.get("confidence") not in CONF:
            raise Invalid("%s.confidence must be low, medium or high" % w)
        if c.get("score") is not None:
            c["_score"] = _dec(c["score"], w + ".score", LO, HI)
        if c.get("value") is not None and not isinstance(c["value"], str):
            raise Invalid("%s.value must be text exactly as the source states it" % w)
    for bad in ("tam", "sam", "som", "market_size", "adoption", "adoption_rate", "assumed_adoption"):
        if bad in d:
            raise Invalid("top-level %r is not accepted: market size and adoption come only from sourced claims" % bad)
    return P


def _g13(P, s, cache):
    key = (s["contract"],)
    if key not in cache:
        if not G13.is_file():
            cache[key] = (None, "the G13 reconciliation tool is not present")
        else:
            sys.dont_write_bytecode = True
            spec = importlib.util.spec_from_file_location("g13_csv_reconcile", str(G13))
            m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
            try:
                rep = m.reconcile(str(P["base"] / s["contract"]))[0]
                cache[key] = (rep, None)
            except Exception as ex:  # G13 refuses invalid contracts with its own Invalid
                cache[key] = (None, "G13 reconciliation refused: %s" % ex)
    rep, err = cache[key]
    if err:
        return None, None, err
    met = rep.get("metrics", {}).get(s["metric"])
    if met is None:
        return None, None, "G13 report has no metric %r" % s["metric"]
    grp = [g for g in met["groups"] if g["group"] == s.get("group", {})]
    if len(grp) != 1:
        return None, None, "G13 metric %r has no group %s" % (s["metric"], json.dumps(s.get("group", {}), sort_keys=True))
    return str(grp[0]["value"]), rep.get("status"), None


def decide(path):
    P = load(path)
    F, verify, excluded, used = [], [], [], []
    cache, snaps = {}, {}
    for k, c in sorted(P["claims"].items()):
        s = P["sources"].get(c.get("source"))
        dim = P["dims"][c["dimension"]]
        conf = c["confidence"]
        if s is None:
            F.append({"code": "unknown_source", "ref": k, "detail": "source %r is not listed" % c.get("source")}); continue
        if s["kind"] == "g13":
            val, status, err = _g13(P, s, cache)
            if err:
                F.append({"code": "g13_unavailable", "ref": k, "detail": err}); continue
            if c.get("value") != val:
                F.append({"code": "g13_value_mismatch", "ref": k, "detail": "claim says %r, G13 rerun gives %r" % (c.get("value"), val)}); continue
            if status != "reconciled":
                conf = "low"
            if c["segment"] != P["icp"]:
                excluded.append({"claim": k, "reason": "segment %s is outside the ICP %s" % (c["segment"], P["icp"])}); continue
        else:
            if s["id"] not in snaps:
                p = P["base"] / s["snapshot"]["path"]
                try:
                    b = p.read_bytes()
                    snaps[s["id"]] = (hashlib.sha256(b).hexdigest(), b.decode("utf-8", "replace"))
                except OSError:
                    snaps[s["id"]] = (None, "")
            got, text = snaps[s["id"]]
            if got != s["snapshot"]["sha256"]:
                F.append({"code": "snapshot_mismatch", "ref": k, "detail": "snapshot of %s is %s" % (s["id"], "missing" if got is None else "changed")}); continue
            q = c.get("quote")
            if not isinstance(q, str) or not q.strip() or _norm(q) not in _norm(text):
                F.append({"code": "quote_not_in_source", "ref": k, "detail": "quote not found in %s" % s["id"]}); continue
            if c.get("value") is not None and not _value_in_quote(c["value"], q):
                F.append({"code": "value_not_in_quote", "ref": k, "detail": "value %r is not a whole number stated in the quote" % c["value"]}); continue
            if c["segment"] != P["icp"]:
                excluded.append({"claim": k, "reason": "segment %s is outside the ICP %s" % (c["segment"], P["icp"])}); continue
            if c.get("value") is None and dim.get("metric_scale") is not None:
                F.append({"code": "value_not_in_quote", "ref": k, "detail": "dimension %s is scored from a stated value" % dim["id"]}); continue
            if dim.get("quantity") is True:
                # a quantity dimension is scored only from a number the source states: the claim's value, found in the quote
                if c.get("value") is None:
                    F.append({"code": "value_not_in_quote", "ref": k, "detail": "quantity claim must state the number it uses%s"
                              % ("" if NUM.search(q) else "; the quote states no number")}); continue
                if not NUM.search(c["value"]):
                    F.append({"code": "value_not_in_quote", "ref": k, "detail": "quantity value %r is not a number" % c["value"]}); continue
            if s["kind"] == "external" and s["mutable"] and (P["as_of"] - s["_got"]).days > s["max_age_days"]:
                verify.append({"claim": k, "source": s["id"], "url": s["url"], "retrieved_at": str(s["_got"]),
                               "age_days": (P["as_of"] - s["_got"]).days, "max_age_days": s["max_age_days"]})
                excluded.append({"claim": k, "reason": "stale mutable source; verify before use"}); continue
        if dim.get("metric_scale") is not None:
            try:
                v = Decimal(c["value"].replace(",", "").rstrip("%"))
            except (InvalidOperation, AttributeError):
                F.append({"code": "value_not_in_quote", "ref": k, "detail": "value is not a number"}); continue
            score = Decimal(sum(1 for t in dim["_th"] if v >= t))
            if c.get("_score") is not None and c["_score"] != score:
                F.append({"code": "stated_score_mismatch", "ref": k, "detail": "stated %s, the metric scale gives %s" % (c["_score"], score)}); continue
        else:
            if c.get("_score") is None:
                F.append({"code": "unscored_claim", "ref": k, "detail": "no score and no metric scale"}); continue
            score = c["_score"]
        used.append({"claim": k, "option": c["option"], "dimension": c["dimension"], "score": score, "confidence": conf,
                     "source": s["id"]})
    cells, contrary = {}, []
    for o in sorted(P["options"]):
        for dk in sorted(P["dims"]):
            ev = [u for u in used if u["option"] == o and u["dimension"] == dk]
            if not ev:
                cells[(o, dk)] = None; continue
            wsum = sum(CONF[u["confidence"]] for u in ev)
            mean = sum(CONF[u["confidence"]] * u["score"] for u in ev) / wsum
            lo, hi = min(u["score"] for u in ev), max(u["score"] for u in ev)
            cells[(o, dk)] = {"mean": mean, "low": lo, "high": hi, "claims": [u["claim"] for u in ev], "conflict": hi - lo >= 2}
            for u in ev:
                if (u["score"] - MID) * (mean - MID) < 0:
                    contrary.append({"option": o, "dimension": dk, "claim": u["claim"], "score": str(u["score"]),
                                     "against": "cell mean %s" % _q(mean)})
    totals = {}
    for o in sorted(P["options"]):
        low = high = point = Decimal(0); unknown = []
        for dk, dm in sorted(P["dims"].items()):
            c = cells[(o, dk)]
            if c is None:
                unknown.append(dk); high += dm["_w"] * HI
            else:
                low += dm["_w"] * c["low"]; high += dm["_w"] * c["high"]; point += dm["_w"] * c["mean"]
        totals[o] = {"low": low, "high": high, "point": None if unknown else point, "unknown_dimensions": unknown}
    pref = [o for o in totals if all(totals[o]["low"] > totals[x]["high"] for x in totals if x != o)]
    deciding = []
    if F:
        status = "blocked_evidence"
    elif pref:
        status = "preferred"
    else:
        status = "no_robust_choice"
        for dk, dm in sorted(P["dims"].items()):
            for o in sorted(P["options"]):
                c = cells[(o, dk)]
                width = HI - LO if c is None else c["high"] - c["low"]
                if width > 0 and dm["_w"] > 0:
                    deciding.append({"option": o, "dimension": dk, "weighted_range": _q(dm["_w"] * width),
                                     "why": "no evidence" if c is None else "evidence spans %s to %s" % (c["low"], c["high"])})
        deciding.sort(key=lambda x: (-Decimal(x["weighted_range"]), x["option"], x["dimension"]))
    rep = {"schema": REPORT, "status": status, "question": P["d"]["decision"]["question"], "owner": P["d"]["decision"]["owner"],
           "as_of": str(P["as_of"]), "icp": {"segment": P["icp"], "definition": P["d"]["decision"]["icp"]["definition"]},
           "package_sha256": P["sha"], "preferred": pref[0] if pref and not F else None,
           "totals": {o: {"low": _q(t["low"]), "high": _q(t["high"]), "point": None if t["point"] is None else _q(t["point"]),
                          "unknown_dimensions": t["unknown_dimensions"]} for o, t in totals.items()},
           "cells": [{"option": o, "dimension": dk, **({"evidence": "none"} if c is None else
                     {"mean": _q(c["mean"]), "low": str(c["low"]), "high": str(c["high"]), "claims": c["claims"], "conflict": c["conflict"]})}
                     for (o, dk), c in sorted(cells.items())],
           "contrary_evidence": contrary, "excluded": excluded, "verify_before_use": verify,
           "findings": sorted(F, key=lambda f: (f["code"], f["ref"])), "deciding_evidence": deciding[:10],
           "used_claims": len(used), "claim_confidence": {u["claim"]: u["confidence"] for u in used}, "estimates_made": "none: no market size or adoption figure is computed",
           "certainty": "ranges come only from the cited evidence; unknown dimensions span the whole scale. The owner decides."}
    return rep, (0 if status == "preferred" else 1)


def _q(d):
    return str(d.quantize(Decimal("0.0001")))


def _write_atomic(out, data, pkg):
    out = Path(out)
    if out.resolve() == Path(pkg).resolve():
        raise Invalid("--out would overwrite the package")
    fd, tmp = tempfile.mkstemp(prefix=".g33-", dir=str(out.resolve().parent))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data); f.flush(); os.fsync(f.fileno())
        os.replace(tmp, str(out))
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def render(r):
    L = ["%s: %s%s (owner %s, ICP %s)" % (r["question"], r["status"].upper(), " " + r["preferred"] if r["preferred"] else "", r["owner"], r["icp"]["segment"])]
    for o, t in r["totals"].items():
        L.append("  %s total %s to %s%s" % (o, t["low"], t["high"], "; unknown: " + ", ".join(t["unknown_dimensions"]) if t["unknown_dimensions"] else ""))
    for c in r["contrary_evidence"]:
        L.append("  CONTRARY %s on %s: %s scores %s against %s" % (c["option"], c["dimension"], c["claim"], c["score"], c["against"]))
    for v in r["verify_before_use"]:
        L.append("  VERIFY %s (%s) is %d days old, max %d" % (v["source"], v["url"], v["age_days"], v["max_age_days"]))
    for x in r["deciding_evidence"]:
        L.append("  DECIDE-BY %s on %s (weighted range %s, %s)" % (x["option"], x["dimension"], x["weighted_range"], x["why"]))
    for f in r["findings"]:
        L.append("  FINDING %s %s: %s" % (f["code"], f["ref"], f["detail"]))
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="evidence_decision.py", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd")
    d = sub.add_parser("decide"); d.add_argument("package"); d.add_argument("--json", action="store_true"); d.add_argument("--out")
    v = sub.add_parser("verify"); v.add_argument("result"); v.add_argument("package")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "decide":
            rep, code = decide(a.package)
            data = (json.dumps(rep, indent=1, sort_keys=True) + "\n").encode()
            if a.out:
                _write_atomic(a.out, data, a.package)
            print(data.decode().rstrip() if a.json else render(rep))
            return code
        if a.cmd == "verify":
            try:
                stored = json.loads(Path(a.result).read_text(encoding="utf-8"))
            except (OSError, ValueError, UnicodeDecodeError) as ex:
                raise Invalid("cannot read result: %s" % ex.__class__.__name__)
            rep, _ = decide(a.package)
            fresh = json.loads(json.dumps(rep))
            diffs = sorted(k for k in set(fresh) | set(stored if isinstance(stored, dict) else {}) if not isinstance(stored, dict) or fresh.get(k) != stored.get(k))
            if diffs:
                print("DIFFERENT: %s do not match a rerun" % ", ".join(diffs)); return 1
            print("IDENTICAL: the stored result matches a rerun (package sha256 %s)" % rep["package_sha256"]); return 0
        ap.print_help(); return 2
    except Invalid as ex:
        print("INVALID: %s. Nothing was written." % ex, file=sys.stderr)
        return 2
    except RecursionError:
        print("INVALID: input nests too deeply. Nothing was written.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
