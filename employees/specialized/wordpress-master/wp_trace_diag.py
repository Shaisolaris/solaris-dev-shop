#!/usr/bin/env python3
"""Offline WordPress diagnosis from a captured trace and config bundle (G23).

Scope: this tool reads a JSON bundle that describes one WordPress site's configuration and some
recorded requests (queries, hook timings, PHP error log lines, plugin bisect runs). It never runs PHP,
WordPress, WP-CLI or a database, and never connects anywhere. The bundles shipped with it are
SYNTHETIC fixtures; a report on them says so (`evidence_scope`) and is not evidence about any real site.
The field names follow what Query Monitor / SAVEQUERIES, `wp profile`, the PHP error log, wp-config.php
and `wp option list --autoload=on` expose, so a real capture can be converted into a bundle by hand.

Commands
  diagnose BUNDLE.json [--slow-ms 50] [--repeat 10] [--slow-hook-ms 100] [--json] [--out R.json]
      Localize plugin conflicts, slow and repeated queries, slow hook callbacks and configuration faults.
  compare BEFORE.json AFTER.json [--json] [--out R.json]
      Claim a speedup only when both bundles hold the same measurement set (same site, environment,
      stack, measurement procedure and the same URLs with the same sample counts, at least 5 each).

Exit codes: 0 healthy (diagnose) or comparable (compare), 1 faults found, 2 invalid input or invocation
(nothing written), 3 not comparable (no speedup claimed). Python 3.9+, standard library only.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import secrets
import statistics
import sys
from itertools import combinations
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

TOOL_VERSION = "1.0.0"
BUNDLE_SCHEMA = "solaris.wp-trace/1"
REPORT_SCHEMA = "solaris.wp-diagnosis/1"
COMPARE_SCHEMA = "solaris.wp-compare/1"
MAX_FILE = 64 * 1024 * 1024
MAX_REQUESTS = 20000
MAX_QUERIES = 2_000_000
MAX_LIST = 10000
MAX_BISECT_PLUGINS = 200
AUTOLOAD_WARN = 800_000           # WordPress 6.6 Site Health warns above 800 KB of autoloaded options
MEMORY_WARN = 0.9                 # peak memory at 90% of WP_MEMORY_LIMIT
MIN_SAMPLES = 5
ENVIRONMENTS = ("production", "staging", "local")
SECRET_RE = re.compile(r"(^DB_|PASSWORD|_KEY|_SALT|SECRET|TOKEN|NONCE)", re.I)
CONST_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,99}(/[A-Za-z0-9._-]{1,100}\.php)?$")
COMPONENT_RE = re.compile(r"^(core|unknown|(plugin|mu-plugin|theme):[a-z0-9][a-z0-9._-]{0,99})$")


class Invalid(Exception):
    pass


# -- input --------------------------------------------------------------------------------

def _no_dupes(pairs):
    out = {}
    for k, v in pairs:
        if k in out:
            raise ValueError(f"duplicate key {k!r}")
        out[k] = v
    return out


def _no_const(name):
    raise ValueError(f"{name} is not a number")


def _num(v: Any, where: str, lo: float = 0.0, hi: float = 1e12) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not lo <= v <= hi:
        raise Invalid(f"{where}: needs a number from {lo:g} to {hi:g}")
    return float(v)


def _str(v: Any, where: str, n: int) -> str:
    if not isinstance(v, str) or len(v) > n:
        raise Invalid(f"{where}: needs text of at most {n} characters")
    return v


def _list(v: Any, where: str, n: int = MAX_LIST) -> list:
    if not isinstance(v, list) or len(v) > n:
        raise Invalid(f"{where}: needs a list of at most {n} items")
    return v


def _obj(v: Any, where: str, allowed: set, required: set = frozenset()) -> dict:
    if not isinstance(v, dict):
        raise Invalid(f"{where}: needs an object")
    extra = set(v) - allowed
    if extra:
        raise Invalid(f"{where}: unknown field {sorted(extra)[0]!r}")
    missing = required - set(v)
    if missing:
        raise Invalid(f"{where}: missing field {sorted(missing)[0]!r}")
    return v


def _component(v: Any, where: str) -> str:
    if v is None:
        return "unknown"
    s = _str(v, where, 128)
    if not COMPONENT_RE.match(s):
        raise Invalid(f"{where}: component must be core, unknown, plugin:<slug>, mu-plugin:<slug> or theme:<slug>")
    return s


def load_bundle(path: Path) -> Dict[str, Any]:
    try:
        if path.is_symlink() or not path.is_file():
            raise Invalid(f"{path.name}: not a regular file")
        if path.stat().st_size > MAX_FILE:
            raise Invalid(f"{path.name}: larger than {MAX_FILE // (1024 * 1024)} MiB")
        text = path.read_bytes().decode("utf-8")
    except OSError as exc:
        raise Invalid(f"{path.name}: cannot read ({exc.strerror})") from None
    except UnicodeDecodeError:
        raise Invalid(f"{path.name}: not UTF-8") from None
    try:
        b = json.loads(text, object_pairs_hook=_no_dupes, parse_constant=_no_const)
    except RecursionError:
        raise Invalid(f"{path.name}: nested too deeply") from None
    except ValueError as exc:
        raise Invalid(f"{path.name}: not valid JSON ({str(exc)[:80]})") from None
    return check_bundle(b, path.name)


def check_bundle(b: Any, name: str) -> Dict[str, Any]:
    top = {"schema", "site", "environment", "source", "env", "measurement", "wp_config", "dropins", "active_plugins",
           "autoload_bytes", "autoload_top", "system_cron", "requests", "php_errors", "bisect"}
    _obj(b, name, top, {"schema", "site", "environment", "source"})
    if b["schema"] != BUNDLE_SCHEMA:
        raise Invalid(f"{name}: schema must be {BUNDLE_SCHEMA}")
    out: Dict[str, Any] = {"site": _str(b["site"], "site", 100), "source": _str(b["source"], "source", 200)}
    if b["environment"] not in ENVIRONMENTS:
        raise Invalid(f"environment: one of {', '.join(ENVIRONMENTS)}")
    out["environment"] = b["environment"]
    env = _obj(b.get("env", {}), "env", {"php", "wp", "host"})
    out["env"] = {k: _str(env[k], f"env.{k}", 64) for k in sorted(env)}
    m = _obj(b.get("measurement", {}), "measurement", {"tool", "warm_cache", "runs_per_url", "concurrency"})
    out["measurement"] = {"tool": _str(m["tool"], "measurement.tool", 100) if "tool" in m else None,
                          "warm_cache": m.get("warm_cache"), "runs_per_url": m.get("runs_per_url"),
                          "concurrency": m.get("concurrency")}
    if out["measurement"]["warm_cache"] not in (None, True, False):
        raise Invalid("measurement.warm_cache: true or false")
    for k in ("runs_per_url", "concurrency"):
        if out["measurement"][k] is not None:
            out["measurement"][k] = int(_num(out["measurement"][k], f"measurement.{k}", 1, 100000))
    cfg = _obj(b.get("wp_config", {}), "wp_config", set(b.get("wp_config", {})) if isinstance(b.get("wp_config"), dict) else set())
    wp, secrets_seen = {}, []
    for k, v in cfg.items():
        if not CONST_RE.match(k):
            raise Invalid("wp_config: constant names are UPPER_CASE")
        if SECRET_RE.search(k):
            secrets_seen.append(k)     # never stored, never echoed
            continue
        if not (isinstance(v, (bool, str)) or (isinstance(v, int) and not isinstance(v, bool))) or (isinstance(v, str) and len(v) > 256):
            raise Invalid(f"wp_config.{k}: true, false, an integer or short text")
        wp[k] = v
    out["wp_config"], out["secrets_ignored"] = wp, sorted(secrets_seen)
    out["dropins"] = sorted({_str(x, "dropins[]", 64) for x in _list(b.get("dropins", []), "dropins", 50)})
    plugs = []
    for x in _list(b.get("active_plugins", []), "active_plugins", 2000):
        if not isinstance(x, str) or not SLUG_RE.match(x):
            raise Invalid("active_plugins[]: plugin slug or slug/file.php")
        plugs.append(x.split("/")[0])
    out["active_plugins"] = sorted(set(plugs))
    out["autoload_bytes"] = int(_num(b["autoload_bytes"], "autoload_bytes", 0, 1e12)) if "autoload_bytes" in b else None
    tops = []
    for i, t in enumerate(_list(b.get("autoload_top", []), "autoload_top", 200)):
        _obj(t, f"autoload_top[{i}]", {"option", "bytes"}, {"option", "bytes"})
        tops.append({"option": _str(t["option"], "autoload_top[].option", 191), "bytes": int(_num(t["bytes"], "autoload_top[].bytes", 0, 1e12))})
    out["autoload_top"] = sorted(tops, key=lambda t: (-t["bytes"], t["option"]))
    if b.get("system_cron") not in (None, True, False):
        raise Invalid("system_cron: true, false or null")
    out["system_cron"] = b.get("system_cron")
    reqs, nq = [], 0
    for i, r in enumerate(_list(b.get("requests", []), "requests", MAX_REQUESTS)):
        w = f"requests[{i}]"
        _obj(r, w, {"id", "url", "total_ms", "peak_memory_mb", "queries", "hooks"}, {"id", "url", "total_ms"})
        qs = []
        for j, q in enumerate(_list(r.get("queries", []), f"{w}.queries", 5000)):
            _obj(q, f"{w}.queries[{j}]", {"sql", "ms", "caller", "component"}, {"sql", "ms"})
            qs.append({"sql": _str(q["sql"], f"{w}.queries[{j}].sql", 8192), "ms": _num(q["ms"], f"{w}.queries[{j}].ms", 0, 3.6e6),
                       "caller": _str(q.get("caller", ""), f"{w}.queries[{j}].caller", 256),
                       "component": _component(q.get("component"), f"{w}.queries[{j}].component")})
        nq += len(qs)
        if nq > MAX_QUERIES:
            raise Invalid(f"more than {MAX_QUERIES} queries in one bundle")
        hooks = []
        for j, h in enumerate(_list(r.get("hooks", []), f"{w}.hooks", 5000)):
            _obj(h, f"{w}.hooks[{j}]", {"hook", "callback", "component", "ms"}, {"hook", "callback", "ms"})
            hooks.append({"hook": _str(h["hook"], "hook", 128), "callback": _str(h["callback"], "callback", 256),
                          "component": _component(h.get("component"), f"{w}.hooks[{j}].component"), "ms": _num(h["ms"], "hook ms", 0, 3.6e6)})
        reqs.append({"id": _str(r["id"], f"{w}.id", 64), "url": _str(r["url"], f"{w}.url", 512),
                     "total_ms": _num(r["total_ms"], f"{w}.total_ms", 0, 3.6e6),
                     "peak_memory_mb": _num(r["peak_memory_mb"], f"{w}.peak_memory_mb", 0, 1e6) if "peak_memory_mb" in r else None,
                     "queries": qs, "hooks": hooks})
    if len({r["id"] for r in reqs}) != len(reqs):
        raise Invalid("requests: ids must be unique")
    out["requests"] = reqs
    out["php_errors"] = [_str(x, "php_errors[]", 4096) for x in _list(b.get("php_errors", []), "php_errors")]
    runs = []
    for i, r in enumerate(_list(b.get("bisect", []), "bisect", 512)):
        _obj(r, f"bisect[{i}]", {"plugins", "result"}, {"plugins", "result"})
        if r["result"] not in ("fail", "ok"):
            raise Invalid(f"bisect[{i}].result: fail or ok")
        ps = _list(r["plugins"], f"bisect[{i}].plugins", 2000)
        if any(not isinstance(p, str) or not SLUG_RE.match(p) for p in ps):
            raise Invalid(f"bisect[{i}].plugins[]: plugin slugs")
        runs.append({"plugins": sorted({p.split("/")[0] for p in ps}), "result": r["result"]})
    out["bisect"] = runs
    return out


# -- analysis -----------------------------------------------------------------------------

_QSTR = re.compile(r"'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"")
_QNUM = re.compile(r"\b\d+(?:\.\d+)?\b")
_QIN = re.compile(r"\(\s*\?(?:\s*,\s*\?)*\s*\)")
_QCOMMENT = re.compile(r"/\*.*?\*/", re.S)


def fingerprint(sql: str) -> str:
    s = _QCOMMENT.sub(" ", sql)
    s = _QSTR.sub("?", s)
    s = _QNUM.sub("?", s)
    s = _QIN.sub("(?+)", s)
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s[:300]


PATH_RE = re.compile(r"/wp-content/(plugins|mu-plugins|themes)/([A-Za-z0-9._-]+)|/(wp-includes|wp-admin)/")


def path_component(path: str) -> str:
    m = PATH_RE.search(path)
    if not m:
        return "unknown"
    if m.group(3):
        return "core"
    kind = {"plugins": "plugin", "mu-plugins": "mu-plugin", "themes": "theme"}[m.group(1)]
    slug = m.group(2).lower()
    if kind == "mu-plugin" and slug.endswith(".php"):
        slug = slug[:-4]
    return f"{kind}:{slug}"


REDECLARE_RE = re.compile(r"Cannot redeclare (?:function )?([A-Za-z0-9_\\]+)\(\) \(previously declared in (\S+?):(\d+)\) in (\S+?) on line (\d+)")
CLASS_RE = re.compile(r"Cannot declare (class|interface|trait) ([A-Za-z0-9_\\]+), because the name is already in use in (\S+?) on line (\d+)")
UNDEF_RE = re.compile(r"Uncaught Error: Call to undefined (?:function|method) ([A-Za-z0-9_\\:>-]+)\(\) in (\S+?):(\d+)")
MEMORY_RE = re.compile(r"Allowed memory size of (\d+) bytes exhausted (?:\(tried to allocate (\d+) bytes\) )?in (\S+?) on line (\d+)")


def _size(v: Any) -> Optional[int]:
    if isinstance(v, int) and not isinstance(v, bool):
        return v
    if isinstance(v, str):
        m = re.fullmatch(r"\s*(\d+)\s*([KMG]?)\s*", v, re.I)
        if m:
            return int(m.group(1)) * {"": 1, "K": 1024, "M": 1024 ** 2, "G": 1024 ** 3}[m.group(2).upper()]
    return None


def _finding(code: str, severity: str, components: List[str], detail: str, evidence: List[str], fix: str) -> Dict[str, Any]:
    return {"code": code, "severity": severity, "components": sorted(set(components)), "detail": detail,
            "evidence": [e[:300] for e in evidence[:5]], "fix": fix}


def bisect_explain(runs: List[Dict[str, Any]]) -> Tuple[str, List[Tuple[str, ...]], str]:
    """Smallest plugin set (one plugin, else one pair) present in every failing run and absent, as a
    whole, from every passing run. Returns (kind, candidates, note)."""
    fails = [set(r["plugins"]) for r in runs if r["result"] == "fail"]
    oks = [set(r["plugins"]) for r in runs if r["result"] == "ok"]
    if not fails:
        return "none", [], "no failing bisect run"
    common = set.intersection(*fails)
    if len(common) > MAX_BISECT_PLUGINS:
        return "none", [], f"more than {MAX_BISECT_PLUGINS} plugins in every failing run; narrow the runs first"
    singles = [(p,) for p in sorted(common) if not any(p in o for o in oks)]
    if singles:
        return "single", singles, ""
    pairs = [(a, b) for a, b in combinations(sorted(common), 2) if not any(a in o and b in o for o in oks)]
    if pairs:
        return "pair", pairs, ""
    return "none", [], "no single plugin or pair explains the bisect runs (theme, data or a larger set may be involved)"


def diagnose(b: Dict[str, Any], slow_ms: float, repeat: int, slow_hook_ms: float) -> Dict[str, Any]:
    F: List[Dict[str, Any]] = []
    notes: List[str] = []
    prod = b["environment"] == "production"
    cfg = b["wp_config"]
    # plugin conflicts and fatals from the PHP error log
    pairs_from_log: Dict[Tuple[str, str], Dict[str, Any]] = {}
    mem_fatal = []
    for line in b["php_errors"]:
        m = REDECLARE_RE.search(line)
        if m:
            a, c = path_component(m.group(2)), path_component(m.group(4))
            if a != c and "unknown" not in (a, c):
                key = tuple(sorted((a, c)))
                if key in pairs_from_log:
                    pairs_from_log[key]["evidence"].append(line[:300])
                    continue
                f = _finding("PLUGIN_CONFLICT", "high", [a, c], f"{c} redeclares {m.group(1)}() already declared by {a}",
                             [line], "rename or guard the function (function_exists) in one of them, or deactivate one; report to both authors")
                pairs_from_log[key] = f
                F.append(f)
            else:
                F.append(_finding("PLUGIN_FATAL", "high", [c], f"{m.group(1)}() declared twice inside {c} (two copies loaded?)",
                                  [line], "remove the duplicate copy of the plugin, then reinstall it once"))
            continue
        m = CLASS_RE.search(line)
        if m:
            c = path_component(m.group(3))
            F.append(_finding("PLUGIN_CONFLICT", "medium", [c], f"{c} declares {m.group(1)} {m.group(2)} that another component already declared; the first declarer is not in this log line",
                              [line], "find the other declarer with a bisect run; guard with class_exists or namespace the class"))
            continue
        m = UNDEF_RE.search(line)
        if m:
            c = path_component(m.group(2))
            F.append(_finding("PLUGIN_FATAL", "high", [c], f"{c} calls {m.group(1)}() which is not defined (missing or deactivated dependency)",
                              [line], "activate the plugin that provides it, or guard the call"))
            continue
        m = MEMORY_RE.search(line)
        if m:
            mem_fatal.append((int(m.group(1)), path_component(m.group(3)), line))
    # bisect runs
    kind, cands, why = bisect_explain(b["bisect"])
    if kind == "pair" and len(cands) == 1:
        a, c = cands[0]
        runs = f"bisect: {sum(r['result'] == 'fail' for r in b['bisect'])} failing and {sum(r['result'] == 'ok' for r in b['bisect'])} passing runs; every failing run has both {a} and {c}, no passing run has both"
        same = pairs_from_log.get(tuple(sorted((f"plugin:{a}", f"plugin:{c}"))))
        if same:
            same["detail"] += "; bisect runs agree"
            same["evidence"] = (same["evidence"] + [runs])[:5]
        else:
            F.append(_finding("PLUGIN_CONFLICT", "high", [f"plugin:{a}", f"plugin:{c}"], runs, [runs],
                              "keep one of the two active, or fix the clash, then rerun the failing request"))
    elif kind == "pair" and any(tuple(sorted((f"plugin:{a}", f"plugin:{c}"))) in pairs_from_log for a, c in cands):
        for a, c in cands:
            hit = pairs_from_log.get(tuple(sorted((f"plugin:{a}", f"plugin:{c}"))))
            if hit:
                hit["detail"] += f"; bisect runs are consistent with this pair ({len(cands)} pairs fit them)"
    elif kind == "pair" or (kind == "single" and len(cands) > 1) or (kind == "none" and any(r["result"] == "fail" for r in b["bisect"])):
        # a failure is recorded but the runs do not single it out: report it, name the candidates, claim no culprit
        names = sorted({p for c in cands for p in c})
        what = (f"{len(cands)} {'plugins' if kind == 'single' else 'plugin pairs'} explain the runs equally: "
                + ", ".join("+".join(c) for c in cands[:6])) if cands else why
        F.append(_finding("PLUGIN_FAILURE_UNLOCALIZED", "medium", [f"plugin:{n}" for n in names[:10]],
                          f"bisect runs record a failure that they do not single out ({what})",
                          [f"{len(b['bisect'])} bisect runs"], "add runs that separate the candidates (each candidate alone, then each pair)"))
    elif kind == "single" and len(cands) == 1:
        F.append(_finding("PLUGIN_FAULT", "high", [f"plugin:{cands[0][0]}"], f"bisect: every failing run has {cands[0][0]}; no passing run has it",
                          [f"{len(b['bisect'])} runs"], "update or replace that plugin; it fails on its own, not as a conflict"))
    elif b["bisect"] and why:
        notes.append(f"bisect: {why}")
    # queries
    by_fp: Dict[str, Dict[str, Any]] = {}
    total_q_ms = 0.0
    for r in b["requests"]:
        counts: Dict[Tuple[str, str], int] = {}
        for q in r["queries"]:
            fp = fingerprint(q["sql"])
            total_q_ms += q["ms"]
            g = by_fp.setdefault(fp, {"n": 0, "ms": 0.0, "max": 0.0, "components": set(), "callers": set(), "repeat_max": 0, "repeat_reqs": set()})
            g["n"] += 1
            g["ms"] += q["ms"]
            g["max"] = max(g["max"], q["ms"])
            g["components"].add(q["component"])
            if q["caller"]:
                g["callers"].add(q["caller"][:120])
            key = (fp, q["caller"])
            counts[key] = counts.get(key, 0) + 1
        for (fp, _caller), n in counts.items():
            if n >= repeat:
                g = by_fp[fp]
                g["repeat_max"] = max(g["repeat_max"], n)
                g["repeat_reqs"].add(r["id"])
    for fp, g in sorted(by_fp.items(), key=lambda kv: (-kv[1]["ms"], kv[0])):
        share = g["ms"] / total_q_ms if total_q_ms else 0.0
        if g["max"] >= slow_ms:
            F.append(_finding("SLOW_QUERY", "high" if share >= 0.25 else "medium", sorted(g["components"]),
                              f"{g['n']} runs, max {g['max']:.1f} ms, total {g['ms']:.1f} ms ({share:.0%} of query time)",
                              [fp] + sorted(g["callers"])[:2], "add an index or cache the result; check EXPLAIN on a copy of the database"))
        if g["repeat_max"]:
            F.append(_finding("REPEATED_QUERY", "medium", sorted(g["components"]),
                              f"the same query ran up to {g['repeat_max']} times from one caller in one request ({len(g['repeat_reqs'])} requests); an N+1 loop",
                              [fp] + sorted(g["callers"])[:2], "batch the lookups (one query with IN, or prime the cache before the loop)"))
    # hooks
    by_cb: Dict[Tuple[str, str, str], List[float]] = {}
    for r in b["requests"]:
        for h in r["hooks"]:
            by_cb.setdefault((h["component"], h["hook"], h["callback"]), []).append(h["ms"])
    for (comp, hook, cb), ms in sorted(by_cb.items()):
        if max(ms) >= slow_hook_ms:
            F.append(_finding("SLOW_HOOK_CALLBACK", "medium", [comp], f"{cb} on {hook}: max {max(ms):.1f} ms over {len(ms)} requests",
                              [f"{hook} {cb}"], "profile that callback (wp profile hook) and defer or cache its work"))
    # configuration
    debug_display = cfg.get("WP_DEBUG_DISPLAY", True)   # WordPress shows errors when WP_DEBUG is on unless this is false
    if prod and cfg.get("WP_DEBUG") is True and debug_display is not False:
        F.append(_finding("CONFIG_DEBUG_DISPLAY", "high", ["core"], "production site with WP_DEBUG on and errors displayed to visitors",
                          ["WP_DEBUG=true", f"WP_DEBUG_DISPLAY={json.dumps(cfg.get('WP_DEBUG_DISPLAY', 'unset (defaults to true)'))}"],
                          "set WP_DEBUG_DISPLAY to false (log with WP_DEBUG_LOG instead), or turn WP_DEBUG off"))
    if prod and cfg.get("SAVEQUERIES") is True:
        F.append(_finding("CONFIG_SAVEQUERIES", "medium", ["core"], "SAVEQUERIES on in production stores every query in memory on every request",
                          ["SAVEQUERIES=true"], "turn it off outside a profiling session"))
    limit = _size(cfg.get("WP_MEMORY_LIMIT")) if "WP_MEMORY_LIMIT" in cfg else None
    if "WP_MEMORY_LIMIT" in cfg and limit is None:
        notes.append("WP_MEMORY_LIMIT is not a size like 256M; memory not judged")
    peaks = [(r["peak_memory_mb"], r["url"]) for r in b["requests"] if r["peak_memory_mb"] is not None]
    if mem_fatal:
        lim, comp, line = mem_fatal[0]
        F.append(_finding("CONFIG_MEMORY_LIMIT", "high", [comp], f"PHP ran out of memory at {lim // (1024 * 1024)} MiB ({len(mem_fatal)} log lines); last allocation in {comp}",
                          [line], "raise WP_MEMORY_LIMIT (and PHP memory_limit) only after checking why that component needs it"))
    elif limit and peaks:
        top = max(peaks)
        if top[0] * 1024 * 1024 >= MEMORY_WARN * limit:
            F.append(_finding("CONFIG_MEMORY_LIMIT", "medium", ["core"], f"peak {top[0]:.0f} MiB on {top[1]} is {top[0] * 1024 * 1024 / limit:.0%} of WP_MEMORY_LIMIT {cfg['WP_MEMORY_LIMIT']}",
                              [f"WP_MEMORY_LIMIT={cfg['WP_MEMORY_LIMIT']}"], "find the request's memory use first; raise the limit only with headroom evidence"))
    elif peaks and limit is None and "WP_MEMORY_LIMIT" not in cfg:
        notes.append("WP_MEMORY_LIMIT not given; peak memory not judged")
    adv = "advanced-cache.php" in b["dropins"]
    if cfg.get("WP_CACHE") is True and not adv:
        F.append(_finding("CONFIG_CACHE_DROPIN_MISSING", "medium", ["core"], "WP_CACHE is on but wp-content/advanced-cache.php is missing, so no page cache runs",
                          ["WP_CACHE=true", f"dropins={b['dropins']}"], "reinstall the caching plugin's drop-in, or turn WP_CACHE off"))
    if adv and cfg.get("WP_CACHE") is not True:
        F.append(_finding("CONFIG_CACHE_DISABLED", "medium", ["core"], "advanced-cache.php is present but WP_CACHE is not true, so it never loads",
                          ["advanced-cache.php present", f"WP_CACHE={json.dumps(cfg.get('WP_CACHE', 'unset'))}"], "set WP_CACHE to true, or remove the stale drop-in"))
    if cfg.get("DISABLE_WP_CRON") is True:
        if b["system_cron"] is False:
            F.append(_finding("CONFIG_CRON_NOT_RUNNING", "high", ["core"], "DISABLE_WP_CRON is on and no system cron calls wp-cron.php, so scheduled events never run",
                              ["DISABLE_WP_CRON=true", "system_cron=false"], "add a system cron for wp cron event run --due-now, or turn DISABLE_WP_CRON off"))
        elif b["system_cron"] is None:
            notes.append("DISABLE_WP_CRON is on and the bundle does not say whether a system cron runs; cron not judged")
    if b["autoload_bytes"] is not None and b["autoload_bytes"] > AUTOLOAD_WARN:
        F.append(_finding("CONFIG_AUTOLOAD_BLOAT", "high" if b["autoload_bytes"] > 2_000_000 else "medium", ["core"],
                          f"{b['autoload_bytes']} bytes of autoloaded options are loaded on every request (WordPress Site Health warns above {AUTOLOAD_WARN})",
                          [f"{t['option']} {t['bytes']}" for t in b["autoload_top"][:5]], "set autoload off for the large options their plugins do not need on every request"))
    if b["secrets_ignored"]:
        notes.append(f"{len(b['secrets_ignored'])} secret-like wp_config constants were present and ignored; they are never echoed")
    F.sort(key=lambda f: ({"high": 0, "medium": 1, "low": 2}[f["severity"]], f["code"], f["components"], f["detail"]))
    return {"verdict": "faults_found" if F else "healthy", "findings": F, "notes": notes,
            "counts": {"requests": len(b["requests"]), "queries": sum(len(r["queries"]) for r in b["requests"]),
                       "query_fingerprints": len(by_fp), "php_error_lines": len(b["php_errors"]), "bisect_runs": len(b["bisect"])}}


def _scope(b: Dict[str, Any]) -> str:
    return ("offline analysis of the given trace and config bundle; no PHP, WordPress, WP-CLI or database was run. "
            f"Bundle source: {b['source']}")


def compare(a: Dict[str, Any], b: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    why = []
    for k in ("site", "environment", "env", "measurement"):
        if a[k] != b[k]:
            why.append(f"{k} differs: {json.dumps(a[k], sort_keys=True)[:120]} vs {json.dumps(b[k], sort_keys=True)[:120]}")
    if a["measurement"]["tool"] is None:
        why.append("measurement.tool is not stated, so the procedure cannot be shown to match")
    def samples(x):
        s: Dict[str, List[float]] = {}
        for r in x["requests"]:
            s.setdefault(r["url"], []).append(r["total_ms"])
        return s
    sa, sb = samples(a), samples(b)
    if sorted(sa) != sorted(sb):
        why.append(f"different URL sets: only before {sorted(set(sa) - set(sb))[:3]}, only after {sorted(set(sb) - set(sa))[:3]}")
    for u in sorted(set(sa) & set(sb)):
        if len(sa[u]) != len(sb[u]):
            why.append(f"{u}: {len(sa[u])} samples before, {len(sb[u])} after")
        elif len(sa[u]) < MIN_SAMPLES:
            why.append(f"{u}: {len(sa[u])} samples, at least {MIN_SAMPLES} needed")
    if not sa:
        why.append("no requests to compare")
    rep: Dict[str, Any] = {"comparable": not why, "not_comparable_because": why[:20]}
    if why:
        rep["speedup_claimed"] = False
        return False, rep
    urls = []
    for u in sorted(sa):
        x, y = sorted(sa[u]), sorted(sb[u])
        mx, my = statistics.median(x), statistics.median(y)
        consistent = y[-1] < x[0]          # every after-sample is faster than every before-sample
        slower = y[0] > x[-1]
        urls.append({"url": u, "samples": len(x), "median_before_ms": round(mx, 3), "median_after_ms": round(my, 3),
                     "ratio": round(mx / my, 3) if my > 0 else None,
                     "result": "faster" if consistent else "slower" if slower else "inconclusive (ranges overlap)"})
    rep["urls"] = urls
    rep["speedup_claimed"] = bool(urls) and all(u["result"] == "faster" for u in urls)
    rep["summary"] = ("every URL faster in every sample" if rep["speedup_claimed"] else
                      f"{sum(u['result'] == 'faster' for u in urls)} of {len(urls)} URLs consistently faster; no overall speedup claimed")
    return True, rep


# -- output -------------------------------------------------------------------------------

def _same(p: Path, q: Path) -> bool:
    try:
        sp, sq = os.stat(p), os.stat(q)
    except OSError:
        return False
    return (sp.st_dev, sp.st_ino) == (sq.st_dev, sq.st_ino)


def guard_out(out: Path, inputs: List[Path]) -> None:
    if out.is_symlink() or (out.exists() and not out.is_file()):
        raise Invalid(f"--out {out.name}: exists and is not a regular file")
    if not out.parent.is_dir():
        raise Invalid(f"--out {out.name}: its folder does not exist")
    fold = lambda p: os.path.normcase(os.path.realpath(p)).casefold()
    for p in inputs:
        if _same(out, p) or fold(out) == fold(p):
            raise Invalid(f"--out {out.name}: would overwrite an input")


def write_atomic(path: Path, data: bytes) -> None:
    tmp = path.parent / f".{path.name}.{secrets.token_hex(6)}.tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o644)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise


def render(rep: Dict[str, Any]) -> str:
    if rep["schema"] == COMPARE_SCHEMA:
        lines = [f"comparable: {rep['comparable']}"]
        lines += [f"  not comparable: {w}" for w in rep["not_comparable_because"]]
        for u in rep.get("urls", []):
            lines.append(f"  {u['url']}: median {u['median_before_ms']} -> {u['median_after_ms']} ms over {u['samples']} samples each: {u['result']}")
        if rep["comparable"]:
            lines.append(f"speedup claimed: {rep['speedup_claimed']} ({rep['summary']})")
        else:
            lines.append("speedup claimed: False")
    else:
        lines = [f"verdict: {rep['verdict']} ({len(rep['findings'])} findings)"]
        for f in rep["findings"]:
            lines.append(f"  {f['severity']:6} {f['code']} [{', '.join(f['components'])}] {f['detail']}")
        lines += [f"  note: {n}" for n in rep["notes"]]
    lines.append(f"scope: {rep['evidence_scope']}")
    return "\n".join(lines) + "\n"


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="wp_trace_diag.py", description="Offline WordPress diagnosis from a trace and config bundle.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("diagnose")
    d.add_argument("bundle")
    d.add_argument("--slow-ms", type=float, default=50.0, help="slow query threshold (Query Monitor's default is 50 ms)")
    d.add_argument("--repeat", type=int, default=10, help="same query from one caller this many times in one request is an N+1")
    d.add_argument("--slow-hook-ms", type=float, default=100.0)
    c = sub.add_parser("compare")
    c.add_argument("before")
    c.add_argument("after")
    for p in (d, c):
        p.add_argument("--json", action="store_true")
        p.add_argument("--out")
    try:
        a = ap.parse_args(argv)
    except SystemExit as exc:
        return 2 if exc.code else 0
    try:
        if a.cmd == "diagnose":
            if not (0 < a.slow_ms <= 3.6e6 and 2 <= a.repeat <= 100000 and 0 < a.slow_hook_ms <= 3.6e6):
                raise Invalid("--slow-ms and --slow-hook-ms must be positive, --repeat 2 or more")
            ins = [Path(a.bundle)]
            if a.out:
                guard_out(Path(a.out), ins)
            b = load_bundle(ins[0])
            rep = {"schema": REPORT_SCHEMA, "tool_version": TOOL_VERSION, "site": b["site"], "environment": b["environment"],
                   "evidence_scope": _scope(b), "thresholds": {"slow_ms": a.slow_ms, "repeat": a.repeat, "slow_hook_ms": a.slow_hook_ms}}
            rep.update(diagnose(b, a.slow_ms, a.repeat, a.slow_hook_ms))
            code = 0 if rep["verdict"] == "healthy" else 1
        else:
            ins = [Path(a.before), Path(a.after)]
            if a.out:
                guard_out(Path(a.out), ins)
            if _same(ins[0], ins[1]):
                raise Invalid("before and after are the same file")
            x, y = load_bundle(ins[0]), load_bundle(ins[1])
            ok, body = compare(x, y)
            rep = {"schema": COMPARE_SCHEMA, "tool_version": TOOL_VERSION, "evidence_scope": _scope(x) + f" / after: {y['source']}"}
            rep.update(body)
            code = 0 if ok else 3
    except Invalid as exc:
        print(f"invalid: {exc}", file=sys.stderr)
        return 2
    text = json.dumps(rep, indent=2, sort_keys=True) + "\n" if a.json or a.out else render(rep)
    if a.out:
        write_atomic(Path(a.out), (json.dumps(rep, indent=2, sort_keys=True) + "\n").encode("utf-8"))
        print(render(rep), end="")
    else:
        print(text, end="")
    return code


if __name__ == "__main__":
    sys.exit(main())
