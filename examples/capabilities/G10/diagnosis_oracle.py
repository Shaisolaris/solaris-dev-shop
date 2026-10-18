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
    n = sum(results)
    print(f"SUMMARY {n}/{len(results)} pass; candidate {'ACCEPTED by oracle' if n == len(results) else 'REJECTED'}")
    return 0 if n == len(results) else 1

if __name__ == "__main__":
    sys.exit(main())
