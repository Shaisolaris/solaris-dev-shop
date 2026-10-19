#!/usr/bin/env python3
"""Repros for the M10 findings. Writes synthetic traces (documentation addresses, .example names)
to a temp dir and runs the candidate CLI on them; prints exit code plus the diagnosis lines.
Usage: python m10_finding_repros.py PY_MAIN PY39 NETDIAG"""
import json, subprocess, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import m10_oracle as M
from m10_oracle import trace, dns, tcp, tls, cert, http, A

PY, PY39, T = sys.argv[1:4]
tmp = Path(tempfile.mkdtemp(prefix="m10-repro-"))


def show(label, doc=None, raw=None, py=PY, args=("diagnose",), lines=4):
    f = tmp / (label.split()[0] + ".json")
    f.write_bytes(raw if raw is not None else json.dumps(doc, indent=1).encode())
    r = subprocess.run([py, T, *args, str(f)], capture_output=True, text=True, env=M.env())
    out = [l for l in r.stdout.splitlines() if l.startswith(("diagnosis", "  finding", "  layers", "  candidate"))][:lines]
    err = r.stderr.strip().splitlines()[-1:] if r.stderr.strip() else []
    print(f"  [{label}] {Path(py).name} rc={r.returncode}")
    for l in out + [f"  stderr: {e[:160]}" for e in err]:
        print("     " + l.strip())


def alert_case(host, san, sni="same"):
    sni = host if sni == "same" else sni
    return trace([dns(qname=host), tcp(), tls("alert", cert(san=san), "bad_certificate", sni=sni)], host=host)

print("F1 typed SAN spellings outside DNS:/IP:/IP Address: (certificate does cover the host)")
for label, san in [("keytool DNSName:", ["DNSName: api.shop.example"]),
                   ("windows 'DNS Name='", ["DNS Name=api.shop.example"]),
                   ("openssl -ext subjectAltName one-line", ["DNS:api.shop.example, DNS:www.shop.example"]),
                   ("control DNS:", ["DNS:api.shop.example"])]:
    show(label, alert_case("api.shop.example", san))
show("keytool IPAddress: for IP target", trace([tcp(), tls("alert", cert(san=["IPAddress: " + A]), "bad_certificate", sni=None)], host=A, expected=(A,)))

print("F2 wildcard over a single remaining label (TLD / public suffix) treated as covering")
for label, host, san in [("*.example", "shop.example", ["DNS:*.example"]), ("*.co.uk", "shop.co.uk", ["DNS:*.co.uk"]),
                         ("control-real-mismatch", "shop.example", ["DNS:other.example"])]:
    show(label, alert_case(host, san))

print("F3 non-ASCII SAN folded to ASCII by str.lower (U+212A KELVIN SIGN)")
show("kelvin", alert_case("kelvin.example", ["DNS:\u212aelvin.example"]))
show("control-ascii-lookalike", alert_case("kelvin.example", ["DNS:kelvln.example"]))

print("F4 client SNI differs from the target host; certificate covers only the SNI")
show("sni-differs", alert_case("api.shop.example", ["DNS:www.other.example"], sni="www.other.example"))

print("F5 deeply nested JSON (100000 levels)")
raw = b'{"schema": "solaris.net-trace/1", "x": ' + b"[" * 100000 + b"]" * 100000 + b"}"
show("deep diagnose", raw=raw)
d = tmp / "batchdir"; d.mkdir()
(d / "a.json").write_bytes(raw); (d / "b.json").write_text(json.dumps(trace(M.healthy_obs())))
r = subprocess.run([PY, T, "batch", str(d)], capture_output=True, text=True, env=M.env())
print(f"  [deep in batch with one good trace] rc={r.returncode} stdout={r.stdout.strip()[:120]!r} stderr_last={r.stderr.strip().splitlines()[-1][:120] if r.stderr.strip() else ''!r}")

print("F6 SAN with a double trailing dot")
show("double-dot", alert_case("api.shop.example", ["DNS:api.shop.example.."]))

print("F7 captured_at forms: Python 3.9 vs 3.12 (same trace, same candidate)")
for ts in ("2026-10-18T16:00:00+0000", "2026-10-18T16:00:00.5Z", "20261018T160000Z", "2026-10-18T16:00:00Z"):
    doc = trace(M.healthy_obs(), captured=ts)
    for py in (PY, PY39):
        show(f"ts {ts}", doc, py=py, lines=1)
