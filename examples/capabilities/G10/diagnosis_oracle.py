#!/usr/bin/env python3
"""G10 oracle: does a candidate localize network failures from inspectable evidence?

Usage: diagnosis_oracle.py [--seed N] -- <candidate command...>
The candidate is called as `<cmd> diagnose TRACE --json [--out FILE]` and
`<cmd> batch DIR --json --workers N`. Traces are generated here from a seed, with names and
addresses the shipped fixtures do not use, so a candidate cannot pass by memorising fixtures.
Every check reads the JSON verdict; exit code 0 alone proves nothing, so a no-op fails.
"""
import hashlib, json, os, random, subprocess, sys, tempfile, time
from pathlib import Path

def gen(rng):
    """Return a dict of named trace builders using fresh synthetic names/addresses."""
    label = "".join(rng.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(7))
    host = f"{label}.svc.example"
    ip = f"198.51.100.{rng.randint(20, 200)}"
    other = f"192.0.2.{rng.randint(20, 200)}"
    res = f"10.{rng.randint(30, 90)}.0.53"
    cfg = {"resolvers": [res], "addresses": [{"dev": "en0", "cidr": f"{res.rsplit('.', 1)[0]}.9/24"}],
           "routes": [{"dst": "default", "via": f"{res.rsplit('.', 1)[0]}.1", "dev": "en0"}], "expected_addresses": [ip]}
    cert = {"san": [host], "not_before": "2025-01-01T00:00:00Z", "not_after": "2027-06-01T00:00:00Z", "chain_trusted": True}
    def tr(obs, captured="2026-09-01T12:00:00Z", c=cfg, port=443):
        return {"schema": "solaris.net-trace/1", "captured_at": captured, "config": c,
                "target": {"host": host, "scheme": "https", "port": port, "path": "/v1/ping"}, "observations": obs}
    dns = {"stage": "dns", "qname": host, "resolver": res, "rcode": "NOERROR", "answers": [ip]}
    tcp = {"stage": "tcp", "dst": ip, "port": 443, "result": "connected"}
    tls = {"stage": "tls", "dst": ip, "sni": host, "result": "ok", "cert": cert}
    http = lambda s: {"stage": "http", "status": s, "headers": {"Authorization": "Bearer ORACLE-CANARY-7731", "Server": "x"}}
    b = {
        "clean": tr([dns, tcp, tls, http(204)]),
        "dns_servfail": tr([dict(dns, rcode="SERVFAIL", answers=[])]),
        "dns_nxdomain": tr([dict(dns, rcode="NXDOMAIN", answers=[])]),
        "route_noroute": tr([dns, dict(tcp, result="timeout")], c=dict(cfg, routes=[])),
        "route_unreach": tr([dns, dict(tcp, result="unreachable")]),
        "tls_untrusted": tr([dns, tcp, dict(tls, result="alert", alert="unknown_ca", cert=dict(cert, chain_trusted=False))]),
        "tls_expired_by_capture": tr([dns, tcp, dict(tls, result="alert", alert="certificate_expired",
                                      cert=dict(cert, not_after="2030-01-01T00:00:00Z"))], captured="2031-03-01T00:00:00Z"),
        "valid_at_capture": tr([dns, tcp, dict(tls, cert=dict(cert, not_after="2025-06-01T00:00:00Z")), http(200)],
                               captured="2025-03-01T00:00:00Z"),
        "app_500": tr([dns, tcp, tls, http(500)]),
        "app_refused": tr([dns, dict(tcp, result="refused")]),
        "incomplete_dns_only": tr([dns]),
        "tls_reset_no_dns": tr([tcp, dict(tls, result="reset", cert=None)]),
        "icmp_filtered_ok": tr([dns, {"stage": "route", "dst": ip, "reached": False, "hops": [{"ttl": 1, "addr": None}]}, tcp, tls, http(200)]),
        "wrong_answer": tr([dict(dns, answers=[other]), dict(tcp, dst=other), dict(tls, dst=other, result="alert", alert="bad_certificate",
                            cert=dict(cert, san=["old.parking.example"]))]),
    }
    return b

