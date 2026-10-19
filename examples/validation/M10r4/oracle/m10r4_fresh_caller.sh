#!/bin/zsh
# M10 r4 fresh caller (Grok self-validation): env -i, a new HOME, a python3 shim, the M10 offline guard, and only the three
# commands in offline-trace-diagnosis.md, run in a /tmp copy of the candidate tree, on 4 NEW traces that exercise the r5
# fixes Q1 (keytool/certutil non-host spellings) and Q2 (bare name after a typed one) (built by M10's own trace helpers, not the candidate), with a hand answer written before running.
# Usage: zsh m10r4_fresh_caller.sh PYTHON CANDIDATE_TREE M10_ORACLE_DIR
PY=$1; C=$2; O=$3; F=/tmp/m10r4-fc
rm -rf $F; mkdir -p $F/home $F/bin $F/tree; rsync -a --exclude .git $C/ $F/tree/
printf '#!/bin/sh\nexec %s "$@"\n' "$PY" > $F/bin/python3; chmod +x $F/bin/python3
mkdir -p $F/tree/traces
/usr/bin/python3 - $O $F/tree/traces <<'PY'
import json, sys
sys.path.insert(0, sys.argv[1]); from m10_oracle import trace, dns, tcp, tls, cert, http
H, AT, d = "pay.ledger.example", "@", sys.argv[2]
def w(name, doc): open(f"{d}/{name}", "w").write(json.dumps(doc, indent=1))
w("a-keytool-mismatch.json", trace([dns(qname=H), tcp(), tls("alert", cert(san=["DNSName: ledger-old.example", "URIName: spiffe://ledger.example/ns/pay", "OIDName: 1.2.3.4"]), "bad_certificate", sni=H)], host=H))
w("b-bare-after-typed.json", trace([dns(qname=H), tcp(), tls("alert", cert(san=["DNS:ledger-old.example, " + H]), "bad_certificate", sni=H)], host=H))
w("c-certutil-covering.json", trace([dns(qname=H), tcp(), tls("alert", cert(san=["DNS Name=" + H, "URL=spiffe://ledger.example/ns/pay"]), "bad_certificate", sni=H)], host=H))
w("d-healthy.json", trace([dns(qname=H), tcp(), tls("ok", cert(san=["DNSName: " + H, "URIName: spiffe://ledger.example/ns/pay"]), sni=H), http(200)], host=H))
PY
cat > $F/tree/hand-answer.txt <<'TXT'
Hand answer (written before running; M10 r4):
a-keytool-mismatch: keytool DNSName ledger-old.example does not cover pay.ledger.example; URIName and OIDName are not host
  names and must not hide it -> TLS_NAME_MISMATCH, layer tls, exit 1, with an "ignored" note.
b-bare-after-typed: one-line 'DNS:ledger-old.example, pay.ledger.example'; the bare second name covers the host ->
  no TLS_NAME_MISMATCH; generic TLS_ALERT (bad_certificate), exit 1.
c-certutil-covering: certutil DNS Name= covers the host, URL= beside it -> no TLS_NAME_MISMATCH; TLS_ALERT, exit 1.
d-healthy: keytool DNSName covers, handshake ok, http 200 -> healthy, exit 0.
batch: 4 traces, none invalid.
TXT
cat $F/tree/hand-answer.txt
(cd $F/tree && find . -type f | sort) > $F/before.txt
run() { echo "\$ $1"; env -i HOME=$F/home PATH=$F/bin:/usr/bin:/bin PYTHONPATH=$O/inject M10_NET_LOG=$F/net.log PYTHONDONTWRITEBYTECODE=1 \
  /bin/bash -c "cd $F/tree && T=employees/infrastructure/network-engineer/netdiag.py && $1"; echo "[exit $?]"; }
echo "# m10r4 fresh caller $(date '+%F %T %Z'); python3 shim -> $($PY -c 'import platform;print(platform.python_version())'); offline guard on (M10_NET_LOG)"
run 'python3 $T diagnose traces/a-keytool-mismatch.json'
for x in a-keytool-mismatch b-bare-after-typed c-certutil-covering d-healthy; do
  run "python3 \$T diagnose traces/$x.json --json --out $x.report.json > /dev/null"
  echo "$x: $($PY -c 'import json,sys;j=json.load(open(sys.argv[1]));print(j["verdict"],j["layer"],sorted(f["code"] for f in j["findings"]),[n[:70] for n in j.get("notes",[]) if "ignored" in n])' $F/tree/$x.report.json)"
done
run 'python3 $T batch traces/ --workers 4'
/usr/bin/python3 - $F/tree <<'PY'
import json, sys
d = sys.argv[1]; g = lambda x: json.load(open(f"{d}/{x}.report.json"))
a, b, c, e = g("a-keytool-mismatch"), g("b-bare-after-typed"), g("c-certutil-covering"), g("d-healthy")
codes = lambda j: sorted(f["code"] for f in j["findings"])
ok = ("TLS_NAME_MISMATCH" in codes(a) and a["layer"] == "tls" and any("ignored" in n for n in a.get("notes", []))
      and "TLS_NAME_MISMATCH" not in codes(b) and "TLS_ALERT" in codes(b)
      and "TLS_NAME_MISMATCH" not in codes(c) and "TLS_ALERT" in codes(c) and e["verdict"] == "healthy")
print("matches the hand answer:", ok)
PY
(cd $F/tree && find . -type f | sort) > $F/after.txt
echo "network attempts logged: $( [ -f $F/net.log ] && wc -l < $F/net.log | tr -d ' ' || echo 0)"
echo "stray files: $(comm -13 $F/before.txt $F/after.txt | grep -v '\.report\.json$' | tr '\n' ' ')"
echo "HOME after: $(find $F/home -mindepth 1 | wc -l | tr -d ' ') entries"
rm -rf $F
