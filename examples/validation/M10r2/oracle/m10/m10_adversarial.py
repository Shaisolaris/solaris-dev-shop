#!/usr/bin/env python3
"""M10 adversarial cases (unseen by the builder's tests/oracle). OK, FINDING or NOTE per case.
Usage: python m10_adversarial.py [--pythons P1,P2,...] -- <candidate prefix...>
--pythons: extra interpreters for the cross-interpreter cases (the candidate script is the last
element of the prefix and is run under each)."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import m10_oracle as M  # noqa: E402
from m10_oracle import A, HOST, cert, dns, tcp, tls, http, trace, healthy_obs  # noqa: E402

CASES = []
PYS = []


def case(fn):
    CASES.append(fn)
    return fn


def diag(w, doc, raw=None, cmd=None, extra=None):
    p = w.write(doc, raw=raw)
    r = subprocess.run((cmd or M.CMD) + ["diagnose", str(p), "--json"], capture_output=True, text=True, env=M.env(extra))
    try:
        return r.returncode, json.loads(r.stdout), r.stderr
    except ValueError:
        return r.returncode, None, (r.stdout + r.stderr)


def corpus():
    out = [("healthy", trace(healthy_obs()))]
    for label, obs, routes, layer, code in M.LOCALIZE:
        out.append((label, trace(obs(), routes=routes)))
    for label, host, san in M.SAN_COVER + M.SAN_REJECT + M.SAN_STRICT:
        is_ip = ":" in host or host.replace(".", "").isdigit()
        dst = host if ":" in host else A
        obs = ([] if is_ip else [dns(qname=host)]) + [tcp(dst=dst), tls("alert", cert(san=san), "bad_certificate", sni=None if is_ip else host, dst=dst)]
        out.append(("san " + label, trace(obs, host=host)))
    out.append(("empty", trace([])))
    out.append(("no captured_at", trace(healthy_obs(), captured=None)))
    return out


@case
def a01_cross_interpreter_bytes(w):
    if not PYS:
        return "NOTE", "no --pythons given"
    script = M.CMD[-1]
    diffs, n = [], 0
    for label, doc in corpus():
        p = w.write(doc)
        outs = {}
        for py in [M.CMD[0]] + PYS:
            r = subprocess.run([py, script, "diagnose", str(p), "--json"], capture_output=True, text=True, env=M.env())
            outs[py] = (r.returncode, r.stdout)
        n += 1
        if len(set(outs.values())) != 1:
            diffs.append(label)
    if diffs:
        return "FINDING", f"{len(diffs)}/{n} traces give different output across interpreters: {diffs[:6]}"
    return "OK", f"{n} traces: identical exit code and bytes on {1 + len(PYS)} interpreters"


TIMES = ["2026-10-18T16:00:00Z", "2026-10-18T16:00:00z", "2026-10-18T16:00:00+00:00", "2026-10-18T16:00:00.5Z",
         "2026-10-18T16:00:00.123Z", "2026-10-18T16:00:00.123456Z", "2026-10-18T16:00:00.1234567Z", "2026-10-18T16:00:00+0000",
         "2026-10-18T16:00Z", "2026-10-18 16:00:00Z", "20261018T160000Z", "2026-10-18T16:00:00+00", "2026-W42-7T16:00:00Z",
         "2026-10-18T16:00:60Z", "2026-10-18T24:00:00Z"]


@case
def a02_timestamp_forms_across_interpreters(w):
    rows, diverge = [], []
    for ts in TIMES:
        doc = trace([dns(), tcp(), tls("alert", cert(na="2026-06-01T00:00:00Z"), "certificate_expired")], captured=ts)
        res = []
        for py in [M.CMD[0]] + PYS:
            rc, rep, err = diag(w, doc, cmd=[py, M.CMD[-1]])
            res.append(rc)
        rows.append(f"{ts}: " + "/".join(str(r) for r in res))
        if len(set(res)) != 1:
            diverge.append(ts)
    st = "FINDING" if diverge else "OK"
    return st, (f"captured_at forms accepted differently by interpreter ({len(diverge)}): {diverge}; exit codes main/" +
                "/".join(Path(p).parts[-3] if 'cpython' in p else p for p in PYS) + ": " + "; ".join(rows))


OTHER_FORMS = [("keytool DNSName:", HOST, ["DNSName: " + HOST]), ("keytool IPAddress:", A, ["IPAddress: " + A]),
               ("Windows DNS Name=", HOST, ["DNS Name=" + HOST]), ("Windows IP Address=", A, ["IP Address=" + A]),
               ("openssl -ext one-line list", HOST, ["DNS:a.example, DNS:" + HOST]), ("URI SAN only", HOST, ["URI:https://" + HOST + "/"])]


@case
def a03_other_san_spellings(w):
    res = []
    for label, host, san in OTHER_FORMS:
        m, rep = M._mismatch(w, host, san)
        res.append((label, m, rep.get("verdict"), rep.get("confidence")))
    false_mm = [r for r in res[:5] if r[1]]
    msg = "; ".join(f"{l}: mismatch={m} {v}/{c}" for l, m, v, c in res)
    if false_mm:
        return "FINDING", "typed SAN spellings outside DNS:/IP:/IP Address: are read as bare names, giving a confident TLS_NAME_MISMATCH: " + msg
    return "OK", msg


@case
def a04_sni_differs_from_target(w):
    doc = trace([dns(), tcp(), tls("alert", cert(san=["DNS:www.other.example"]), "bad_certificate", sni="www.other.example")])
    rc, rep, _ = diag(w, doc)
    txt = json.dumps(rep)
    flagged = "TLS_NAME_MISMATCH" in txt or "sni" in " ".join(rep.get("notes", [])).lower()
    if not flagged:
        return "FINDING", (f"client sent SNI www.other.example for target {HOST}; certificate covers only the SNI; report "
                           f"{rep['verdict']}/{rep['layer']} {M.codes(rep)}, no mismatch and no note about the SNI")
    return "OK", "SNI/target difference reported"


@case
def a05_double_trailing_dot_san(w):
    m, rep = M._mismatch(w, HOST, ["DNS:" + HOST + ".."])
    rc, rep2, err = diag(w, trace(healthy_obs(), host=HOST + ".."))
    return ("FINDING" if not m else "OK"), f"SAN '{HOST}..' (not a valid name) covers {HOST}: {not m}; target host '{HOST}..' rc={rc}"


@case
def a06_deep_nesting(w):
    raw = b'{"schema": "solaris.net-trace/1", "x": ' + b"[" * 100000 + b"]" * 100000 + b"}"
    rc, rep, err = diag(w, None, raw=raw)
    p = w.tmp / "deep"
    p.mkdir()
    (p / "a.json").write_bytes(raw)
    (p / "b.json").write_text(json.dumps(trace(healthy_obs())))
    r = subprocess.run(M.CMD + ["batch", str(p), "--json"], capture_output=True, text=True, env=M.env())
    tb = "Traceback" in err or "Traceback" in r.stderr
    st = "FINDING" if tb or rc != 2 or r.returncode not in (0, 1, 2) else "OK"
    return st, f"100000-deep JSON: diagnose rc={rc} traceback={'Traceback' in err}; batch with it plus a good trace rc={r.returncode} traceback={'Traceback' in r.stderr}"


@case
def a07_batch_workers_values(w):
    p = w.tmp / "wk"
    p.mkdir()
    for i in range(3):
        (p / f"{i}.json").write_text(json.dumps(trace(healthy_obs())))
    res = []
    for v in ("0", "-3", "1", "64", "100000"):
        try:
            r = subprocess.run(M.CMD + ["batch", str(p), "--workers", v, "--json"], capture_output=True, text=True, env=M.env(), timeout=60)
            res.append(f"{v}:rc={r.returncode}{' TB' if 'Traceback' in r.stderr else ''}")
        except subprocess.TimeoutExpired:
            res.append(f"{v}:TIMEOUT")
    st = "FINDING" if any("TB" in x or "TIMEOUT" in x for x in res) else "NOTE"
    return st, "batch --workers " + ", ".join(res)


@case
def a08_shell_metachar_path(w):
    import shlex
    path = "/x';touch /tmp/m10-pwned;'$(id)`id`"
    res = []
    for label, obs in (("tls expired", [dns(), tcp(), tls("alert", cert(na="2026-06-01T00:00:00Z"), "certificate_expired")]),
                       ("http 500", healthy_obs()[:3] + [http(500)]), ("http timeout", healthy_obs()[:3] + [http(result="timeout")])):
        doc = trace(obs)
        doc["target"]["path"] = path
        rc, rep, err = diag(w, doc)
        for a in rep.get("next_actions", []):
            if "touch /tmp/m10-pwned" not in a:
                continue  # prose or commands that do not carry the path
            try:
                toks = shlex.split(a.split(" | ")[0])
            except ValueError as e:
                res.append(f"{label}: unparsable shell line {a[:80]!r} ({e})")
                continue
            if not any(path in t for t in toks):
                res.append(f"{label}: path split across tokens in {a[:100]!r}")
            elif any("touch" == t for t in toks):
                res.append(f"{label}: injected command became a separate token in {a[:100]!r}")
            else:
                res.append(f"{label}: safe")
    unsafe = [r for r in res if not r.endswith("safe")]
    return ("FINDING" if unsafe or not res else "OK"), f"path with quote/$()/backticks in {len(res)} command lines: " + "; ".join(res)


@case
def a09_header_values_not_echoed(w):
    doc = trace(healthy_obs()[:3] + [{"stage": "http", "status": 503, "headers": {"Authorization": "Bearer SECRET-TOKEN-123", "Via": "1.1 proxy"}}])
    rc, rep, err = diag(w, doc)
    leak = "SECRET-TOKEN-123" in json.dumps(rep)
    return ("FINDING" if leak else "OK"), f"header value echoed: {leak}; verdict {rep['verdict']}/{rep['layer']} {M.codes(rep)}"


@case
def a10_unicode_target(w):
    rc, rep, err = diag(w, trace(healthy_obs(), host="b\u00fccher.example"))
    return "NOTE", f"U-label target host b\u00fccher.example: rc={rc} (A-labels only; no IDNA conversion)"


@case
def a11_ipv6_zone_target(w):
    rc, rep, err = diag(w, trace([tcp(dst="fe80::1%en0")], host="fe80::1%en0"))
    return "NOTE", f"IPv6 target with zone id: rc={rc} {(err or '').strip().splitlines()[-1][:100] if rc == 2 and err else ''}"


@case
def a12_http_ok_but_tls_failed(w):
    rc, rep, err = diag(w, trace([dns(), tcp(), tls("reset", None), http(200)]))
    return "NOTE", f"handshake reset plus HTTP 200 in one trace: {rep['verdict']}/{rep['layer']} tls={M.states(rep)['tls']} {M.codes(rep)}"


@case
def a13_cert_without_san(w):
    c = {"not_before": "2026-01-01T00:00:00Z", "not_after": "2027-01-01T00:00:00Z", "chain_trusted": True, "subject_cn": HOST}
    rc, rep, err = diag(w, trace([dns(), tcp(), tls("alert", c, "bad_certificate")]))
    return "NOTE", f"certificate with no san (CN only), alert bad_certificate: {rep['verdict']}/{rep['layer']} {M.codes(rep)}; CN is never consulted"


@case
def a14_scale(w):
    import time
    obs = [dns()] + [tcp() for _ in range(9990)] + [tls(), http(200)]
    t0 = time.time()
    rc, rep, err = diag(w, trace(obs))
    t1 = time.time() - t0
    p = w.tmp / "scale-batch"
    p.mkdir()
    for i in range(2000):
        (p / f"{i:04d}.json").write_text(json.dumps(trace(M.LOCALIZE[i % len(M.LOCALIZE)][1](), routes=M.LOCALIZE[i % len(M.LOCALIZE)][2])))
    t0 = time.time()
    r1 = subprocess.run(M.CMD + ["batch", str(p), "--json"], capture_output=True, text=True, env=M.env())
    t2 = time.time() - t0
    t0 = time.time()
    r4 = subprocess.run(M.CMD + ["batch", str(p), "--workers", "4", "--json"], capture_output=True, text=True, env=M.env())
    t3 = time.time() - t0
    same = r1.stdout == r4.stdout
    return ("OK" if same and rc == 0 else "FINDING"), (f"10000 observations: rc={rc} {t1:.1f}s; batch of 2000 traces: {t2:.1f}s sequential, "
                                                     f"{t3:.1f}s with 4 workers, identical={same}")


@case
def a15_batch_symlink_and_dotfiles(w):
    p = w.tmp / "bl"
    p.mkdir()
    out = w.tmp / "outside.json"
    out.write_text(json.dumps(trace(healthy_obs())))
    os.symlink(out, p / "link.json")
    (p / ".hidden.json").write_text(json.dumps(trace(healthy_obs())))
    (p / "ok.json").write_text(json.dumps(trace(healthy_obs())))
    r = subprocess.run(M.CMD + ["batch", str(p), "--json"], capture_output=True, text=True, env=M.env())
    b = json.loads(r.stdout)
    followed = "link.json" in b.get("reports", {})
    return ("FINDING" if followed else "OK"), f"batch: symlinked trace followed={followed}, invalid={list(b.get('invalid', {}))}, dotfile skipped={'.hidden.json' not in b.get('reports', {})}"


def main(argv):
    global PYS
    i = argv.index("--")
    M.CMD = argv[i + 1:]
    if "--pythons" in argv[:i]:
        PYS = [p for p in argv[argv.index("--pythons") + 1].split(",") if p]
    tmp = Path(tempfile.mkdtemp(prefix="m10-adv-")).resolve()
    w = M.Work(tmp)
    counts = {}
    try:
        for fn in CASES:
            try:
                st, msg = fn(w)
            except M.Fail as e:
                st, msg = "FINDING", f"harness Fail: {e}"
            except Exception as e:
                st, msg = "ERROR", f"{type(e).__name__}: {str(e)[:300]}"
            counts[st] = counts.get(st, 0) + 1
            print(f"{st} {fn.__name__}: {msg}", flush=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("SUMMARY " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))


if __name__ == "__main__":
    main(sys.argv[1:])
