#!/usr/bin/env python3
"""M10 network-diagnosis oracle (written for M10; independent of the builder's diagnosis_oracle.py
and tests). Derived from the G10/M10 acceptance text: correct known-failure localization; incomplete
trace stays bounded uncertainty; output reproducible from the same trace; cites actual fields; does
not turn missing evidence into certainty; offline only. Interface from offline-trace-diagnosis.md:
  <cmd> diagnose TRACE [--json] [--out FILE]   exit 0 healthy, 1 fault/undetermined, 2 invalid
  <cmd> batch DIR [--workers N] [--json]
Every trace is synthetic (documentation address ranges, .example names); nothing touches a network.
Usage: python m10_oracle.py [--only O1,O6] -- <candidate prefix...>"""
import copy
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
INJECT = HERE / "inject"
CMD = []
A = "198.51.100.77"
HOST = "api.shop.example"


class Fail(Exception):
    pass


def need(c, m):
    if not c:
        raise Fail(m)


def env(extra=None):
    e = {k: v for k, v in os.environ.items() if not k.startswith("M10_")}
    e["PYTHONDONTWRITEBYTECODE"] = "1"
    e.update(extra or {})
    return e


def run(*args, extra=None, cwd=None, timeout=120):
    try:
        p = subprocess.run(CMD + [str(a) for a in args], capture_output=True, text=True, env=env(extra), cwd=cwd, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise Fail(f"candidate did not finish in {timeout}s")
    return p.returncode, p.stdout, p.stderr


# ------------------------------------------------------------------ trace builders

def cert(san=None, nb="2026-01-01T00:00:00Z", na="2027-01-01T00:00:00Z", trusted=True):
    return {"san": [HOST] if san is None else san, "not_before": nb, "not_after": na, "chain_trusted": trusted}


def dns(rcode="NOERROR", answers=None, resolver="10.20.0.2", qname=HOST):
    return {"stage": "dns", "qname": qname, "resolver": resolver, "rcode": rcode,
            "answers": ([A] if answers is None else answers) if rcode == "NOERROR" else []}


def tcp(result="connected", dst=A, port=443):
    return {"stage": "tcp", "dst": dst, "port": port, "result": result}


def tls(result="ok", c="default", alert=None, sni=HOST, dst=A):
    o = {"stage": "tls", "dst": dst, "sni": sni, "result": result, "cert": cert() if c == "default" else c}
    if alert:
        o["alert"] = alert
    return o


def http(status=200, via_proxy=False, result=None):
    o = {"stage": "http"}
    if result:
        o["result"] = result
    else:
        o["status"] = status
    if via_proxy:
        o["via_proxy"] = True
    return o


def trace(obs, host=HOST, scheme="https", expected=(A,), routes=None, captured="2026-10-18T16:00:00Z"):
    t = {"schema": "solaris.net-trace/1",
         "target": {"host": host, "scheme": scheme, "port": 443 if scheme == "https" else 80, "path": "/health"},
         "config": {"resolvers": ["10.20.0.2", "10.20.0.3"], "addresses": [{"dev": "eth0", "cidr": "10.20.0.15/24"}],
                    "routes": routes or [{"dst": "default", "via": "10.20.0.1", "dev": "eth0"}],
                    "expected_addresses": list(expected)},
         "observations": obs}
    if captured:
        t["captured_at"] = captured
    return t


def healthy_obs():
    return [dns(), tcp(), tls(), http(200)]


class Work:
    def __init__(self, tmp):
        self.tmp = tmp
        self.n = 0
        self.reports = []  # (trace, report) for the citation check

    def write(self, doc, name=None, raw=None):
        self.n += 1
        d = self.tmp / f"t{self.n}"
        d.mkdir()
        p = d / (name or "trace.json")
        if raw is not None:
            p.write_bytes(raw)
        else:
            p.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
        return p

    def diagnose(self, doc, keep=True):
        p = self.write(doc)
        rc, out, err = run("diagnose", p, "--json")
        try:
            rep = json.loads(out)
        except ValueError:
            raise Fail(f"no JSON report (rc={rc}): {(out + err)[-200:]}")
        if keep:
            self.reports.append((doc, rep))
        return rc, rep


def codes(rep):
    return [f.get("code") for f in rep.get("findings", [])]


def states(rep):
    return {l: v.get("state") for l, v in rep.get("layers", {}).items()}


# ------------------------------------------------------------------ checks

def o1_clean_controls(w):
    rc, rep = w.diagnose(trace(healthy_obs()))
    need(rc == 0 and rep.get("verdict") == "healthy", f"https clean control: rc={rc} verdict={rep.get('verdict')}")
    need(all(s == "ok" for s in states(rep).values()) and not codes(rep), f"https clean control layers {states(rep)} findings {codes(rep)}")
    rc, rep = w.diagnose(trace([dns(), tcp(port=80), http(200)], scheme="http"))
    need(rc == 0 and rep.get("verdict") == "healthy", f"http clean control: rc={rc} verdict={rep.get('verdict')}")
    need(states(rep).get("tls") == "not_applicable", f"http control: tls state {states(rep).get('tls')}")
    rc, rep = w.diagnose(trace([tcp(), tls(sni=None, c=cert(san=["IP:" + A])), http(200)], host=A))
    need(rc == 0 and rep.get("verdict") == "healthy", f"IP-literal clean control: rc={rc} verdict={rep.get('verdict')} {codes(rep)}")
    mixed = "API.Shop.Example"
    rc, rep = w.diagnose(trace([dns(qname=mixed), tcp(), tls(sni=mixed), http(200)], host=mixed))
    need(rc == 0 and rep.get("verdict") == "healthy", f"mixed-case target host: rc={rc} verdict={rep.get('verdict')} {codes(rep)}")
    return "https, http, IP-literal and mixed-case targets: healthy, exit 0, every layer ok, no findings"


LOCALIZE = [
    ("dns NXDOMAIN", lambda: [dns("NXDOMAIN"), dns("NXDOMAIN", resolver="10.20.0.3")], None, "dns", "DNS_NXDOMAIN"),
    ("dns SERVFAIL", lambda: [dns("SERVFAIL"), dns("SERVFAIL", resolver="10.20.0.3")], None, "dns", "DNS_"),
    ("route blackhole", lambda: [dns(), tcp("timeout")], [{"dst": "default", "via": "10.20.0.1", "dev": "eth0"},
                                                         {"dst": "198.51.100.0/24", "type": "blackhole"}], "route", "ROUTE"),
    ("tls expired", lambda: [dns(), tcp(), tls("alert", cert(na="2026-06-01T00:00:00Z"), "certificate_expired")], None, "tls", "TLS_CERT_EXPIRED"),
    ("tls not yet valid", lambda: [dns(), tcp(), tls("alert", cert(nb="2026-12-01T00:00:00Z"), "bad_certificate")], None, "tls", "TLS_CERT_NOT_YET_VALID"),
    ("tls name mismatch, DNS verified", lambda: [dns(), tcp(), tls("alert", cert(san=["DNS:legacy.hosting.example"]), "bad_certificate")], None, "tls", "TLS_NAME_MISMATCH"),
    ("tls untrusted chain", lambda: [dns(), tcp(), tls("alert", cert(trusted=False), "unknown_ca")], None, "tls", "TLS_UNTRUSTED_CHAIN"),
    ("tcp refused", lambda: [dns(), tcp("refused")], None, "application", "APP_NOT_LISTENING"),
    ("http 503 via proxy", lambda: healthy_obs()[:3] + [http(503, via_proxy=True)], None, "application", "APP_UPSTREAM_ERROR"),
    ("http 500", lambda: healthy_obs()[:3] + [http(500)], None, "application", "APP_SERVER_ERROR"),
    ("http timeout", lambda: healthy_obs()[:3] + [http(result="timeout")], None, "application", "APP_"),
]


def o2_localization(w):
    done = []
    for label, obs, routes, layer, code in LOCALIZE:
        rc, rep = w.diagnose(trace(obs(), routes=routes))
        need(rc == 1, f"{label}: exit {rc}, expected 1")
        need(rep.get("verdict") == "localized" and rep.get("layer") == layer,
             f"{label}: verdict={rep.get('verdict')} layer={rep.get('layer')}, expected localized at {layer} ({codes(rep)})")
        need(any(c.startswith(code) for c in codes(rep)), f"{label}: findings {codes(rep)} lack {code}")
        need(all(f.get("layer") == layer for f in rep.get("findings", []) if f.get("code", "").startswith(code)),
             f"{label}: finding {code} attributed to layer {[f.get('layer') for f in rep['findings']]}, expected {layer}")
        order = ["dns", "route", "tls", "application"]
        # a refused TCP connection never reaches TLS, so only dns and route must be proven there
        must_ok = ["dns", "route"] if label == "tcp refused" else order[:order.index(layer)]
        for l in must_ok:
            need(states(rep).get(l) == "ok", f"{label}: earlier layer {l} is {states(rep).get(l)}, not ok")
        if label == "tcp refused":
            need(states(rep).get("tls") in ("not_reached", "unknown"), f"tcp refused: tls state {states(rep).get('tls')}")
        done.append(label)
    return f"{len(done)} known failures localized at the right layer with the right code; earlier layers ok"


def o3_bounded_uncertainty(w):
    rc, rep = w.diagnose(trace([]))
    need(rc == 1 and rep.get("verdict") == "undetermined", f"empty trace: rc={rc} verdict={rep.get('verdict')}")
    need(len(rep.get("missing_evidence", [])) >= 4, f"empty trace: missing_evidence {rep.get('missing_evidence')}")
    rc, rep = w.diagnose(trace([dns()]))
    need(rc == 1 and rep.get("verdict") == "undetermined" and rep.get("missing_evidence"),
         f"dns-only trace: rc={rc} verdict={rep.get('verdict')} missing={rep.get('missing_evidence')}")
    rc, rep = w.diagnose(trace([tls("alert", cert(na="2026-06-01T00:00:00Z"), "certificate_expired")]))
    need(rep.get("verdict") == "probable" and "tls" in rep.get("candidates", []) and len(rep.get("candidates", [])) > 1,
         f"expired cert with no dns/tcp evidence: verdict={rep.get('verdict')} candidates={rep.get('candidates')}")
    rc, rep = w.diagnose(trace([dns(), tcp(), tls("alert", cert(san=["DNS:legacy.hosting.example"]), "bad_certificate")], expected=()))
    need(rep.get("verdict") == "probable" and {"dns", "tls"} <= set(rep.get("candidates", [])),
         f"name mismatch with unverified DNS: verdict={rep.get('verdict')} candidates={rep.get('candidates')}")
    rc, rep = w.diagnose(trace([dns(), tcp(), tls("reset", None)]))
    need(rep.get("verdict") == "probable" and "route" in rep.get("candidates", []),
         f"handshake reset (middlebox possible): verdict={rep.get('verdict')} candidates={rep.get('candidates')}")
    rc, rep = w.diagnose(trace([dns(), dns("NXDOMAIN", resolver="10.20.0.3")] + healthy_obs()[1:]))
    need(rep.get("verdict") != "localized" and states(rep).get("dns") == "intermittent",
         f"contrary dns evidence: verdict={rep.get('verdict')} dns={states(rep).get('dns')}")
    # certificate dates are judged against captured_at, never the wall clock
    rc, rep = w.diagnose(trace([dns(), tcp(), tls("alert", cert(nb="2018-01-01T00:00:00Z", na="2020-01-01T00:00:00Z"), "bad_certificate")],
                               captured="2019-06-01T00:00:00Z"))
    need("TLS_CERT_EXPIRED" not in codes(rep), "cert valid at captured_at (2019) but called expired: wall clock used")
    rc, rep = w.diagnose(trace([dns(), tcp(), tls("alert", cert(nb="2026-01-01T00:00:00Z", na="2040-01-01T00:00:00Z"), "certificate_expired")],
                               captured="2041-01-01T00:00:00Z"))
    need("TLS_CERT_EXPIRED" in codes(rep), "cert expired at captured_at (2041) not reported")
    rc, rep = w.diagnose(trace([dns(), tcp(), tls("alert", cert(na="2020-01-01T00:00:00Z"), "bad_certificate")], captured=None))
    need("TLS_CERT_EXPIRED" not in codes(rep), "no captured_at, yet the certificate was judged expired")
    rc, rep = w.diagnose(trace([dns(), tcp("timeout"), tcp("connected")] + healthy_obs()[2:]))
    need(rep.get("verdict") != "localized", f"connected and timed-out TCP to the same address: verdict {rep.get('verdict')}")
    return ("empty and dns-only traces undetermined; expired cert without lower evidence, unverified name mismatch and "
            "handshake reset stay probable with extra candidates; contrary DNS and TCP intermittent; dates judged at captured_at only")


def _norm(rep):
    r = copy.deepcopy(rep)
    r.pop("input_sha256", None)
    return json.dumps(r, sort_keys=True)


def o4_reproducible(w):
    docs = [trace(healthy_obs()), trace(LOCALIZE[5][1]()), trace([dns(), dns("NXDOMAIN", resolver="10.20.0.3"), tcp(), tcp("timeout")]),
            trace([dns(answers=["198.51.100.9", A, "198.51.100.3"]), tcp(), tls("alert", cert(san=["b.example", "a.example", "DNS:c.example"]), "bad_certificate")])]
    rnd = random.Random(10)
    for i, doc in enumerate(docs):
        p = w.write(doc)
        outs = set()
        for seed in ("0", "1", "4242"):
            for tz in ("UTC", "America/Los_Angeles", "Asia/Kolkata"):
                rc, out, _ = run("diagnose", p, "--json", extra={"PYTHONHASHSEED": seed, "TZ": tz})
                outs.add(out)
        need(len(outs) == 1, f"trace {i}: {len(outs)} different outputs across PYTHONHASHSEED/TZ")
        base = json.loads(outs.pop())
        for k in range(3):
            d2 = copy.deepcopy(doc)
            rnd.shuffle(d2["observations"])
            for o in d2["observations"]:
                if o.get("answers"):
                    rnd.shuffle(o["answers"])
                if o.get("cert"):
                    rnd.shuffle(o["cert"]["san"])
            raw = json.dumps(dict(reversed(list(d2.items()))), indent=k).encode()
            p2 = w.write(None, raw=raw)
            rc, out, _ = run("diagnose", p2, "--json")
            need(_norm(json.loads(out)) == _norm(base), f"trace {i}: reordered observations/keys changed the report")
        outp = p.parent / "report.json"
        rc, out, _ = run("diagnose", p, "--json", "--out", outp)
        need(outp.read_text() == out or json.loads(outp.read_text()) == json.loads(out), f"trace {i}: --out differs from stdout")
    bd = w.tmp / "batch"
    bd.mkdir()
    for i, doc in enumerate(docs * 10):
        (bd / f"{i:03d}.json").write_text(json.dumps(doc))
    r1 = run("batch", bd, "--json")
    r4 = run("batch", bd, "--workers", "4", "--json")
    need(r1[1] == r4[1] and r1[0] == r4[0], "batch --workers 1 and --workers 4 differ")
    b = json.loads(r1[1])
    need(b.get("traces") == 40 and len(b.get("reports", {})) == 40, f"batch report counts {b.get('traces')}/{len(b.get('reports', {}))}")
    for name, rep in b["reports"].items():
        need(_norm(rep) == _norm(json.loads(run("diagnose", bd / name, "--json")[1])), f"batch report for {name} differs from diagnose")
    return "same bytes across 3 hash seeds x 3 TZ; reordered observations, answers, SANs and keys give the same report; --out equals stdout; batch workers 1 = 4 = diagnose"


IP_RE = re.compile(r"(?<![\w.:])(\d{1,3}(?:\.\d{1,3}){3})(?![\w.])")
NAME_RE = re.compile(r"\b((?:[a-z0-9-]+\.)+(?:example|test|invalid|com|org|net|uk))\b", re.I)


def o5_cites_actual_fields(w):
    checked = 0
    for doc, rep in w.reports:
        text = json.dumps(doc).lower()
        lines = list(rep.get("missing_evidence", [])) + list(rep.get("next_actions", []))
        for f in rep.get("findings", []):
            lines += [f.get("detail", ""), f.get("evidence", "")]
        for l in rep.get("layers", {}).values():
            lines += l.get("evidence", [])
        for line in lines:
            for ip in IP_RE.findall(line):
                need(ip in text, f"output cites address {ip} that is not in the trace: {line[:140]}")
            for name in NAME_RE.findall(line):
                need(name.lower() in text, f"output cites name {name} that is not in the trace: {line[:140]}")
            checked += 1
        for f in rep.get("findings", []):
            ev = f.get("evidence", "")
            need(ev and any(ev in e for l in rep["layers"].values() for e in l.get("evidence", [])) or ev.startswith("config"),
                 f"finding {f.get('code')} evidence {ev!r} is not one of the layer evidence lines")
    need(checked > 50, f"only {checked} lines checked")
    return f"{checked} output lines from {len(w.reports)} reports: every address and name cited appears in the trace; findings point at listed evidence"


SAN_COVER = [
    ("DNS:", HOST, ["DNS:" + HOST]), ("dns: lower", HOST, ["dns:" + HOST]), ("spaced", HOST, ["Dns : " + HOST]),
    ("bare", HOST, [HOST]), ("upper value", HOST, ["DNS:API.SHOP.EXAMPLE"]), ("san trailing dot", HOST, ["DNS:" + HOST + "."]),
    ("host trailing dot", HOST + ".", ["DNS:" + HOST]), ("wildcard one label", HOST, ["DNS:*.shop.example"]),
    ("bare wildcard", HOST, ["*.shop.example"]), ("A-label", "xn--bcher-kva.example", ["DNS:xn--bcher-kva.example"]),
    ("IP:", A, ["IP:" + A]), ("IP Address:", A, ["IP Address:" + A]), ("bare ip", A, [A]),
    ("IPv6 long form", "2001:db8::1", ["IP Address:2001:DB8:0:0:0:0:0:1"]), ("second entry", HOST, ["DNS:a.example", "DNS:" + HOST]),
]
SAN_REJECT = [
    ("other name", HOST, ["DNS:other.example"]), ("two labels deep", "a." + HOST, ["DNS:*.shop.example"]),
    ("apex", "shop.example", ["DNS:*.shop.example"]), ("partial w*", "web.shop.example", ["DNS:w*.shop.example"]),
    ("partial *eb", "web.shop.example", ["DNS:*eb.shop.example"]), ("partial xn--*", "xn--bcher-kva.example", ["DNS:xn--*.example"]),
    ("double wildcard", "a.b.shop.example", ["DNS:*.*.shop.example"]), ("DNS:<ip> for IP", A, ["DNS:" + A]), ("IP: for a name", HOST, ["IP:" + HOST]),
    ("mapped v6", A, ["IP:::ffff:" + A]), ("suffix not label", "evilshop.example", ["DNS:shop.example"]),
]
# sibling strictness rules beyond the documented forms: no wildcard directly over a TLD or public
# suffix, and no non-ASCII SAN text folded into an ASCII name
SAN_STRICT = [
    ("wildcard over TLD", "web.example", ["DNS:*.example"]), ("wildcard over .com", "shop.com", ["*.com"]),
    ("KELVIN SIGN homoglyph", "kelvin.example", ["DNS:\u212aelvin.example"]),
]


def _mismatch(w, host, san):
    is_ip = ":" in host or host.replace(".", "").isdigit()
    obs = ([] if is_ip else [dns(qname=host)]) + [tcp(dst=A if not ":" in host else host),
                                                  tls("alert", cert(san=san), "bad_certificate", sni=None if is_ip else host, dst=A if not ":" in host else host)]
    rc, rep = w.diagnose(trace(obs, host=host, expected=(A,)))
    return "TLS_NAME_MISMATCH" in codes(rep), rep


def o6a_san_documented(w):
    bad = []
    for label, host, san in SAN_COVER:
        m, rep = _mismatch(w, host, san)
        if m:
            bad.append(f"{label}: {san} should cover {host}")
    for label, host, san in SAN_REJECT:
        m, rep = _mismatch(w, host, san)
        if not m:
            bad.append(f"{label}: {san} must not cover {host}")
    need(not bad, "; ".join(bad))
    return f"{len(SAN_COVER)} covering and {len(SAN_REJECT)} non-covering documented SAN forms judged correctly"


def o6b_san_strict(w):
    bad = [f"{label}: {san} must not cover {host}" for label, host, san in SAN_STRICT if not _mismatch(w, host, san)[0]]
    need(not bad, "; ".join(bad))
    return f"{len(SAN_STRICT)} TLD/public-suffix wildcard and homoglyph SANs refused"


def o7_invalid_input(w):
    good = json.dumps(trace(healthy_obs()))
    variants = {
        "duplicate key": good.replace('"schema"', '"schema": "solaris.net-trace/1", "schema"', 1),
        "NaN": good.replace('"port": 443', '"port": NaN', 1),
        "wrong schema": good.replace("solaris.net-trace/1", "solaris.net-trace/9"),
        "no zone": good.replace("2026-10-18T16:00:00Z", "2026-10-18T16:00:00"),
        "bad address": good.replace('"dst": "198.51.100.77"', '"dst": "198.51.100.777"', 1),
        "unknown stage": good.replace('"stage": "http"', '"stage": "smtp"'),
        "not an object": "[]",
        "truncated": good[:-5],
        "too many observations": json.dumps(trace([tcp() for _ in range(10001)])),
    }
    out_bad = []
    for label, raw in variants.items():
        p = w.write(None, raw=raw.encode())
        outp = p.parent / "report.json"
        rc, out, err = run("diagnose", p, "--json", "--out", outp)
        if rc != 2 or outp.exists() or "Traceback" in err:
            out_bad.append(f"{label}: rc={rc} out_written={outp.exists()} traceback={'Traceback' in err}")
    p = w.write(json.loads(good))
    link = p.parent / "link.json"
    os.symlink(p, link)
    rc, out, err = run("diagnose", link, "--json", "--out", p.parent / "r.json")
    if rc != 2 or (p.parent / "r.json").exists():
        out_bad.append(f"symlinked trace: rc={rc}")
    big = w.write(None, raw=b'{"schema": "solaris.net-trace/1", "pad": "' + b"x" * (8 * 1024 * 1024 + 10) + b'"}')
    rc, out, err = run("diagnose", big, "--json")
    if rc != 2:
        out_bad.append(f">8 MiB: rc={rc}")
    need(not out_bad, "; ".join(out_bad))
    return f"{len(variants) + 2} invalid traces: exit 2, no traceback, --out never written"


def o8_offline(w):
    log = w.tmp / "net.log"
    extra = {"M10_NET_LOG": str(log), "PYTHONPATH": str(INJECT)}
    bd = w.tmp / "offline-batch"
    bd.mkdir()
    for i, (label, obs, routes, layer, code) in enumerate(LOCALIZE):
        (bd / f"{i:02d}.json").write_text(json.dumps(trace(obs(), routes=routes)))
    for f in sorted(bd.iterdir()):
        rc, out, err = run("diagnose", f, "--json", extra=extra)
        need(rc in (0, 1) and out.strip(), f"diagnose {f.name} failed with the network blocked: rc={rc} {err[-150:]}")
    rc, out, err = run("batch", bd, "--workers", "2", "--json", extra=extra)
    need(rc in (0, 1) and out.strip(), f"batch failed with the network blocked: rc={rc}")
    rc, out, err = run("diagnose", bd / "00.json", extra={"PYTHONPATH": str(INJECT), "M10_NET_LOG": str(log)})
    need(not log.exists(), f"candidate attempted network calls: {log.read_text()[:300] if log.exists() else ''}")
    return f"{len(LOCALIZE)} diagnoses and a 2-worker batch with sockets and DNS blocked: zero network attempts"


def o9_no_side_writes(w):
    p = w.write(trace(healthy_obs()))
    cwd = w.tmp / "cwd"
    cwd.mkdir()
    before = sorted(os.listdir(p.parent)), p.read_bytes()
    run("diagnose", p, cwd=cwd)
    run("diagnose", p, "--json", cwd=cwd)
    run("batch", p.parent, cwd=cwd)
    need((sorted(os.listdir(p.parent)), p.read_bytes()) == before and not os.listdir(cwd), "diagnose/batch wrote files")
    outp = p.parent / "r.json"
    outp.write_text("old")
    rc, out, err = run("diagnose", p, "--json", "--out", outp)
    need(json.loads(outp.read_text()) == json.loads(out), "--out did not replace the old report")
    need(sorted(os.listdir(p.parent)) == sorted(before[0] + ["r.json"]), f"--out left temp files: {os.listdir(p.parent)}")
    rc, out, err = run("diagnose", p, "--json", "--out", p)
    need(rc == 2 and p.read_bytes() == before[1], "--out pointing at the input trace was not refused")
    return "no files written without --out; --out replaces atomically with no temp leftovers; --out onto the input refused"


CHECKS = [o1_clean_controls, o2_localization, o3_bounded_uncertainty, o4_reproducible, o5_cites_actual_fields,
          o6a_san_documented, o6b_san_strict, o7_invalid_input, o8_offline, o9_no_side_writes]


def main(argv):
    global CMD
    if "--" not in argv:
        print(__doc__)
        return 2
    i = argv.index("--")
    opts, CMD = argv[:i], argv[i + 1:]
    only = set(opts[opts.index("--only") + 1].upper().split(",")) if "--only" in opts else None
    tmp = Path(tempfile.mkdtemp(prefix="m10-oracle-")).resolve()
    w = Work(tmp)
    passed = failed = 0
    print(f"# m10_oracle candidate: {' '.join(CMD)}")
    try:
        for chk in CHECKS:
            if only and chk.__name__.split("_")[0].upper() not in only:
                continue
            t0 = time.time()
            try:
                msg = chk(w)
                passed += 1
                print(f"PASS {chk.__name__} ({time.time() - t0:.1f}s): {msg}")
            except Fail as exc:
                failed += 1
                print(f"FAIL {chk.__name__}: {exc}")
            except Exception as exc:
                failed += 1
                print(f"FAIL {chk.__name__}: {type(exc).__name__}: {str(exc)[:300]}")
            sys.stdout.flush()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    total = passed + failed
    verdict = "ACCEPTS" if failed == 0 and total else "REJECTS"
    print(f"SUMMARY {passed}/{total} pass; oracle {verdict} candidate")
    return 0 if verdict == "ACCEPTS" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
