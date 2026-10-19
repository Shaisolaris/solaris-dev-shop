#!/usr/bin/env python3
"""M10 r4 probes (Grok self-validation) on the G10 r5 rework (Q1 keytool/certutil non-host spellings, Q2 split of a
bare name after a typed one). Each case runs r5 (NEW) and r4 (OLD, 69c6081) on the same synthetic trace.
Usage: python m10r4_probes.py PY NEW OLD M10_ORACLE_DIR. Synthetic data only; offline (M10 env guard).
v2: the email and Principal Name values are plain strings (no address-shaped text) so the published output
carries none; the tool classifies these entries by their type prefix. v1 outputs are kept unpublished."""
import json, subprocess, sys, tempfile
from pathlib import Path
PY, NEW, OLD, ODIR = sys.argv[1:5]
sys.path.insert(0, ODIR)
import m10_oracle as M
from m10_oracle import trace, dns, tcp, tls, cert
tmp = Path(tempfile.mkdtemp(prefix="m10r4-pr-")); n = [0]; AT = "@"; H = "api.shop.example"
res = {"GAP": 0, "HOLDS": 0, "OBS": 0}


def run(tool, doc):
    n[0] += 1; f = tmp / ("t%03d.json" % n[0]); f.write_text(json.dumps(doc), encoding="utf-8")
    r = subprocess.run([PY, tool, "diagnose", "--json", str(f)], capture_output=True, text=True, env=M.env())
    if "Traceback" in r.stderr:
        return r.returncode, "TRACEBACK", [], []
    try:
        j = json.loads(r.stdout)
    except ValueError:
        return r.returncode, "NOJSON", [], []
    codes = sorted(x["code"] for x in j.get("findings", []))
    det = [x.get("detail", "") for x in j.get("findings", [])]
    return r.returncode, "%s/%s [%s]" % (j.get("verdict"), j.get("layer"), ",".join(codes)), j.get("notes", []), det


def alert(san):
    return trace([dns(qname=H), tcp(), tls("alert", cert(san=san), "bad_certificate", sni=H)], host=H)


mm = lambda r: "TLS_NAME_MISMATCH" in r[1]
no_mm = lambda r: "TLS_NAME_MISMATCH" not in r[1] and r[0] in (0, 1) and r[1] not in ("TRACEBACK", "NOJSON")


def case(tag, label, doc, want, obs=False):
    a, b = run(NEW, doc), run(OLD, doc)
    ok = want(a); k = "OBS" if obs else ("HOLDS" if ok else "GAP")
    res[k] += 1
    print("%s %s %s\n    r5 rc=%s %s\n    r4 rc=%s %s" % (k.ljust(5), tag, label, a[0], a[1], b[0], b[1]))
    return a


print("s01 Q2 residual: a bare covering name after a NON-HOST entry in one pasted line (want: no mismatch)")
case("s01", "'DNS:other.example, URI:spiffe://shop.example/x, %s'" % H, alert(["DNS:other.example, URI:spiffe://shop.example/x, " + H]), no_mm)
case("s01", "'email:ops, %s'" % H, alert(["email:ops, " + H]), no_mm)
case("s01", "'DNS:other.example, Registered ID:1.2.3.4, %s'" % H, alert(["DNS:other.example, Registered ID:1.2.3.4, " + H]), no_mm)
case("s01", "keytool order 'DNSName: other.example, URIName: spiffe://x, %s'" % H, alert(["DNSName: other.example, URIName: spiffe://x, " + H]), no_mm)
print("s02 controls for s01 (want: mismatch, nothing covers)")
case("s02", "'DNS:other.example, URI:spiffe://x, DNS:other2.example'", alert(["DNS:other.example, URI:spiffe://x, DNS:other2.example"]), mm)
case("s02", "'DNS:other.example, URI:spiffe://x, other2.example'", alert(["DNS:other.example, URI:spiffe://x, other2.example"]), mm)
case("s02", "DirName with commas then nothing covering", alert(["DNS:other.example, DirName:/C=GB, O=Shop, CN=svc"]), mm)
print("s03 Q1 spellings: case and spacing variants beside DNS:other.example (want: mismatch)")
for lab, ex in [("URINAME:", "URINAME: spiffe://x"), ("uriname no space", "uriname:spiffe://x"), ("url= lower", "url=spiffe://x"),
                ("URI Name:", "URI Name: spiffe://x"), ("oidname=", "oidname=1.2.3.4"), ("Other-Name upper", "OTHER-NAME: 1.2.3"),
                ("DirectoryName:", "DirectoryName: CN=svc, O=Shop")]:
    case("s03", lab, alert(["DNS:other.example", ex]), mm)
print("s04 notes and detail after r5")
a = case("s04", "unknown typed spelling beside DNS: note no longer advises rewriting a non-host value as DNS",
         alert(["DNS:other.example", "Principal Name=svc"]),
         lambda r: not mm(r) and any("do not rewrite" in x for x in r[2]))
print("    r5 notes:", [x[:160] for x in a[2]])
a = case("s04", "mismatch detail lists host names only (no URI/email text)",
         alert(["DNS:other.example, URI:spiffe://shop.example/x, email:ops" + AT + "shop.example"]),
         lambda r: mm(r) and any("other.example" in d for d in r[3]) and not any("spiffe" in d for d in r[3]))
print("    r5 detail:", [d[:160] for d in a[3]])
print("s05 split edge observations")
case("s05", "DirName then bare host 'DirName:/C=GB, O=Shop, %s' (ambiguous; a confident mismatch would be wrong)" % H,
     alert(["DNS:other.example, DirName:/C=GB, O=Shop, " + H]), no_mm, obs=True)
case("s05", "no-space typed then bare 'DNS:a.example,%s'" % H, alert(["DNS:a.example," + H]), no_mm)
case("s05", "bare then typed '%s, URI:spiffe://x'" % H, alert([H + ", URI:spiffe://x"]), no_mm)
print("SUMMARY HOLDS=%d GAP=%d OBS=%d" % (res["HOLDS"], res["GAP"], res["OBS"]))
