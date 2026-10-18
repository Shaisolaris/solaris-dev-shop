# G10 network diagnosis oracle and fixtures

`fixtures/` holds 12 synthetic traces (documentation address ranges, `.example` names) for
`employees/infrastructure/network-engineer/netdiag.py`:

| Fixture | Expected verdict |
|---|---|
| 01 clean control | healthy, every layer ok |
| 02 NXDOMAIN on both resolvers | localized dns |
| 03 DNS timeout, config has no route to the resolver | localized route (medium) |
| 04 blackhole route to the target | localized route |
| 05 traceroute goes silent, TCP times out | localized route |
| 06 certificate expired at capture time | localized tls |
| 07 name mismatch, DNS answer not verified | probable tls, candidates dns + tls |
| 08 TCP refused | localized application |
| 09 HTTP 503 through a proxy | localized application |
| 10 only a DNS answer | undetermined, candidates route + tls + application |
| 11 traceroute filtered but HTTP 200 | healthy |
| 12 TLS reset, no DNS evidence | probable tls, candidates dns + route + tls |

`diagnosis_oracle.py` generates its own traces from a seed (names and addresses the fixtures
do not use) and checks the JSON verdicts, so exit 0 alone proves nothing:

```bash
PY=python3.12
TOOL=employees/infrastructure/network-engineer/netdiag.py
$PY examples/capabilities/G10/diagnosis_oracle.py -- $PY $TOOL
$PY examples/capabilities/G10/diagnosis_oracle.py -- $PY examples/capabilities/G10/noop_stub.py    # must be REJECTED
$PY examples/capabilities/G10/diagnosis_oracle.py -- $PY examples/capabilities/G10/naive_stub.py   # must be REJECTED
```

Checks: o1 clean control proves every layer; o2 seven known faults localized; o3 incomplete
traces stay bounded candidate sets, never high confidence; o4 DNS pointing at the wrong
server is blamed on dns; o5 identical bytes on rerun and the same verdict for reordered or
reformatted input; o6 no false blame (filtered ICMP, certificate dates judged at capture);
o7 header values never echoed; o8 invalid input exits 2 and leaves the previous report;
o9 the next good run recovers; o10 no socket use under a socket-denying guard and the trace
folder unchanged; o11 600 shuffled traces with 4 workers plus 6 parallel runs.
The naive stub blames the first bad-looking observation, is always certain, uses the wall
clock for certificates, does a live lookup and copies headers.
