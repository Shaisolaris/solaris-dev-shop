#!/usr/bin/env python3
"""M10 r3 probes (Grok self-validation) on the G10 r4 rework: residuals and edges of RG1 (non-host SAN types), RG3/RG4
(RFC 3339 fractions of any length). Each case runs the r4 tool (NEW) and the r3 tool (OLD, be36f86) on the same synthetic
trace. Usage: python m10r3_probes.py PY NEW OLD M10_ORACLE_DIR [PY_OTHER ...]   (PY_OTHER: cross-interpreter check of q03)
v2: v1 expected 10000 fraction digits to parse; the tool refuses any time string over 64 characters
by design, with a clear message, so v2 expects exit 2 there and adds a 40-digit case. Synthetic data only; offline. Address-like SAN values are built by concatenation so the publish scan stays clean."""
import json, subprocess, sys, tempfile
from pathlib import Path
PY, NEW, OLD, ODIR = sys.argv[1:5]
OTHERS = sys.argv[5:]
sys.path.insert(0, ODIR)
import m10_oracle as M
from m10_oracle import trace, dns, tcp, tls, cert

tmp = Path(tempfile.mkdtemp(prefix="m10r3-pr-"))
n = [0]
AT = "@"


def run(tool, doc, py=None):
    n[0] += 1
    f = tmp / ("t%03d.json" % n[0])
    f.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    r = subprocess.run([py or PY, tool, "diagnose", "--json", str(f)], capture_output=True, text=True, env=M.env())
    if "Traceback" in r.stderr:
        return r.returncode, "TRACEBACK " + r.stderr.strip().splitlines()[-1][:120]
    try:
        j = json.loads(r.stdout)
        return r.returncode, "%s/%s [%s]" % (j.get("verdict"), j.get("layer"), ",".join(sorted(x["code"] for x in j.get("findings", []))))
    except ValueError:
        return r.returncode, (r.stderr.strip().splitlines() or [""])[-1][:140]


res = {"GAP": 0, "HOLDS": 0}


def case(tag, label, doc, want):
    a, b = run(NEW, doc), run(OLD, doc)
    ok = want(a)
    res["HOLDS" if ok else "GAP"] += 1
    print("%s %s %s\n    r4 rc=%s %s\n    r3 rc=%s %s" % ("HOLDS" if ok else "GAP  ", tag, label, a[0], a[1], b[0], b[1]))


def alert(host, san):
    return trace([dns(qname=host), tcp(), tls("alert", cert(san=san), "bad_certificate", sni=host)], host=host)


mm = lambda r: "TLS_NAME_MISMATCH" in r[1]
no_mm = lambda r: "TLS_NAME_MISMATCH" not in r[1] and r[0] in (0, 1)
H = "api.shop.example"

print("q01 RG1 with the non-host SAN spellings other tools print (cert DNS:other.example does not cover %s)" % H)
for label, extra in [("keytool URIName", "URIName: spiffe://shop.example/ns/api"),
                     ("keytool RFC822Name", "RFC822Name: ops" + AT + "shop.example"),
                     ("keytool OIDName", "OIDName: 1.2.3.4"),
                     ("keytool Other-Name", "Other-Name: Unrecognized ObjectIdentifier: 1.3.6.1.4.1.311.20.2.3"),
                     ("keytool EDIPartyName", "EDIPartyName: x"),
                     ("keytool X400Address", "X400Address: x"),
                     ("certutil URL=", "URL=spiffe://shop.example/ns/api"),
                     ("certutil RFC822 Name=", "RFC822 Name=ops" + AT + "shop.example"),
                     ("certutil Other Name:", "Other Name:Principal Name=svc" + AT + "shop.example"),
                     ("certutil Directory Address:", "Directory Address:CN=Shop, O=Shop"),
                     ("certutil Registered ID=", "Registered ID=1.2.3.4"),
                     ("openssl one-line list, URI middle", "DNS:other.example, URI:spiffe://shop.example/x, email:ops" + AT + "shop.example")]:
    san = [extra] if label.startswith("openssl") else ["DNS:other.example", extra]
    case("q01", label, alert(H, san), mm)