EXPECT = {  # name -> (verdict set, layer, required candidates, forbidden candidates)
    "clean": ({"healthy"}, None, set(), {"dns", "route", "tls", "application"}),
    "dns_servfail": ({"localized"}, "dns", {"dns"}, {"route", "tls", "application"}),
    "dns_nxdomain": ({"localized"}, "dns", {"dns"}, {"route", "tls", "application"}),
    "route_noroute": ({"localized"}, "route", {"route"}, {"dns", "tls", "application"}),
    "route_unreach": ({"localized"}, "route", {"route"}, {"dns", "tls", "application"}),
    "tls_untrusted": ({"localized"}, "tls", {"tls"}, {"dns", "route", "application"}),
    "tls_expired_by_capture": ({"localized"}, "tls", {"tls"}, {"route", "application"}),
    "valid_at_capture": ({"healthy"}, None, set(), {"tls"}),
    "app_500": ({"localized"}, "application", {"application"}, {"dns", "route", "tls"}),
    "app_refused": ({"localized"}, "application", {"application"}, {"dns", "route"}),
    "incomplete_dns_only": ({"undetermined"}, None, {"route", "tls", "application"}, {"dns"}),
    "tls_reset_no_dns": ({"probable", "undetermined"}, "tls", {"dns", "tls"}, {"application"}),
    "icmp_filtered_ok": ({"healthy"}, None, set(), {"route"}),
    "wrong_answer": ({"localized", "probable"}, "dns", {"dns"}, {"application"}),
}

