#!/usr/bin/env python3
"""Offline network failure localization from a supplied trace (Solaris network-engineer).

Reads a JSON trace (schema "solaris.net-trace/1": target, optional host config and the
observations a client recorded while trying to reach it) and says which layer failed:
dns, route, tls or application. It never opens a socket, resolves a name or changes any
configuration. Evidence it does not have stays "unknown": a layer is only blamed with high
confidence when every earlier layer has positive evidence, otherwise the answer is a bounded
candidate set plus the observation that would settle it.

The same trace always gives the same bytes: observations are put in canonical order, no
wall clock is used (certificate dates are judged against the trace's captured_at), and
JSON output is sorted. Header values and response bodies are never echoed.

Usage:
  netdiag.py diagnose TRACE.json [--json] [--out REPORT]
  netdiag.py batch DIR [--json] [--out REPORT] [--workers N]
Exit codes: 0 healthy, 1 analysed with a fault or an undetermined result, 2 invalid input.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import hashlib
import ipaddress
import json
import os
import re
import secrets
import shlex
import stat
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

TRACE_SCHEMA = "solaris.net-trace/1"
REPORT_SCHEMA = "solaris.net-diagnosis/1"
BATCH_SCHEMA = "solaris.net-diagnosis-batch/1"
LAYERS = ("dns", "route", "tls", "application")
STAGES = ("dns", "route", "tcp", "tls", "http")
MAX_BYTES = 8 * 1024 * 1024
MAX_OBSERVATIONS = 10000
MAX_BATCH_FILES = 20000
HOST_RE = re.compile(r"^(?=.{1,253}$)(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))*\.?$")
DNS_RCODES = ("NOERROR", "NXDOMAIN", "SERVFAIL", "REFUSED", "TIMEOUT")
TCP_RESULTS = ("connected", "refused", "timeout", "unreachable", "reset")
TLS_RESULTS = ("ok", "alert", "timeout", "reset", "eof")
HTTP_RESULTS = ("response", "timeout", "reset")
ROUTE_TYPES = ("unicast", "blackhole", "unreachable", "prohibit")


class Invalid(Exception):
    """The trace cannot be analysed; nothing is written."""


# -- input validation -----------------------------------------------------------------

def _no_dupes(pairs: List[Tuple[str, Any]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k, v in pairs:
        if k in out:
            raise Invalid(f"duplicate key {k!r}; ambiguous evidence")
        out[k] = v
    return out


def _reject_const(name: str) -> Any:
    raise Invalid(f"non-finite number {name} is not valid evidence")


def _ip(value: Any, where: str) -> ipaddress._BaseAddress:
    if not isinstance(value, str):
        raise Invalid(f"{where}: expected an IP address string")
    try:
        return ipaddress.ip_address(value)
    except ValueError:
        raise Invalid(f"{where}: {value[:60]!r} is not an IP address") from None


def _net(value: Any, where: str) -> ipaddress._BaseNetwork:
    if not isinstance(value, str):
        raise Invalid(f"{where}: expected a CIDR string")
    try:
        return ipaddress.ip_network(value, strict=False)
    except ValueError:
        raise Invalid(f"{where}: {value[:60]!r} is not a network") from None


def _int(value: Any, where: str, lo: int, hi: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not lo <= value <= hi:
        raise Invalid(f"{where}: expected an integer {lo}..{hi}")
    return value


def _str(value: Any, where: str, limit: int = 256) -> str:
    if not isinstance(value, str) or len(value) > limit or any(ord(c) < 32 for c in value):
        raise Invalid(f"{where}: expected a single-line string of at most {limit} characters")
    return value


def _choice(value: Any, where: str, options: Tuple[str, ...]) -> str:
    if value not in options:
        raise Invalid(f"{where}: expected one of {', '.join(options)}")
    return value


RFC3339_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})[Tt ](\d{2}:\d{2}:\d{2})(?:\.(\d+))?([Zz]|[+-]\d{2}:\d{2})$")


def _iso(s: str) -> dt.datetime:
    """RFC 3339 only, parsed the same way on Python 3.9 to 3.13 (3.11+ fromisoformat accepts more
    forms, such as +0000, basic or week dates, that 3.9 refuses, so they are refused everywhere).
    RFC 3339 allows any number of fraction digits (Go, Kubernetes and journald write 9); digits past
    the sixth are truncated, since datetime keeps microseconds."""
    m = RFC3339_RE.match(s)
    if not m:
        raise ValueError(s)
    day, clock, frac, zone = m.groups()
    zone = "+00:00" if zone in ("Z", "z") else zone
    return dt.datetime.fromisoformat(f"{day}T{clock}" + (f".{frac[:6].ljust(6, '0')}" if frac else "") + zone)


def _time(value: Any, where: str) -> dt.datetime:
    s = _str(value, where, 64)
    try:
        t = _iso(s)
    except ValueError:
        raise Invalid(f"{where}: {s!r} is not an RFC 3339 time (YYYY-MM-DDTHH:MM:SS[.fraction] with Z or +HH:MM)") from None
    if t.tzinfo is None:
        raise Invalid(f"{where}: time must carry a zone (for example Z or +00:00)")
    return t.astimezone(dt.timezone.utc)


def _host(value: Any, where: str) -> str:
    s = _str(value, where, 253)
    try:
        ipaddress.ip_address(s)
        return s
    except ValueError:
        pass
    if not HOST_RE.match(s):
        raise Invalid(f"{where}: {s[:60]!r} is not a host name")
    return s.rstrip(".").lower()


def _obj(value: Any, where: str) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise Invalid(f"{where}: expected an object")
    return value


def _list(value: Any, where: str, limit: int = 256) -> List[Any]:
    if not isinstance(value, list) or len(value) > limit:
        raise Invalid(f"{where}: expected a list of at most {limit} items")
    return value


def load_trace(path: Path) -> Tuple[Dict[str, Any], str]:
    """Read and validate one trace file. Returns (normalised trace, sha256 of the bytes)."""
    try:
        st = os.lstat(path)
    except FileNotFoundError:
        raise Invalid(f"{path.name}: no such file") from None
    if stat.S_ISLNK(st.st_mode):
        raise Invalid(f"{path.name}: is a symlink; pass the real file")
    if not stat.S_ISREG(st.st_mode):
        raise Invalid(f"{path.name}: not a regular file")
    if st.st_size > MAX_BYTES:
        raise Invalid(f"{path.name}: larger than {MAX_BYTES} bytes")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(fd, "rb") as fh:
        raw = fh.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise Invalid(f"{path.name}: larger than {MAX_BYTES} bytes")
    try:
        doc = json.loads(raw.decode("utf-8"), object_pairs_hook=_no_dupes, parse_constant=_reject_const)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Invalid(f"{path.name}: not UTF-8 JSON ({exc.__class__.__name__})") from None
    except RecursionError:
        raise Invalid(f"{path.name}: JSON nested too deeply") from None
    return normalise(doc), hashlib.sha256(raw).hexdigest()


def normalise(doc: Any) -> Dict[str, Any]:
    doc = _obj(doc, "trace")
    if doc.get("schema") != TRACE_SCHEMA:
        raise Invalid(f"trace: schema must be {TRACE_SCHEMA!r}")
    tgt = _obj(doc.get("target"), "target")
    scheme = _choice(tgt.get("scheme", "https"), "target.scheme", ("http", "https"))
    target = {"host": _host(tgt.get("host"), "target.host"), "scheme": scheme,
              "port": _int(tgt.get("port", 443 if scheme == "https" else 80), "target.port", 1, 65535),
              "path": _str(tgt.get("path", "/"), "target.path", 512)}
    captured = _time(doc["captured_at"], "captured_at") if doc.get("captured_at") is not None else None
    cfg = _obj(doc.get("config", {}), "config")
    config = {
        "resolvers": sorted({str(_ip(r, f"config.resolvers[{i}]")) for i, r in enumerate(_list(cfg.get("resolvers", []), "config.resolvers"))}),
        "addresses": [], "routes": [],
        "expected_addresses": sorted({str(_ip(a, f"config.expected_addresses[{i}]")) for i, a in
                                      enumerate(_list(cfg.get("expected_addresses", []), "config.expected_addresses"))}),
        "has_routes": "routes" in cfg,
    }
    for i, a in enumerate(_list(cfg.get("addresses", []), "config.addresses")):
        a = _obj(a, f"config.addresses[{i}]")
        try:
            iface = ipaddress.ip_interface(_str(a.get("cidr"), f"config.addresses[{i}].cidr", 64))
        except ValueError:
            raise Invalid(f"config.addresses[{i}].cidr: not an interface address such as 10.0.0.5/24") from None
        config["addresses"].append({"dev": _str(a.get("dev", "?"), f"config.addresses[{i}].dev", 32), "cidr": str(iface)})
    for i, r in enumerate(_list(cfg.get("routes", []), "config.routes", 4096)):
        r = _obj(r, f"config.routes[{i}]")
        dst = "0.0.0.0/0" if r.get("dst") == "default" else r.get("dst")
        route = {"dst": str(_net(dst, f"config.routes[{i}].dst")),
                 "type": _choice(r.get("type", "unicast"), f"config.routes[{i}].type", ROUTE_TYPES),
                 "via": str(_ip(r["via"], f"config.routes[{i}].via")) if r.get("via") is not None else None,
                 "dev": _str(r.get("dev", ""), f"config.routes[{i}].dev", 32)}
        config["routes"].append(route)
    config["routes"].sort(key=lambda r: (r["dst"], r["type"], r["via"] or "", r["dev"]))
    obs_in = _list(doc.get("observations", []), "observations", MAX_OBSERVATIONS)
    obs = [_observation(o, i) for i, o in enumerate(obs_in)]
    obs.sort(key=lambda o: json.dumps(o, sort_keys=True))  # canonical order: input order never matters
    return {"target": target, "captured_at": captured.isoformat() if captured else None,
            "config": config, "observations": obs}


def _observation(o: Any, i: int) -> Dict[str, Any]:
    w = f"observations[{i}]"
    o = _obj(o, w)
    stage = _choice(o.get("stage"), f"{w}.stage", STAGES)
    if stage == "dns":
        rcode = _choice(o.get("rcode"), f"{w}.rcode", DNS_RCODES)
        answers = sorted({str(_ip(a, f"{w}.answers")) for a in _list(o.get("answers", []), f"{w}.answers")})
        return {"stage": "dns", "qname": _host(o.get("qname"), f"{w}.qname"),
                "resolver": str(_ip(o["resolver"], f"{w}.resolver")) if o.get("resolver") is not None else None,
                "rcode": rcode, "answers": answers}
    if stage == "route":
        hops = []
        for j, h in enumerate(_list(o.get("hops", []), f"{w}.hops", 64)):
            h = _obj(h, f"{w}.hops[{j}]")
            hops.append({"ttl": _int(h.get("ttl"), f"{w}.hops[{j}].ttl", 1, 255),
                         "addr": str(_ip(h["addr"], f"{w}.hops[{j}].addr")) if h.get("addr") is not None else None})
        hops.sort(key=lambda h: h["ttl"])
        reached = o.get("reached")
        if not isinstance(reached, bool):
            raise Invalid(f"{w}.reached: expected true or false")
        return {"stage": "route", "dst": str(_ip(o.get("dst"), f"{w}.dst")), "hops": hops, "reached": reached}
    if stage == "tcp":
        return {"stage": "tcp", "dst": str(_ip(o.get("dst"), f"{w}.dst")),
                "port": _int(o.get("port"), f"{w}.port", 1, 65535),
                "result": _choice(o.get("result"), f"{w}.result", TCP_RESULTS)}
    if stage == "tls":
        out: Dict[str, Any] = {"stage": "tls", "result": _choice(o.get("result"), f"{w}.result", TLS_RESULTS),
                               "sni": _host(o["sni"], f"{w}.sni") if o.get("sni") is not None else None,
                               "dst": str(_ip(o["dst"], f"{w}.dst")) if o.get("dst") is not None else None,
                               "alert": _str(o["alert"], f"{w}.alert", 64) if o.get("alert") is not None else None,
                               "version": _str(o["version"], f"{w}.version", 16) if o.get("version") is not None else None,
                               "cert": None}
        if o.get("cert") is not None:
            c = _obj(o["cert"], f"{w}.cert")
            out["cert"] = {
                "san": sorted({_san_text(_str(s, f"{w}.cert.san", 1024)) for s in _list(c.get("san", []), f"{w}.cert.san")}),
                "not_before": _time(c["not_before"], f"{w}.cert.not_before").isoformat() if c.get("not_before") is not None else None,
                "not_after": _time(c["not_after"], f"{w}.cert.not_after").isoformat() if c.get("not_after") is not None else None,
                "chain_trusted": c.get("chain_trusted") if isinstance(c.get("chain_trusted"), bool) else None}
        return out
    status = o.get("status")
    result = _choice(o.get("result", "response" if status is not None else None), f"{w}.result", HTTP_RESULTS)
    if result == "response":
        status = _int(status, f"{w}.status", 100, 599)
    else:
        status = None
    headers = o.get("headers", {})
    names = sorted({_str(k, f"{w}.headers", 64).lower() for k in _obj(headers, f"{w}.headers")})
    return {"stage": "http", "result": result, "status": status, "header_names": names,
            "via_proxy": bool(o.get("via_proxy", False))}


# -- analysis -------------------------------------------------------------------------

# Typed SAN spellings: openssl "DNS:", "IP:", "IP Address:"; keytool "DNSName:", "IPAddress:";
# Windows certutil "DNS Name=", "IP Address=". Anything else typed is not understood.
SAN_PREFIX_RE = re.compile(r"^\s*(dns ?name|dns|ip ?address|ip)\s*[:=]\s*", re.I)
OTHER_TYPE_RE = re.compile(r"^\s*[A-Za-z][A-Za-z0-9 ._-]{0,30}\s*[:=]")
# SAN types that are never host names (RFC 6125: only dNSName and iPAddress identify a TLS server), in the
# spellings of openssl (URI:, email:, othername:, DirName:, Registered ID:), Java keytool (URIName:, OIDName:,
# Other-Name:, RFC822Name:, DirectoryName:, EDIPartyName:, X400Address:) and Windows certutil (URL=,
# RFC822 Name=, Other Name:, Directory Address:, Registered ID=).
NON_HOST_TYPES = (r"uri ?name|uri|url|email|rfc822 ?name|other[ -]?name|oid ?name|dir ?name|directory ?name|"
                  r"directory ?address|registered ?id|x400(?: ?name| ?address)?|edi ?party ?name")
NON_HOST_TYPE_RE = re.compile(r"^\s*(" + NON_HOST_TYPES + r")\s*[:=]", re.I)
TYPED_SPLIT_RE = re.compile(r",\s*(?=(?:dns ?name|dns|ip ?address|ip|" + NON_HOST_TYPES + r")\s*[:=])", re.I)
# Multi-label public suffixes a wildcard may not sit on (a short list, not the full PSL).
PUBLIC_SUFFIXES = frozenset("""co.uk org.uk ac.uk gov.uk ltd.uk plc.uk me.uk net.uk sch.uk nhs.uk
com.au net.au org.au edu.au gov.au co.nz org.nz net.nz govt.nz co.jp ne.jp or.jp ac.jp go.jp
com.br net.br org.br gov.br co.in net.in org.in gov.in com.cn net.cn org.cn gov.cn com.mx org.mx
co.za org.za gov.za com.tr com.tw org.tw com.hk org.hk com.sg org.sg com.my co.kr or.kr co.il
org.il ac.il com.ar com.co com.pe com.ua co.id or.id ac.id github.io herokuapp.com
cloudfront.net amazonaws.com azurewebsites.net appspot.com blogspot.com""".split())


def _san_text(raw: str) -> str:
    """Normalise case for ASCII text only. str.lower() folds some non-ASCII letters into ASCII
    (U+212A KELVIN SIGN becomes k), which would let a non-ASCII entry match an ASCII host."""
    return raw.lower() if raw.isascii() else raw


def _split_nonhost(piece: str) -> List[str]:
    """A non-host value (URI, email, Registered ID, DirName, ...) ends at ', ' when the next chunk has
    no '=' and no type prefix, so 'URI:spiffe://x, api.example' gives the bare name its own entry
    (M10 r4 V1), while DirName RDNs (', O=Shop') stay with their value. URI, email and Registered ID
    values hold no spaces, so ', ' never splits inside them; a comma without a space never splits."""
    chunks = re.split(r",(?=\s)", piece)
    out = [chunks[0]]
    for c in chunks[1:]:
        if "=" in c or OTHER_TYPE_RE.match(c):
            out[-1] += "," + c
        else:
            out.append(c)
    return out


def _san_parts(raw: str) -> List[str]:
    """One SAN item may be the one-line openssl list 'DNS:a, DNS:b, IP Address:192.0.2.1'."""
    if "," not in raw:
        return [raw]
    typed = SAN_PREFIX_RE.match(raw) or NON_HOST_TYPE_RE.match(raw)
    if not typed:
        parts = raw.split(",")
    else:
        # split before each type prefix, then split a DNS, IP or bare piece at its own commas, so a bare
        # name after a typed one ('DNS:a.example, api.example') is its own entry; a non-host value
        # (DirName, URI, ...) keeps its commas except before a bare name (_split_nonhost)
        parts = []
        for piece in TYPED_SPLIT_RE.split(raw):
            parts.extend(_split_nonhost(piece) if NON_HOST_TYPE_RE.match(piece) else piece.split(","))
    return [p for p in (x.strip() for x in parts) if p]


def _san_entry(raw: str) -> Tuple[Optional[str], str]:
    """Split one SAN entry into (kind, value): kind 'dns', 'ip', None for a bare entry, 'invalid' for
    text that can never be a certificate name (non-ASCII: dNSName is IA5String; a double trailing
    dot), or 'unknown' for another type spelling the tool does not understand. Neither covers
    anything; an unknown entry is reported and blocks a confident mismatch verdict."""
    if not raw.isascii():
        return "invalid", raw
    m = SAN_PREFIX_RE.match(raw)
    if m:
        kind, value = ("dns" if m.group(1).lower().startswith("dns") else "ip"), raw[m.end():].strip()
    elif NON_HOST_TYPE_RE.match(raw):
        return "other", raw.strip()
    elif OTHER_TYPE_RE.match(raw) and not _is_ip(raw.strip()):
        return "unknown", raw.strip()
    else:
        kind, value = None, raw.strip()
    if value.endswith("..") or not value:
        return "invalid", raw.strip()
    value = value[:-1] if value.endswith(".") else value
    return kind, value.lower()


def _san_entries(san: List[str]) -> List[Tuple[Optional[str], str]]:
    return [_san_entry(p) for raw in san for p in _san_parts(raw)]


def _wildcard_covers(name: str, host: str) -> bool:
    """One leftmost '*' label only, over at least two labels that are not a public suffix."""
    base = name[2:]
    if "*" in base or "." not in base or base in PUBLIC_SUFFIXES:
        return False
    head, _, rest = host.partition(".")
    return bool(head) and rest == base


def _san_matches(host: str, san: List[str]) -> bool:
    try:
        host_ip = ipaddress.ip_address(host)
    except ValueError:
        host_ip = None
    for kind, name in _san_entries(san):
        if kind in ("unknown", "invalid", "other"):
            continue
        if host_ip is not None:
            # an address target is covered only by an address entry (bare or IP:), compared as addresses
            if kind == "dns":
                continue
            try:
                if ipaddress.ip_address(name) == host_ip:
                    return True
            except ValueError:
                pass
            continue
        if kind == "ip":
            continue  # an address entry never covers a host name
        if name == host:
            return True
        if name.startswith("*.") and "." in host:
            if _wildcard_covers(name, host):
                return True
    return False


def _route_for(config: Dict[str, Any], ip: str) -> Optional[Dict[str, Any]]:
    addr = ipaddress.ip_address(ip)
    best = None
    for r in config["routes"]:
        net = ipaddress.ip_network(r["dst"])
        if net.version == addr.version and addr in net and (best is None or net.prefixlen > ipaddress.ip_network(best["dst"]).prefixlen):
            best = r
    for a in config["addresses"]:  # connected networks
        iface = ipaddress.ip_interface(a["cidr"])
        if iface.version == addr.version and addr in iface.network:
            if best is None or iface.network.prefixlen >= ipaddress.ip_network(best["dst"]).prefixlen:
                best = {"dst": str(iface.network), "type": "unicast", "via": None, "dev": a["dev"]}
    return best


def _config_path_problem(config: Dict[str, Any], ip: str) -> Optional[Tuple[str, str]]:
    """Return (code, detail) when the supplied config cannot carry packets to ip."""
    if not config["has_routes"] and not config["addresses"]:
        return None  # no config supplied: say nothing
    r = _route_for(config, ip)
    if r is None:
        return "ROUTE_NO_MATCH", f"no route in the supplied config covers {ip}"
    if r["type"] != "unicast":
        return "ROUTE_" + r["type"].upper(), f"route {r['dst']} for {ip} is type {r['type']}"
    if r["via"] and config["addresses"]:
        gw = ipaddress.ip_address(r["via"])
        if not any(gw in ipaddress.ip_interface(a["cidr"]).network for a in config["addresses"]):
            return "ROUTE_GATEWAY_OFFLINK", f"gateway {r['via']} for {r['dst']} is on no local network"
    return None


class _Layer:
    def __init__(self) -> None:
        self.ok: List[str] = []
        self.failed: List[str] = []

    def state(self) -> str:
        if self.failed and self.ok:
            return "intermittent"
        if self.failed:
            return "failed"
        if self.ok:
            return "ok"
        return "unknown"


def analyse(trace: Dict[str, Any], input_sha256: str) -> Dict[str, Any]:
    t, cfg, obs = trace["target"], trace["config"], trace["observations"]
    host, port = t["host"], t["port"]
    is_ip = _is_ip(host)
    applicable = [l for l in LAYERS if not (l == "tls" and t["scheme"] == "http")]
    L = {l: _Layer() for l in LAYERS}
    findings: List[Dict[str, Any]] = []
    notes: List[str] = []
    ambiguous: Dict[str, List[str]] = {}  # layer -> extra candidate layers that could explain it

    def find(code: str, layer: str, detail: str, ev: str) -> None:
        findings.append({"code": code, "layer": layer, "detail": detail, "evidence": ev})

    # DNS
    dns_obs = [o for o in obs if o["stage"] == "dns" and o["qname"] == host]
    answers = sorted({a for o in dns_obs if o["rcode"] == "NOERROR" for a in o["answers"]})
    if is_ip:
        L["dns"].ok.append(f"target is the IP literal {host}; no lookup needed")
        answers = [host]
    for o in dns_obs:
        ev = f"dns {host} @{o['resolver'] or '?'} -> {o['rcode']}" + (f" {','.join(o['answers'])}" if o["answers"] else "")
        if o["rcode"] == "NOERROR" and o["answers"]:
            L["dns"].ok.append(ev)
        elif o["rcode"] == "NOERROR":
            L["dns"].failed.append(ev)
            find("DNS_NO_ADDRESS", "dns", f"{host} exists but has no address record at {o['resolver'] or 'the resolver'}", ev)
        elif o["rcode"] == "TIMEOUT":
            L["dns"].failed.append(ev)
            prob = _config_path_problem(cfg, o["resolver"]) if o["resolver"] else None
            if prob:
                find(prob[0], "route", prob[1] + " (the resolver)", ev)
                L["route"].failed.append(f"config: {prob[1]}")
                notes.append(f"DNS timed out because the supplied config has no usable path to resolver {o['resolver']}")
            else:
                find("DNS_TIMEOUT", "dns", f"resolver {o['resolver'] or '?'} did not answer", ev)
                ambiguous.setdefault("dns", []).append("route")
        else:
            L["dns"].failed.append(ev)
            find("DNS_" + o["rcode"], "dns", f"resolver {o['resolver'] or '?'} answered {o['rcode']} for {host}", ev)
    ok_sets = {tuple(o["answers"]) for o in dns_obs if o["rcode"] == "NOERROR" and o["answers"]}
    if len(ok_sets) > 1:
        notes.append(f"resolvers disagree about {host}: {sorted(' '.join(s) for s in ok_sets)}")
        find("DNS_INCONSISTENT", "dns", f"resolvers return different addresses for {host}", "dns answers differ")
    if cfg["expected_addresses"] and answers and not is_ip and not set(answers) & set(cfg["expected_addresses"]):
        ev = f"dns answers {','.join(answers)} vs expected {','.join(cfg['expected_addresses'])}"
        L["dns"].failed.append(ev)
        find("DNS_WRONG_ADDRESS", "dns", f"{host} resolves to an address the config does not expect", ev)

    # Route / transport
    for o in obs:
        if o["stage"] == "route":
            ev = f"traceroute {o['dst']}: {len(o['hops'])} hops, reached={str(o['reached']).lower()}"
            addrs = [h["addr"] for h in o["hops"] if h["addr"]]
            loop = any(addrs[i] in addrs[:i - 1] for i in range(2, len(addrs)))
            if loop:
                L["route"].failed.append(ev)
                find("ROUTE_LOOP", "route", f"path to {o['dst']} revisits a router", ev)
            elif o["reached"]:
                L["route"].ok.append(ev)
            else:
                last = next((h for h in reversed(o["hops"]) if h["addr"]), None)
                o["_unreached"] = (ev, last)
    tcp = [o for o in obs if o["stage"] == "tcp" and o["port"] == port]
    for o in tcp:
        ev = f"tcp {o['dst']}:{o['port']} -> {o['result']}"
        if o["result"] in ("connected", "refused"):
            L["route"].ok.append(ev + " (host reached)")
        elif o["result"] in ("timeout", "unreachable"):
            L["route"].failed.append(ev)
            prob = _config_path_problem(cfg, o["dst"])
            if prob:
                find(prob[0], "route", prob[1], ev)
            elif o["result"] == "unreachable":
                find("ROUTE_UNREACHABLE", "route", f"a router reported {o['dst']} unreachable", ev)
            else:
                find("ROUTE_OR_FILTER_TIMEOUT", "route", f"no answer from {o['dst']}:{o['port']}; packets are dropped on the path or by a firewall", ev)
                notes.append("a TCP timeout cannot tell a routing hole from a silent firewall drop; both sit in the route layer here")
        else:
            L["route"].ok.append(ev + " (host reached)")
            L["tls" if "tls" in applicable else "application"].failed.append(ev)
            find("TCP_RESET", "tls" if "tls" in applicable else "application", f"{o['dst']}:{o['port']} reset the connection after accepting it", ev)
            ambiguous.setdefault("tls" if "tls" in applicable else "application", []).append("route")
        if o["result"] in ("connected", "refused", "reset") and answers and not is_ip and o["dst"] not in answers:
            notes.append(f"TCP target {o['dst']} is not among the DNS answers {answers}")
    if not L["route"].ok and not L["route"].failed and answers and (cfg["has_routes"] or cfg["addresses"]):
        probs = {a: _config_path_problem(cfg, a) for a in answers}
        if all(probs.values()):
            for a, p in sorted(probs.items()):
                find(p[0], "route", p[1], "config")
            L["route"].failed.append("config: no usable route to any answer")

    # TLS
    if "tls" in applicable:
        for o in obs:
            if o["stage"] != "tls":
                continue
            ev = f"tls {o['dst'] or host} sni={o['sni'] or '-'} -> {o['result']}" + (f" ({o['alert']})" if o["alert"] else "")
            problems = []
            if o["sni"] and not is_ip and o["sni"] != host:
                problems.append(("TLS_SNI_MISMATCH", f"the client sent SNI {o['sni']} but the target is {host}"))
            c = o["cert"]
            if c is not None:
                if trace["captured_at"]:
                    now = _iso(trace["captured_at"])
                    if c["not_after"] and now > _iso(c["not_after"]):
                        problems.append(("TLS_CERT_EXPIRED", f"certificate expired {c['not_after']} (trace captured {trace['captured_at']})"))
                    if c["not_before"] and now < _iso(c["not_before"]):
                        problems.append(("TLS_CERT_NOT_YET_VALID", f"certificate valid only from {c['not_before']}"))
                elif c["not_after"]:
                    notes.append("certificate dates not judged: the trace has no captured_at")
                entries = _san_entries(c["san"])
                hostnames = [n for k, n in entries if k in ("dns", "ip")]
                # Non-host types are ignored beside real DNS/IP entries; with no host entry at all they stay
                # "not understood" (no confident mismatch), as in r3.
                unknown = [n for k, n in entries if k == "unknown" or (k == "other" and not hostnames)]
                other = [n for k, n in entries if k == "other" and hostnames]
                if other:
                    notes.append(f"certificate SAN entries that are not host names were ignored: {sorted(other)[:4]}")
                if unknown:
                    notes.append(f"certificate SAN entries not understood and not used: {sorted(unknown)[:4]}; "
                                 "if one of them is really a host name, give it as DNS:<name> or IP:<address>. "
                                 "URI, email and other non-host types never name a TLS server: do not rewrite them as DNS")
                if c["san"] and not unknown and not _san_matches(o["sni"] or host, c["san"]):
                    problems.append(("TLS_NAME_MISMATCH", f"certificate host names {hostnames[:4]} do not cover {o['sni'] or host}"))
                    verified = bool(cfg["expected_addresses"]) and bool(set(answers) & set(cfg["expected_addresses"]))
                    if not is_ip and not verified:
                        ambiguous.setdefault("tls", []).append("dns")
                        notes.append(f"a name mismatch can also mean DNS sent the client to the wrong server; "
                                     f"supply config.expected_addresses for {host} to rule that out")
                if c["chain_trusted"] is False:
                    problems.append(("TLS_UNTRUSTED_CHAIN", "certificate chain does not lead to a trusted root"))
            if o["result"] in ("ok", "alert"):
                L["route"].ok.append(ev + " (server answered)")
            if o["result"] == "ok" and not problems:
                L["tls"].ok.append(ev)
                if not is_ip and c is not None and c["san"]:
                    L["dns"].ok.append(f"server presented a valid certificate for {host} (implied)")
                continue
            L["tls"].failed.append(ev)
            for code, detail in problems:
                find(code, "tls", detail, ev)
            if o["result"] == "ok" and any(code != "TLS_SNI_MISMATCH" for code, _ in problems):
                notes.append("the client completed the handshake despite certificate problems; was verification disabled?")
            if not problems:
                if o["result"] == "alert":
                    code = "TLS_PROTOCOL_MISMATCH" if (o["alert"] or "").lower() in ("protocol_version", "handshake_failure", "insufficient_security") else "TLS_ALERT"
                    find(code, "tls", f"server sent alert {o['alert'] or '(unnamed)'}", ev)
                else:
                    find("TLS_HANDSHAKE_" + o["result"].upper(), "tls", f"handshake ended with {o['result']} before a certificate was seen", ev)
                    ambiguous.setdefault("tls", []).append("route")  # middleboxes also cut handshakes

    # Application
    for o in tcp:
        if o["result"] == "refused":
            ev = f"tcp {o['dst']}:{o['port']} -> refused"
            L["application"].failed.append(ev)
            find("APP_NOT_LISTENING", "application", f"{o['dst']} is reachable but nothing accepts connections on port {o['port']}", ev)
    for o in obs:
        if o["stage"] != "http":
            continue
        ev = f"http {t['path']} -> {o['status'] if o['status'] is not None else o['result']}"
        if o["result"] == "response":
            L["route"].ok.append(ev + " (server answered)")
            if "tls" in applicable:
                L["tls"].ok.append(ev + " (request carried over TLS)")
        if o["result"] != "response":
            L["application"].failed.append(ev)
            find("APP_" + o["result"].upper(), "application", f"request sent but the response {'never came' if o['result'] == 'timeout' else 'was cut off'}", ev)
        elif o["status"] >= 500:
            L["application"].failed.append(ev)
            gw = o["status"] in (502, 503, 504) and (o["via_proxy"] or "via" in o["header_names"])
            find("APP_UPSTREAM_ERROR" if gw else "APP_SERVER_ERROR", "application",
                 f"HTTP {o['status']}" + (" from a proxy; the service behind it failed" if gw else " from the service"), ev)
        elif o["status"] >= 400:
            L["application"].failed.append(ev)
            find("APP_CLIENT_ERROR", "application", f"HTTP {o['status']}: the network delivered the request; the request itself was refused", ev)
        else:
            L["application"].ok.append(ev)

    for o in obs:
        if o.get("_unreached"):
            ev, last = o.pop("_unreached")
            if L["route"].ok:
                notes.append(f"traceroute to {o['dst']} stops after {last['addr'] if last else 'the first hop'} but the host answered TCP; ICMP is probably filtered")
            else:
                L["route"].failed.append(ev)
                prob = _config_path_problem(cfg, o["dst"])
                if prob:
                    find(prob[0], "route", prob[1], ev)
                else:
                    find("ROUTE_PATH_LOSS", "route", f"path to {o['dst']} goes silent after {last['addr'] if last else 'the first hop'}", ev)
    # implied positive evidence: a server that answered proves the layers below it
    if L["application"].ok and not L["application"].failed:
        for l in ("dns", "route"):
            if not L[l].ok and not L[l].failed:
                L[l].ok.append("implied by an end-to-end application response")
    not_reached = set()
    if tcp and all(o["result"] == "refused" for o in tcp) and "tls" in applicable and not L["tls"].ok and not L["tls"].failed:
        not_reached.add("tls")  # nothing accepted the connection, so no handshake could start
    dns_symptom = bool(dns_obs) and not L["dns"].ok and all(
        o["rcode"] == "TIMEOUT" and o["resolver"] and _config_path_problem(cfg, o["resolver"]) for o in dns_obs)
    resolver = next((o["resolver"] for o in dns_obs if o["resolver"]), None)
    addr = (sorted({o["dst"] for o in tcp}) or answers or [None])[0]
    ctx = {"addr": resolver if dns_symptom else addr, "resolver": resolver, "answers": answers}
    return _verdict(t, applicable, L, findings, notes, ambiguous, trace, input_sha256, not_reached, dns_symptom, ctx)


def _is_ip(s: str) -> bool:
    try:
        ipaddress.ip_address(s)
        return True
    except ValueError:
        return False


def _verdict(t, applicable, L, findings, notes, ambiguous, trace, sha, not_reached, dns_symptom, ctx) -> Dict[str, Any]:
    states = {l: (L[l].state() if l in applicable else "not_applicable") for l in LAYERS}
    for l in not_reached:
        states[l] = "not_reached"
    first = next((l for l in applicable if states[l] in ("failed", "intermittent")), None)
    if first == "dns" and dns_symptom:
        first = "route"  # the lookup failed only because the resolver cannot be reached
        states["route"] = "failed"
    if first:
        for l in applicable[applicable.index(first) + 1:]:
            if states[l] == "unknown":
                states[l] = "not_reached"
    before = applicable[: applicable.index(first)] if first else applicable
    unknown_before = [l for l in before if states[l] == "unknown"]
    if first is None:
        if all(states[l] == "ok" for l in applicable):
            verdict, layer, conf, cands = "healthy", None, "high", []
        else:
            verdict, layer, conf = "undetermined", None, "low"
            cands = [l for l in applicable if states[l] == "unknown"]
    else:
        extra = sorted(set(ambiguous.get(first, [])) - {first}, key=LAYERS.index)
        if dns_symptom:
            unknown_before = []
        cands = sorted(set(unknown_before) | {first} | set(extra), key=LAYERS.index)
        layer = first
        if len(cands) == 1 and states[first] == "failed":
            verdict, conf = "localized", ("medium" if dns_symptom else "high")
        else:
            verdict, conf = "probable", "medium"
        if states[first] == "intermittent":
            notes.append(f"{first} has both working and failing observations; the fault is intermittent")
    missing = []
    for l in applicable:
        if states[l] == "unknown":
            missing.append(_MISSING[l].format(host=t["host"], port=t["port"], path=t["path"]))
        elif verdict != "localized" and l in cands and states[l] == "ok":
            missing.append(_CONFIRM[l].format(host=t["host"], answers=", ".join(ctx["answers"]) or "the address used"))
    actions = []
    seen = set()
    for f in findings:
        for a in _ACTIONS.get(f["code"], []):
            cmd = a.format(host=shlex.quote(t["host"]), port=t["port"], path=shlex.quote(t["path"]),
                           url=shlex.quote(f"{t['scheme']}://{t['host']}:{t['port']}{t['path']}"))
            if ctx["addr"]:
                cmd = cmd.replace("<address>", ctx["addr"])
            if ctx["resolver"]:
                cmd = cmd.replace("<resolver>", ctx["resolver"])
            if cmd not in seen:
                seen.add(cmd)
                actions.append(cmd)
    findings.sort(key=lambda f: (LAYERS.index(f["layer"]), f["code"], f["evidence"]))
    uniq = []
    for f in findings:
        if f not in uniq:
            uniq.append(f)
    if verdict in ("probable", "undetermined"):
        notes.append("uncertain: collect the missing evidence listed before acting on this result")
    return {
        "schema": REPORT_SCHEMA, "input_sha256": sha,
        "target": f"{t['scheme']}://{t['host']}:{t['port']}{t['path']}",
        "verdict": verdict, "layer": layer, "confidence": conf, "candidates": cands,
        "layers": {l: {"state": states[l], "evidence": sorted(set(L[l].ok + L[l].failed))} for l in LAYERS},
        "findings": uniq, "next_actions": actions, "missing_evidence": missing,
        "notes": sorted(set(notes)), "observations": len(trace["observations"]),
        "read_only": "offline analysis of the supplied trace; nothing was sent on the network or changed",
    }


_MISSING = {
    "dns": "a DNS lookup of {host} against each configured resolver (rcode and answers)",
    "route": "a TCP connect to the resolved address on port {port}, or a traceroute to it",
    "tls": "a TLS handshake with SNI {host}, including the certificate names, dates and trust result",
    "application": "an HTTP request for {path} with its status code",
}
_CONFIRM = {
    "dns": "confirmation that {answers} is the right address for {host} (authoritative lookup or config.expected_addresses)",
    "route": "the same attempt from a second network, to separate a middlebox on this path from the server",
    "tls": "a TLS handshake from a second network, to separate a middlebox from the server",
    "application": "an HTTP request from a second network",
}
_ACTIONS = {
    "DNS_NXDOMAIN": ["dig +norecurse {host} SOA  # read-only: does the zone hold the name?", "dig {host} @<another resolver>  # compare answers"],
    "DNS_SERVFAIL": ["dig +dnssec {host}  # read-only: DNSSEC or upstream failure?", "dig {host} @<another resolver>"],
    "DNS_REFUSED": ["check the resolver ACL allows this client (read-only review)"],
    "DNS_TIMEOUT": ["dig {host} @<resolver> +tries=1 +time=2  # is the resolver up?", "traceroute -n <resolver>  # is the path to it intact?"],
    "DNS_NO_ADDRESS": ["dig {host} A && dig {host} AAAA  # which record type is missing?"],
    "DNS_INCONSISTENT": ["dig {host} @<each resolver>  # find the stale or split-horizon view"],
    "DNS_WRONG_ADDRESS": ["dig {host} @<authoritative server>  # is the record stale or poisoned locally?"],
    "ROUTE_NO_MATCH": ["ip route get <address>  # read-only: confirm the missing route", "plan a route change in a change window with rollback; do not apply from this report"],
    "ROUTE_BLACKHOLE": ["ip route show type blackhole  # find who installed it"],
    "ROUTE_UNREACHABLE": ["ip route show type unreachable"],
    "ROUTE_PROHIBIT": ["ip route show type prohibit"],
    "ROUTE_GATEWAY_OFFLINK": ["ip addr && ip route  # the gateway must sit on a local network"],
    "ROUTE_PATH_LOSS": ["mtr -n -c 20 <address>  # where does loss start?"],
    "ROUTE_LOOP": ["traceroute -n <address>  # capture the loop for the router owner"],
    "ROUTE_UNREACHABLE_ICMP": [],
    "ROUTE_OR_FILTER_TIMEOUT": ["nc -vz -w 3 <address> {port}  # from a second network to split path from firewall", "review firewall/security-group rules for port {port} (read-only)"],
    "TCP_RESET": ["openssl s_client -connect <address>:{port} -servername {host} </dev/null  # where is the reset?"],
    "TLS_CERT_EXPIRED": ["openssl s_client -connect {host}:{port} -servername {host} </dev/null | openssl x509 -noout -dates", "renew the certificate through the owner's normal process"],
    "TLS_CERT_NOT_YET_VALID": ["check the client clock and the certificate notBefore"],
    "TLS_NAME_MISMATCH": ["openssl s_client -connect {host}:{port} -servername {host} </dev/null | openssl x509 -noout -ext subjectAltName", "confirm DNS points {host} at the server that owns this certificate"],
    "TLS_SNI_MISMATCH": ["check the client's server name setting: it must send {host} (openssl s_client -connect {host}:{port} -servername {host} </dev/null)"],
    "TLS_UNTRUSTED_CHAIN": ["openssl s_client -connect {host}:{port} -servername {host} -showcerts </dev/null  # missing intermediate?"],
    "TLS_PROTOCOL_MISMATCH": ["testssl.sh --protocols {host}:{port}  # read-only scan of supported versions"],
    "TLS_ALERT": ["openssl s_client -connect {host}:{port} -servername {host} -state </dev/null"],
    "TLS_HANDSHAKE_TIMEOUT": ["openssl s_client -connect {host}:{port} -servername {host} </dev/null  # from a second network: middlebox or server?"],
    "TLS_HANDSHAKE_RESET": ["openssl s_client -connect {host}:{port} -servername {host} </dev/null  # from a second network: middlebox or server?"],
    "TLS_HANDSHAKE_EOF": ["openssl s_client -connect {host}:{port} -servername {host} </dev/null"],
    "APP_NOT_LISTENING": ["on the server: ss -ltnp | grep :{port}  # is the service running and bound?"],
    "APP_SERVER_ERROR": ["read the service logs around the trace time", "curl -sS -o /dev/null -w '%{{http_code}}' {url}"],
    "APP_UPSTREAM_ERROR": ["read the proxy error log for the upstream it chose", "check the upstream service health directly"],
    "APP_CLIENT_ERROR": ["compare the request path, method and auth with the service docs (no network change needed)"],
    "APP_TIMEOUT": ["read the service logs for slow requests; check its dependencies"],
    "APP_RESET": ["read the proxy/service logs for aborted requests"],
}


# -- output ---------------------------------------------------------------------------

def render(report: Dict[str, Any]) -> str:
    r = report
    lines = [f"diagnosis: {r['verdict']}" + (f" at {r['layer']}" if r["layer"] else "") + f" (confidence {r['confidence']})",
             f"  target {r['target']}; {r['observations']} observations; input sha256 {r['input_sha256'][:16]}"]
    if r["candidates"]:
        lines.append(f"  candidate layers: {', '.join(r['candidates'])}")
    lines.append("  layers: " + ", ".join(f"{l}={r['layers'][l]['state']}" for l in LAYERS))
    lines += [f"  finding {f['code']} ({f['layer']}): {f['detail']}" for f in r["findings"]]
    lines += [f"  note: {n}" for n in r["notes"]]
    lines += [f"  missing evidence: {m}" for m in r["missing_evidence"]]
    lines += [f"  next (read-only, not run): {a}" for a in r["next_actions"]]
    return "\n".join(lines) + "\n"


def _write_atomic(out: Path, data: bytes, inputs: List[Path]) -> None:
    out = Path(os.path.abspath(out))
    if out.is_symlink() or (out.exists() and not out.is_file()):
        raise Invalid(f"--out {out.name}: exists and is not a regular file; not replaced")
    for p in inputs:
        if out.exists() and p.exists() and os.path.samefile(out, p):
            raise Invalid("--out must not be one of the input traces")
    if not out.parent.is_dir():
        raise Invalid(f"--out: directory {out.parent.name} does not exist")
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


def diagnose_file(path: str) -> Dict[str, Any]:
    trace, sha = load_trace(Path(path))
    return analyse(trace, sha)


def _batch_one(p: str) -> Tuple[str, Optional[Dict[str, Any]], Optional[str]]:
    try:
        return Path(p).name, diagnose_file(p), None
    except Invalid as exc:
        return Path(p).name, None, str(exc)


def batch(directory: str, workers: int = 1) -> Dict[str, Any]:
    d = Path(directory)
    if d.is_symlink() or not d.is_dir():
        raise Invalid(f"{d.name}: not a directory")
    files = sorted(p for p in d.iterdir() if p.suffix == ".json" and not p.name.startswith("."))
    if len(files) > MAX_BATCH_FILES:
        raise Invalid(f"{d.name}: more than {MAX_BATCH_FILES} traces")
    if workers > 1:
        with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as ex:
            results = list(ex.map(_batch_one, [str(p) for p in files], chunksize=32))
    else:
        results = [_batch_one(str(p)) for p in files]
    reports, invalid, counts = {}, {}, {}
    for name, rep, err in results:
        if err:
            invalid[name] = err
        else:
            reports[name] = rep
            key = rep["verdict"] + (f":{rep['layer']}" if rep["layer"] else "")
            counts[key] = counts.get(key, 0) + 1
    return {"schema": BATCH_SCHEMA, "traces": len(files), "counts": dict(sorted(counts.items())),
            "invalid": invalid, "reports": reports}


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="netdiag.py", description="Offline network failure localization from a trace.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("diagnose", help="analyse one trace file")
    d.add_argument("trace")
    b = sub.add_parser("batch", help="analyse every *.json trace in a directory")
    b.add_argument("directory")
    b.add_argument("--workers", type=int, default=1)
    for p in (d, b):
        p.add_argument("--json", action="store_true", help="print the JSON report")
        p.add_argument("--out", help="also write the JSON report here, atomically")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "diagnose":
            rep = diagnose_file(a.trace)
            inputs = [Path(a.trace)]
            code = 0 if rep["verdict"] == "healthy" else 1
            text = render(rep)
        else:
            if not 1 <= a.workers <= 32:
                raise Invalid("--workers must be 1..32")
            rep = batch(a.directory, a.workers)
            inputs = [Path(a.directory) / n for n in rep["reports"]]
            code = 2 if rep["invalid"] and not rep["reports"] else (0 if set(rep["counts"]) <= {"healthy"} and not rep["invalid"] else 1)
            text = (f"batch: {rep['traces']} traces; " + ", ".join(f"{k}={v}" for k, v in rep["counts"].items())
                    + (f"; invalid={len(rep['invalid'])}" if rep["invalid"] else "") + "\n"
                    + "".join(f"  invalid {n}: {e}\n" for n, e in sorted(rep["invalid"].items())))
        data = (json.dumps(rep, indent=2, sort_keys=True) + "\n").encode("utf-8")
        if a.out:
            _write_atomic(Path(a.out), data, inputs)
    except Invalid as exc:
        msg = {"schema": REPORT_SCHEMA, "verdict": "invalid", "error": str(exc)}
        sys.stdout.write(json.dumps(msg, sort_keys=True) + "\n" if a.json else f"invalid: {exc}\nnothing written\n")
        return 2
    sys.stdout.write(data.decode("utf-8") if a.json else text)
    return code


if __name__ == "__main__":
    sys.exit(main())