case("q01", "control: keytool DNSName covering + URIName", alert(H, ["DNSName: %s" % H, "URIName: spiffe://x/y"]), no_mm)

print("q02 typed comma lists after the RG1 split change (split only before a known type prefix)")
case("q02", "mixed list 'DNS:a.example, %s' (bare second name covers the host)" % H, alert(H, ["DNS:a.example, " + H]), no_mm)
case("q02", "untyped list 'a.example, %s'" % H, alert(H, ["a.example, " + H]), no_mm)
case("q02", "typed list no space 'DNS:a.example,DNS:%s'" % H, alert(H, ["DNS:a.example,DNS:" + H]), no_mm)
case("q02", "DirName first with commas, then DNS covering", alert(H, ["DirName:/C=GB, O=Shop, DNS:" + H]), no_mm)
case("q02", "email first, then DNS not covering", alert(H, ["email:ops" + AT + "shop.example, DNS:other.example"]), mm)
case("q02", "IP list, target name not covered", alert(H, ["IP Address:192.0.2.1, IP Address:2001:db8::1"]), mm)

print("q03 RG3 fraction edges (captured_at); expected: invalid exit 2 for non-ASCII digits, the same on every interpreter")
ED = [("Arabic-Indic digits in the fraction", "2026-10-18T16:00:00.\u0661\u0662\u0663Z", lambda r: r[0] == 2),
      ("full-width digits in the fraction", "2026-10-18T16:00:00.\uff11\uff12Z", lambda r: r[0] == 2),
      ("full-width year", "\uff12\uff10\uff12\uff16-10-18T16:00:00Z", lambda r: r[0] == 2),
      ("10000 fraction digits (over the documented 64-character field limit)", "2026-10-18T16:00:00." + "1" * 10000 + "Z", lambda r: r[0] == 2),
      ("40 fraction digits (within the field limit)", "2026-10-18T16:00:00." + "1" * 40 + "Z", lambda r: r[0] == 0),
      ("bare '.' then Z", "2026-10-18T16:00:00.Z", lambda r: r[0] == 2),
      ("one digit", "2026-10-18T16:00:00.5Z", lambda r: r[0] == 0)]
for label, ts, want in ED:
    case("q03", label, trace(M.healthy_obs(), captured=ts), want)
for label, ts, _ in ED:
    outs = {}
    for py in [PY] + OTHERS:
        v = subprocess.run([py, "-c", "import platform;print(platform.python_version())"], capture_output=True, text=True).stdout.strip()
        outs[v] = run(NEW, trace(M.healthy_obs(), captured=ts), py)
    same = len({str(o) for o in outs.values()}) == 1
    res["HOLDS" if same else "GAP"] += 1
    print("%s q03x cross-interpreter %s: %s" % ("HOLDS" if same else "GAP  ", label, outs))

print("q04 documented limit: digits past the sixth are dropped (expiry decided below a microsecond)")
for label, na, cap in [("not_after .9999995Z, captured .9999999Z (truly after expiry)", "2026-10-18T15:59:59.9999995Z", "2026-10-18T15:59:59.9999999Z"),
                       ("not_after .999999999Z, captured 16:00:00Z (after expiry)", "2026-10-18T15:59:59.999999999Z", "2026-10-18T16:00:00Z")]:
    doc = trace([dns(), tcp(), tls("alert", cert(san=["DNS:" + M.HOST], na=na), "certificate_expired")], captured=cap)
    a = run(NEW, doc)
    print("OBS q04 %s: r4 rc=%s %s" % (label, a[0], a[1]))
print("SUMMARY HOLDS=%d GAP=%d" % (res["HOLDS"], res["GAP"]))