def main():
    argv = sys.argv[1:]
    seed = 1010
    if argv[:1] == ["--seed"]:
        seed = int(argv[1]); argv = argv[2:]
    if argv[:1] != ["--"] or len(argv) < 2:
        sys.exit(__doc__)
    cmd = argv[1:]
    rng = random.Random(seed)
    results = []
    def check(name, ok, detail):
        results.append(ok); print(("PASS " if ok else "FAIL ") + f"{name}: {detail}")
    with tempfile.TemporaryDirectory(prefix="g10-oracle-") as tmp:
        base = Path(tmp)
        guard = base / "guard"; guard.mkdir(); audit = base / "net-audit.txt"
        (guard / "sitecustomize.py").write_text(
            "import socket\n"
            f"_A = {str(audit)!r}\n"
            "def _deny(*a, **k):\n    open(_A, 'a').write('network call\\n'); raise OSError('network disabled by G10 oracle')\n"
            "class _S:\n    def __init__(self, *a, **k): _deny()\n"
            "socket.socket = _S; socket.create_connection = _deny; socket.getaddrinfo = _deny; socket.gethostbyname = _deny\n")
        env = dict(os.environ, PYTHONPATH=str(guard), PYTHONDONTWRITEBYTECODE="1")
        def run(*args, timeout=120):
            p = subprocess.run(cmd + list(args), capture_output=True, text=True, env=env, timeout=timeout)
            try:
                return p.returncode, json.loads(p.stdout), p.stdout
            except ValueError:
                return p.returncode, None, p.stdout
        traces = gen(rng)
        tdir = base / "traces"; tdir.mkdir()
        for n, d in traces.items():
            (tdir / f"{n}.json").write_text(json.dumps(d, indent=1))
        snap = {p.name: p.read_bytes() for p in tdir.iterdir()}
        reps = {n: run("diagnose", str(tdir / f"{n}.json"), "--json") for n in traces}

        def verdict_ok(n):
            rc, j, _ = reps[n]
            if not isinstance(j, dict):
                return False, "no JSON report"
            vs, layer, req, forb = EXPECT[n]
            c = set(j.get("candidates") or [])
            ok = j.get("verdict") in vs and j.get("layer") == layer and req <= c and not (c & forb)
            return ok, f"verdict={j.get('verdict')} layer={j.get('layer')} candidates={sorted(c)}"
        ok, d = verdict_ok("clean")
        layers_ok = isinstance(reps["clean"][1], dict) and all(
            (reps["clean"][1].get("layers") or {}).get(l, {}).get("state") == "ok" for l in ("dns", "route", "tls", "application"))
        check("o1_clean_control", ok and layers_ok and reps["clean"][0] == 0, d + f"; every layer ok={layers_ok}; exit {reps['clean'][0]}")
        known = ["dns_servfail", "dns_nxdomain", "route_noroute", "route_unreach", "tls_untrusted", "app_500", "app_refused"]
        bad = [f"{n}({verdict_ok(n)[1]})" for n in known if not verdict_ok(n)[0]]
        check("o2_known_faults_localized", not bad, "all 7 localized to the right layer" if not bad else "; ".join(bad))
        bad = [f"{n}({verdict_ok(n)[1]})" for n in ("incomplete_dns_only", "tls_reset_no_dns") if not verdict_ok(n)[0]]
        conf = [reps[n][1].get("confidence") for n in ("incomplete_dns_only", "tls_reset_no_dns") if isinstance(reps[n][1], dict)]
        check("o3_bounded_uncertainty", not bad and "high" not in conf and len(conf) == 2,
              (("; ".join(bad)) or "incomplete traces stay bounded candidate sets") + f"; confidence {conf}")
        bad = [f"{n}({verdict_ok(n)[1]})" for n in ("wrong_answer",) if not verdict_ok(n)[0]]
        check("o4_cross_layer_ambiguity", not bad, "DNS pointing at the wrong server is blamed on dns, not just tls" if not bad else bad[0])
        # reproducibility and order independence
        n = "app_500"; d0 = traces[n]
        a = run("diagnose", str(tdir / f"{n}.json"), "--json")[2]
        b = run("diagnose", str(tdir / f"{n}.json"), "--json")[2]
        sh = dict(d0, observations=list(reversed(d0["observations"])))
        (base / "shuffled.json").write_text(json.dumps(sh, separators=(",", ":")))
        c = run("diagnose", str(base / "shuffled.json"), "--json")[1]
        strip = lambda j: {k: v for k, v in (j or {}).items() if k != "input_sha256"}
        same = bool(a) and a == b and strip(json.loads(a) if a.strip().startswith("{") else None) == strip(c) and bool(strip(c))
        check("o5_reproducible", same, "same trace -> identical bytes; reordered/reformatted trace -> identical verdict" if same else "output differs between runs or orderings")
        ok1, d1 = verdict_ok("icmp_filtered_ok"); ok2, d2 = verdict_ok("valid_at_capture"); ok3, d3 = verdict_ok("tls_expired_by_capture")
        check("o6_no_false_blame", ok1 and ok2 and ok3, f"icmp filtered: {d1}; cert valid at capture: {d2}; expired at capture: {d3}")
        # secrets not echoed
        leaked = [n for n, (_, _, out) in reps.items() if "ORACLE-CANARY-7731" in out]
        real = isinstance(reps["clean"][1], dict) and reps["clean"][1].get("verdict") == "healthy"  # a real report, not silence
        check("o7_no_secret_echo", not leaked and real, f"header values echoed in {leaked}" if leaked else "header values never echoed" if real else "no real report to inspect")
        # invalid input + previous report preserved
        out = base / "report.json"; out.write_text('{"previous": "good report"}\n'); before = out.read_bytes()
        bad_inputs = {"garbage": b"{not json", "schema": json.dumps({"schema": "other/9"}).encode(),
                      "dupkey": b'{"schema":"solaris.net-trace/1","schema":"solaris.net-trace/1","target":{"host":"a.example"}}',
                      "badip": json.dumps(dict(traces["clean"], observations=[{"stage": "tcp", "dst": "999.1.1.1", "port": 443, "result": "connected"}])).encode()}
        rcs = {}
        for k, v in bad_inputs.items():
            (base / f"bad-{k}.json").write_bytes(v)
            rcs[k] = run("diagnose", str(base / f"bad-{k}.json"), "--json", "--out", str(out))[0]
        os.symlink(tdir / "clean.json", base / "link.json")
        rcs["symlink"] = run("diagnose", str(base / "link.json"), "--json", "--out", str(out))[0]
        kept = out.read_bytes() == before and not [p for p in base.iterdir() if p.name.startswith(".report.json")]
        check("o8_invalid_input_safe", all(r == 2 for r in rcs.values()) and kept, f"exit codes {rcs}; previous report intact={kept}")
        rc, _, _ = run("diagnose", str(tdir / "clean.json"), "--json", "--out", str(out))
        try:
            fresh = json.loads(out.read_text()).get("verdict") == "healthy"
        except ValueError:
            fresh = False
        check("o9_recovery_after_bad_run", rc == 0 and fresh, f"next good run rewrote the report: {fresh}")
        # no network, no writes into the trace directory
        after = {p.name: p.read_bytes() for p in tdir.iterdir()}
        net = audit.read_text() if audit.exists() else ""
        check("o10_offline_read_only", not net and after == snap and real,
              (f"network attempted: {net.count('call')} calls" if net else "no socket use under a socket-denying guard; trace directory unchanged")
              + ("" if real else "; no real report produced"))
        # scale + concurrency
        sdir = base / "scale"; sdir.mkdir(); want = {}
        kinds = ["clean", "dns_nxdomain", "route_unreach", "tls_untrusted", "app_500", "incomplete_dns_only"]
        for i in range(600):
            k = kinds[i % len(kinds)]; d = gen(random.Random(seed * 1000 + i))[k]
            d["observations"] = random.Random(i).sample(d["observations"], len(d["observations"]))
            (sdir / f"t{i:04d}.json").write_text(json.dumps(d)); want[f"t{i:04d}.json"] = k
        t0 = time.monotonic(); rc, j, _ = run("batch", str(sdir), "--json", "--workers", "4", timeout=300); el = time.monotonic() - t0
        wrong = []
        reports = (j or {}).get("reports") or {}
        for f, k in want.items():
            r = reports.get(f) or {}
            vs, layer, _, _ = EXPECT[k]
            if r.get("verdict") not in vs or r.get("layer") != layer:
                wrong.append(f)
        procs = [subprocess.Popen(cmd + ["diagnose", str(tdir / "wrong_answer.json"), "--json"], stdout=subprocess.PIPE, text=True, env=env) for _ in range(6)]
        outs = {p.communicate(timeout=120)[0] for p in procs}
        check("o11_scale_concurrency", len(reports) == 600 and not wrong and len(outs) == 1 and bool(next(iter(outs)).strip()),
              f"600 shuffled traces with 4 workers in {el:.1f}s, {len(wrong)} wrong; 6 parallel runs gave {len(outs)} distinct output(s)")
        # o12 (G10 rework): SAN entries written with a type prefix, in any case, must still cover the host,
        # while a prefixed entry for another name must still be a mismatch
        host = traces["clean"]["target"]["host"]
        sdir = base / "san"; sdir.mkdir()
        cases = {"dns_upper": ([f"DNS:{host}"], True), "dns_lower": ([f"dns:{host}"], True),
                 "dns_wild": ([f"DNS:*.{host.split('.', 1)[1]}"], True), "mixed": ([f" Dns : {host.upper()}."], True),
                 "ip_entry_plus_dns": ([f"IP:{traces['clean']['observations'][1]['dst']}", f"DNS:{host}"], True),
                 "other_name": ([f"DNS:other-{host}"], False), "ip_only": ([f"IP Address:{traces['clean']['observations'][1]['dst']}"], False)}
        bad = []
        for n, (san, covers) in cases.items():
            d = json.loads(json.dumps(traces["clean"]))
            for o in d["observations"]:
                if o["stage"] == "tls":
                    o["cert"]["san"] = san
                    if not covers:
                        o.update(result="alert", alert="bad_certificate")
            if not covers:
                d["observations"] = [o for o in d["observations"] if o["stage"] != "http"]
            (sdir / f"{n}.json").write_text(json.dumps(d))
            rc, j, _ = run("diagnose", str(sdir / f"{n}.json"), "--json")
            codes = [f.get("code") for f in (j or {}).get("findings", [])] if isinstance(j, dict) else None
            if codes is None:
                bad.append(f"{n}: no JSON report")
            elif covers and (j.get("verdict") != "healthy" or "TLS_NAME_MISMATCH" in codes):
                bad.append(f"{n}: {san} should cover {host}, got {j.get('verdict')} {codes}")
            elif not covers and "TLS_NAME_MISMATCH" not in codes:
                bad.append(f"{n}: {san} must still be a name mismatch, got {codes}")
        check("o12_san_forms", not bad, "prefixed SAN entries cover the host; other names still mismatch" if not bad else "; ".join(bad[:3]))
        # o13 (G10 r3, from M10 self-validation): the specific cause, not just the layer
        clean = traces["clean"]; ip = clean["observations"][1]["dst"]
        def variant(name, edit, drop_http=True, alert="bad_certificate", target=None):
            d = json.loads(json.dumps(clean))
            if target:
                d["target"]["host"] = target
            for o in d["observations"]:
                if o["stage"] == "tls":
                    edit(o)
                    if alert:
                        o.update(result="alert", alert=alert)
            if drop_http:
                d["observations"] = [o for o in d["observations"] if o["stage"] != "http"]
            (sdir / f"{name}.json").write_text(json.dumps(d))
            rc, j, out = run("diagnose", str(sdir / f"{name}.json"), "--json")
            return j if isinstance(j, dict) else {}
        codes = lambda j: [f.get("code") for f in j.get("findings", [])]
        bad = []
        want_code = {"tls_untrusted": "TLS_UNTRUSTED_CHAIN", "tls_expired_by_capture": "TLS_CERT_EXPIRED"}
        for n, c in want_code.items():
            if c not in codes(reps[n][1] or {}):
                bad.append(f"{n}: expected {c}, got {codes(reps[n][1] or {})}")
        lay = [(f.get("code"), f.get("layer")) for f in (reps["app_refused"][1] or {}).get("findings", [])]
        if lay != [("APP_NOT_LISTENING", "application")]:
            bad.append(f"refused port: findings {lay}, expected APP_NOT_LISTENING at application")
        j = variant("ipname", lambda o: o["cert"].update(san=[f"IP:{host}"]))
        if "TLS_NAME_MISMATCH" not in codes(j):
            bad.append(f"an IP: entry holding the host name covered it: {codes(j)}")
        # wildcard depth (G10 r4, M10 r2 E1): a legal wildcard one label above the host covers it and does not
        # cover a name two labels below; "*.example" would be refused by the single-label rule before depth.
        wdom = host.split(".", 1)[1]
        j = variant("deep-ok", lambda o: o["cert"].update(san=[f"DNS:*.{wdom}"]))
        if codes(j) != ["TLS_ALERT"]:
            bad.append(f"DNS:*.{wdom} must cover {host}: {codes(j)}, expected only TLS_ALERT")
        def deep_ed(o):
            o["cert"]["san"] = [f"DNS:*.{wdom}"]; o["sni"] = f"a.{host}"
        j = variant("deep", deep_ed, target=f"a.{host}")
        if "TLS_NAME_MISMATCH" not in codes(j):
            bad.append(f"DNS:*.{wdom} covered a.{host} (two labels below): {codes(j)}")
        nocfg = json.loads(json.dumps(clean)); nocfg["config"]["expected_addresses"] = []
        for o in nocfg["observations"]:
            if o["stage"] == "tls":
                o.update(result="alert", alert="bad_certificate"); o["cert"]["san"] = ["DNS:elsewhere.example"]
        nocfg["observations"] = [o for o in nocfg["observations"] if o["stage"] != "http"]
        (sdir / "unverified.json").write_text(json.dumps(nocfg))
        j = run("diagnose", str(sdir / "unverified.json"), "--json")[1] or {}
        if "dns" not in (j.get("candidates") or []):
            bad.append(f"unverified name mismatch: candidates {j.get('candidates')}, dns must stay a candidate")
        reset = json.loads(json.dumps(clean))
        for o in reset["observations"]:
            if o["stage"] == "tls":
                o.update(result="reset", cert=None)
        reset["observations"] = [o for o in reset["observations"] if o["stage"] != "http"]
        (sdir / "reset.json").write_text(json.dumps(reset))
        j = run("diagnose", str(sdir / "reset.json"), "--json")[1] or {}
        if "route" not in (j.get("candidates") or []):
            bad.append(f"handshake reset: candidates {j.get('candidates')}, a middlebox (route) must stay a candidate")
        mixed = json.loads(json.dumps(clean)); mixed["target"]["host"] = host.upper()
        (sdir / "mixed.json").write_text(json.dumps(mixed))
        j = run("diagnose", str(sdir / "mixed.json"), "--json")[1] or {}
        if j.get("verdict") != "healthy":
            bad.append(f"upper-case target host: {j.get('verdict')} {codes(j)}")
        v6 = "2001:db8::7"
        d6 = json.loads(json.dumps(clean)); d6["target"]["host"] = v6
        d6["observations"] = [dict(o, dst=v6) for o in d6["observations"] if o["stage"] in ("tcp", "tls")] + [o for o in d6["observations"] if o["stage"] == "http"]
        for o in d6["observations"]:
            if o["stage"] == "tls":
                o["sni"] = None; o["cert"]["san"] = ["IP:2001:db8:0:0:0:0:0:7"]
        (sdir / "v6.json").write_text(json.dumps(d6))
        j = run("diagnose", str(sdir / "v6.json"), "--json")[1] or {}
        if j.get("verdict") != "healthy":
            bad.append(f"IPv6 target with a long-form IP entry: {j.get('verdict')} {codes(j)}")
        d6b = json.loads(json.dumps(d6))
        for o in d6b["observations"]:
            if o["stage"] == "tls":
                o["cert"]["san"] = [f"DNS:{v6}"]; o.update(result="alert", alert="bad_certificate")
        d6b["observations"] = [o for o in d6b["observations"] if o["stage"] != "http"]
        (sdir / "v6dns.json").write_text(json.dumps(d6b))
        j = run("diagnose", str(sdir / "v6dns.json"), "--json")[1] or {}
        if "TLS_NAME_MISMATCH" not in codes(j):
            bad.append(f"a DNS: entry holding the address covered the IPv6 target: {codes(j)}")
        many = json.loads(json.dumps(clean))
        many["observations"][0]["answers"] = [ip, "198.51.100.3", "198.51.100.250", "198.51.100.17"]
        (sdir / "many.json").write_text(json.dumps(many))
        outs = set()
        for seed_ in range(5):
            p = subprocess.run(cmd + ["diagnose", str(sdir / "many.json"), "--json"], capture_output=True, text=True,
                               env=dict(env, PYTHONHASHSEED=str(seed_)), timeout=120)
            outs.add(p.stdout)
        if len(outs) != 1:
            bad.append(f"{len(outs)} different reports for one trace across hash seeds")
        check("o13_specific_causes", not bad, "chain, expiry, refused port, IP/DNS entry types, wildcard depth, ambiguity, case, IPv6, order" if not bad else "; ".join(bad[:3]))
        # o14 (G10 r3, from M10 self-validation): other SAN spellings, public-suffix wildcards, non-ASCII,
        # SNI, deep JSON and strict times
        bad = []
        dom = host.split(".", 1)[1]
        for n, san in (("keytool", [f"DNSName: {host}"]), ("windows", [f"DNS Name={host}"]),
                       ("oneline", [f"DNS:other.example, DNS:{host}, IP Address:{ip}"])):
            j = variant("sp-" + n, lambda o, san=san: o["cert"].update(san=san))
            if codes(j) != ["TLS_ALERT"]:
                bad.append(f"{n} spelling {san} covering {host}: {codes(j)}, expected only TLS_ALERT")
            if any("not understood" in x for x in j.get("notes", [])):
                bad.append(f"{n} spelling {san} reported as not understood; it is a known spelling")
        # an unrecognised typed spelling (certutil "Principal Name=") and a known non-host type with no host
        # entry beside it are both "not understood" and never a confident mismatch (G10 r4 keeps both cases)
        for n, san in (("sp-unknown", [f"Principal Name={host}"]), ("sp-unknown-dns", ["DNS:other.example", f"Principal Name={host}"]),
                       ("sp-nonhost-only", [f"othername:{host}"])):
            j = variant(n, lambda o, san=san: o["cert"].update(san=san))
            if "TLS_NAME_MISMATCH" in codes(j) or not any("not understood" in x for x in j.get("notes", [])):
                bad.append(f"{san}: must be noted as not understood, not judged a mismatch: {codes(j)}")
        for n, tgt, san in (("tld", "shop.example", "DNS:*.example"), ("psl", "shop.co.uk", "DNS:*.co.uk"),
                            ("kelvin", "kelvin.example", "DNS:\u212aelvin.example"), ("dots", host, f"DNS:{host}..")):
            def ed(o, san=san, tgt=tgt):
                o["cert"]["san"] = [san]; o["sni"] = tgt
            j = variant("ns-" + n, ed, target=tgt)
            if "TLS_NAME_MISMATCH" not in codes(j):
                bad.append(f"{san} must not cover {tgt}: {codes(j)}")
        j = variant("sni", lambda o: o.update(sni=f"www.other-{dom}") or o["cert"].update(san=[f"DNS:www.other-{dom}"]))
        if "TLS_SNI_MISMATCH" not in codes(j):
            bad.append(f"SNI different from the target not flagged: {codes(j)}")
        (sdir / "deep.json").write_text("[" * 100000 + "]" * 100000)
        rc = run("diagnose", str(sdir / "deep.json"), "--json")[0]
        if rc != 2:
            bad.append(f"deeply nested JSON exit {rc}, expected 2")
        for ts, ok in (("2026-09-01T12:00:00.5Z", 0), ("2026-09-01T12:00:00.1234567Z", 0),
                       ("2026-09-01T12:00:00.123456789Z", 0), ("2026-09-01T12:00:00.Z", 2),
                       ("2026-09-01T12:00:00+0000", 2), ("20260901T120000Z", 2)):
            d = dict(clean, captured_at=ts)
            (sdir / "ts.json").write_text(json.dumps(d))
            rc = run("diagnose", str(sdir / "ts.json"), "--json")[0]
            if rc != ok:
                bad.append(f"captured_at {ts}: exit {rc}, expected {ok} (RFC 3339 only, same on every Python)")
        # G10 r4 (M10 r2 RG1): non-host SAN types beside DNS entries never hide a real name mismatch
        for n, extra in (("uri", "URI:spiffe://svc.example/ns/a/sa/b"), ("email", "email:ops@svc.example"),
                         ("othername", "othername:UPN::ops@svc.example"), ("dirname", "DirName:/C=GB, O=Example, CN=x"),
                         ("rid", "Registered ID:1.2.3.4")):
            for form, san in (("list", ["DNS:other.example", extra]), ("oneline", [f"DNS:other.example, {extra}"])):
                j = variant(f"nh-{n}-{form}", lambda o, san=san: o["cert"].update(san=san))
                if "TLS_NAME_MISMATCH" not in codes(j):
                    bad.append(f"{san} on {host}: {codes(j)}, a real name mismatch must be reported")
                elif not any("not host names" in x for x in j.get("notes", [])):
                    bad.append(f"{san} on {host}: the ignored non-host entry is not named in the notes")
        # G10 r5 (M10 r3 Q1): keytool and certutil spellings of non-host types, too
        for n, extra in (("kt-uri", "URIName: spiffe://svc.example/a"), ("kt-oid", "OIDName: 1.2.3.4"),
                         ("kt-other", "Other-Name: Unrecognized ObjectIdentifier: 1.3.6.1.4.1.311.20.2.3"),
                         ("cu-url", "URL=spiffe://svc.example/a")):
            j = variant(f"nh-{n}", lambda o, extra=extra: o["cert"].update(san=["DNS:other.example", extra]))
            if "TLS_NAME_MISMATCH" not in codes(j):
                bad.append(f"{extra} beside DNS:other.example on {host}: {codes(j)}, a real name mismatch must be reported")
        j = variant("nh-uri-alone", lambda o: o["cert"].update(san=["URIName: spiffe://svc.example/a"]))
        if any("paste them as DNS" in x or ("not understood" in x and "do not rewrite" not in x) for x in j.get("notes", [])):
            bad.append("a URI that is not understood must not be advised to be pasted as DNS")
        # G10 r5 (M10 r3 Q2): a bare name after a typed entry in one list is its own entry
        j = variant("mixed-cover", lambda o: o["cert"].update(san=[f"DNS:other.example, {host}"]))
        if codes(j) != ["TLS_ALERT"]:
            bad.append(f"'DNS:other.example, {host}' covers {host}: {codes(j)}, expected only TLS_ALERT")
        j = variant("nh-cover", lambda o: o["cert"].update(san=[f"DNS:{host}", "URI:spiffe://svc.example/a"]))
        if codes(j) != ["TLS_ALERT"]:
            bad.append(f"covering DNS entry plus URI: {codes(j)}, expected only TLS_ALERT")
        # G10 r4 (M10 r2 RG4): a nanosecond not_after before the capture is an expiry, not invalid input
        exp = json.loads(json.dumps(clean)); exp["captured_at"] = "2026-10-18T16:00:00Z"
        for o in exp["observations"]:
            if o["stage"] == "tls":
                o["cert"]["not_after"] = "2026-10-18T15:59:59.999999999Z"
        (sdir / "ns-expired.json").write_text(json.dumps(exp))
        rc, j, _ = run("diagnose", str(sdir / "ns-expired.json"), "--json")
        if rc == 2 or "TLS_CERT_EXPIRED" not in codes(j if isinstance(j, dict) else {}):
            bad.append(f"not_after with 9 fraction digits before capture: exit {rc}, expected TLS_CERT_EXPIRED")
        # digits past the sixth are dropped, never rounded: .1234567 is before .123457
        exp["captured_at"] = "2026-10-18T16:00:00.123457Z"
        for o in exp["observations"]:
            if o["stage"] == "tls":
                o["cert"]["not_after"] = "2026-10-18T16:00:00.1234567Z"
        (sdir / "ns-trunc.json").write_text(json.dumps(exp))
        rc, j, _ = run("diagnose", str(sdir / "ns-trunc.json"), "--json")
        if rc == 2 or "TLS_CERT_EXPIRED" not in codes(j if isinstance(j, dict) else {}):
            bad.append(f"not_after .1234567 before capture .123457: exit {rc}, expected TLS_CERT_EXPIRED (truncate, not round)")
        check("o14_san_spellings_and_inputs", not bad, "keytool/Windows/one-line SANs cover; non-host SAN types (openssl, keytool, certutil) never hide a mismatch; a bare name after a typed one covers; suffix wildcards, non-ASCII, double dot refused; SNI flagged; deep JSON and non-RFC 3339 times exit 2; any fraction digit count accepted" if not bad else "; ".join(bad[:3]))
    n = sum(results)
    print(f"SUMMARY {n}/{len(results)} pass; candidate {'ACCEPTED by oracle' if n == len(results) else 'REJECTED'}")
    return 0 if n == len(results) else 1

if __name__ == "__main__":
    sys.exit(main())
