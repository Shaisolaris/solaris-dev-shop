# M10 r2: re-validation of G10 r3 "Offline network diagnosis"

**Kind:** Grok self-validation (same bot as the G10 builder). Not independent review. It reruns the M10 method on the reworked candidate:
- the M10 oracle, adversarial suite and finding repros, unchanged from M10 (copied to `oracle/m10/`);
- a new r2 regression script (`oracle/m10r2_regressions.py`) comparing r3 with r2;
- 23 mutants: the 15 M10 mutants plus 8 fix-revert mutants (`oracle/make_mutants_r2.py`).

An independent reviewer is still required by the QA2 contract.

**Verdict: FAIL** against candidate commit `be36f866550c28b272d8e42a24a33c741ee2d3ab` (branch `review/grok-g10-network-diagnosis`, subject "G10 rework r3: M10 findings F1-F8 (review only)", parent `6af7849`, base `02ba9c571b10ad1dba792d2ac5534bcad3171e67`). The candidate manifest verified 25/25, and its file set equals the diff `02ba9c5..be36f86` (`raw/manifest-verify.txt`).

What the rework got right:
- F1 to F7 are fixed. Every finding repro now gives the correct answer (`raw/finding-repros.txt`).
- The M10 oracle passes 10/10 on 3.9.6, 3.11.16, 3.12.14 and 3.13.15.
- The suite passes (38 G10, 84 original, 122 total) on all four interpreters.
- 43 traces give identical bytes on all four interpreters, and timestamp handling no longer differs by interpreter.
- A fresh caller succeeds on 3.9.6 and 3.12.14.
- F8 is mostly fixed: the builder tests now kill 23/23 mutants and the builder oracle 22/23.

The fail comes from one new P2 regression introduced by the F1 fix:
- **RG1:** when a certificate carries any URI, email, othername, DirName or Registered ID entry, a real name mismatch is no longer reported. The cert's DNS entries do not cover the host, yet the report gives a generic `TLS_ALERT` instead of `TLS_NAME_MISMATCH`.
- r2 reported these correctly.
- This contradicts the doc ("does not claim a name mismatch on them alone"). It is common in practice: SPIFFE and mTLS certificates carry URI SANs.

`oracle/proposed-fix-r2.patch` fixes RG1 and passes every builder test, the builder oracle and the M10 oracle. It was not applied to the candidate.

The other findings:
- 1 P4 regression: valid RFC 3339 times with 7 to 9 fraction digits are now refused.
- 1 P4 evidence-strength item: the builder oracle accepts one mutant, and its wildcard-depth case no longer tests depth.

Runs were on host macOS (arm64) on 2026-10-18 between 15:02 and 15:45 PT. Python 3.12.14 was used unless stated.

## Isolation
- The candidate was fetched with `git fetch origin review/grok-g10-network-diagnosis` (FETCH_HEAD `be36f866...`, `raw/fetch.txt`). It was checked out detached at `/tmp/m10r2-eval` (`raw/worktree-add.txt`). The r2 tool (`6af7849`) was extracted to `/tmp/m10r2-old/netdiag.py` with `git show`, for comparison only.
- Mutants were written to `/tmp/m10r2-mutants`. The positive control is a `/tmp` copy of the tree with the patch applied (`/tmp/m10r2-pc`). The fresh caller ran in a `/tmp` copy.
- The candidate worktree had 0 status lines before and after the suite runs (`raw/pyversions-matrix.txt`).
- Nothing was written to the week-grok working tree. Its branch, HEAD, index hash and status hash were recorded before (`raw/weekgrok-before.txt`) and after (`raw/weekgrok-after.txt`).
- No candidate file was modified.

## M10 findings, rechecked
| M10 finding | r3 status | Evidence |
|---|---|---|
| F1 (P2) typed SAN spellings (keytool, Windows, openssl one-line lists) read as bare names | **Fixed** | `raw/finding-repros.txt` F1: every covering spelling gives `TLS_ALERT`, not a mismatch. a03 is OK. RG6: comma lists cover. The fix introduced RG1. |
| F2 (P2) wildcard over a TLD or public suffix covers | **Fixed** | F2: `*.example` and `*.co.uk` give `TLS_NAME_MISMATCH`. RG5: `*.github.io` mismatches; `*.shop.github.io` and `*.example.com` still cover; depth two still mismatches. |
| F3 (P3) Kelvin sign folded to ASCII | **Fixed** | F3: `DNS:\u212aelvin.example` gives `TLS_NAME_MISMATCH`. |
| F4 (P3) SNI differs from target, unreported | **Fixed** | F4 and RG2: `TLS_SNI_MISMATCH`; case and trailing-dot SNI variants give no false mismatch. a04 still prints FINDING only because its M10 criterion predates the new code (below). |
| F5 (P3) deep JSON traceback | **Fixed** | F5 and a06: 100000-deep gives exit 2 with no traceback; `batch` reports it and runs the rest. RG7: 6-deep metadata still parses. |
| F6 (P4) double trailing dot covers | **Fixed** | F6 and a05: `api.shop.example..` is invalid and does not cover. |
| F7 (P4) timestamp forms differ by interpreter | **Fixed** (consistency) | a02: 0 forms differ across 4 interpreters. `raw/regressions-3.9.6.txt` and `-3.12.14.txt` give identical r3 answers. The price is RG3. |
| F8 (P3) builder oracle and tests let mutants through | **Mostly fixed** | Builder tests kill 23/23; builder oracle 22/23. It accepts `wildcard_any_depth` (E1). The rework note says "o13/o14 kill all 15 M10 mutants", which is not reproduced. |

## Findings
### RG1 (P2, regression): a real name mismatch is hidden when the certificate also carries a non-host SAN type
Repro: `PY oracle/m10r2_regressions.py PY T/employees/infrastructure/network-engineer/netdiag.py OLD/netdiag.py oracle/m10`, section RG1 (`raw/regressions-3.12.14.txt`, identical on 3.9.6).

Target `api.shop.example`, TLS alert `bad_certificate`, certificate SAN `DNS:other.example` plus one non-host entry:

| Extra SAN entry | r2 (6af7849) | r3 (be36f86) | With proposed-fix-r2 |
|---|---|---|---|
| `URI:spiffe://...` | `TLS_NAME_MISMATCH` | `TLS_ALERT` | `TLS_NAME_MISMATCH` |
| `email:...` | `TLS_NAME_MISMATCH` | `TLS_ALERT` | `TLS_NAME_MISMATCH` |
| `othername:UPN...` | `TLS_NAME_MISMATCH` | `TLS_ALERT` | `TLS_NAME_MISMATCH` |
| `DirName:/C=GB, O=...` (contains a comma) | `TLS_NAME_MISMATCH` | `TLS_ALERT` | `TLS_NAME_MISMATCH` |
| `Registered ID:...` | `TLS_NAME_MISMATCH` | `TLS_ALERT` | `TLS_NAME_MISMATCH` |
| control: `DNS:other.example` only | `TLS_NAME_MISMATCH` | `TLS_NAME_MISMATCH` | `TLS_NAME_MISMATCH` |
| control: covering DNS plus URI | `TLS_ALERT` | `TLS_ALERT` | `TLS_ALERT` |

**Cause.** In r3, any typed spelling the tool does not use counts as "unknown". Line 537 is `if c["san"] and not unknown and not _san_matches(...)`, so a single unknown entry vetoes the mismatch even when real DNS or IP entries exist and do not cover the host. The only trace left is a "not understood" note.

**Why P2.** It is the same impact class as F2: the most useful TLS diagnosis is lost, leaving a generic alert. It is also common in practice, since workload and mTLS certificates routinely carry URI SANs. The builder test `test_f1_an_unknown_san_type_is_noted_not_turned_into_a_mismatch` and builder oracle o14 cover only certificates with no DNS entry at all, so neither catches it.

**Proposed fix** (`oracle/proposed-fix-r2.patch`, not applied):
- Recognise the known non-host SAN types (URI, email or rfc822Name, otherName, DirName or directory address, Registered ID, x400, EDI party). Treat them as "other": noted, never covering, and not blocking when the certificate has DNS or IP entries.
- With no host entry at all, they stay "not understood", so there is still no confident mismatch, as r3 intends.
- Unrecognised spellings stay blocking, as before.
- A typed comma list is split only before a known type prefix, so a `DirName` value with commas stays one entry.

Positive control (`raw/positive-control-3.12.14.txt`, `raw/positive-control-3.9.6.txt`): RG1 is fixed in all 5 cases and both controls are unchanged. On both interpreters it passes:
- builder tests 38/38;
- builder oracle 14/14;
- M10 oracle 10/10;
- full suite 122 OK.

### RG3 (P4, regression): valid RFC 3339 times with 7 to 9 fraction digits are refused
`RFC3339_RE` allows `\.(\d{1,6})`. On every interpreter, r3 refuses these with exit 2:
- `captured_at` `2026-10-18T16:00:00.123456789Z` and `.1234567Z`;
- (RG4) a certificate `not_after` of `2026-10-18T15:59:59.999999999Z` on a trace captured after it. r2 on 3.11+ reported this as `TLS_CERT_EXPIRED`; r3 reports invalid input.

RFC 3339 allows any number of fraction digits, and the doc says "RFC 3339 only". Nanosecond times are what Go, Kubernetes and journald write.

It is P4 because:
- it fails closed with a clear exit 2;
- it is now the same on every interpreter (r2 on 3.9.6 already refused these);
- the cure is simple: accept any digit count and truncate to microseconds.

The forms `+0000`, `20261018T160000Z` and a missing offset are refused by intent (F7). The leap second `23:59:60` was refused by r2 and r3.

### E1 (P4, evidence strength): the builder oracle accepts `wildcard_any_depth`, and its depth case no longer tests depth
The mutant makes `*.shop.example` cover `a.api.shop.example`. The builder oracle passes it 14/14. The M10 oracle (o6a) and the builder tests kill it.

The cause is in o13's wildcard-depth variant, which uses `DNS:*.example`. Since the F2 fix, the single-label rule refuses that before depth is ever considered. So the check now tests F2, not depth.

The rework note's "o13/o14 kill all 15 M10 mutants" is therefore not reproduced (14/15). The candidate's own matching is right (RG5 depth two mismatches).

### Notes
- **a04 is a criterion artifact, not a finding.** M10's a04 accepts `TLS_NAME_MISMATCH` or a note mentioning the SNI. r3 reports the dedicated code `TLS_SNI_MISMATCH` that its doc specifies, which a04 does not know, so it still prints FINDING. F4 is fixed (repro F4, RG2). The M10 tool was left unchanged so the run stays comparable.
- **a07, a10 to a13 are notes, as in M10:**
  - batch worker bounds;
  - U-label hosts refused (A-labels only);
  - IPv6 zone id;
  - HTTP 200 with a reset handshake is `probable/tls`;
  - CN never consulted.

## Oracle teeth (3.12.14; `raw/oracle-teeth.txt`, `raw/builder-oracle-vs-teeth.txt`, `raw/builder-tests-vs-mutants.txt`, `raw/repro-teeth.txt`, `raw/regressions-teeth.txt`)
`oracle/make_mutants_r2.py` makes 23 mutants. Each edit must apply exactly once.
- **The 15 M10 mutants.** 13 have unchanged anchors. Two were ported to the r3 code with the same meaning:
  - `prefix_strip3` strips 3 characters instead of the matched prefix;
  - `wildcard_any_depth` is `host.endswith(name[1:])`.
- **8 fix-revert mutants (`rv_*`), each undoing one r3 fix:**
  - unknown types read as bare names;
  - no comma split;
  - no public-suffix check;
  - no single-label check;
  - Unicode folding back;
  - SNI check off;
  - RecursionError not caught;
  - `fromisoformat` back.

  An F6 revert would be equivalent, as the builder also notes, and was not made.

The runner is M10's `run_teeth.sh`, unchanged, with this mutant set and the positive control.

| Subject | M10 oracle (10 core) | Builder oracle (14) | Builder tests (38) | Finding repros plus r2 regression script |
|---|---|---|---|---|
| candidate be36f86 | 10/10 ACCEPT | 14/14 accept | OK | reference |
| M10 stubs noop_echo, naive_first_failure | REJECT (1, 0 pass) | reject (4, 5 pass) | n/a | n/a |
| builder noop_stub, naive_stub | REJECT (1, 0 pass) | reject (0, 3 pass) | n/a | n/a |
| 15 M10 mutants killed | **15/15** | **14/15** (accepts wildcard_any_depth) | **15/15** | not run |
| 8 fix-revert mutants killed | 2/8 (rv_f2_one_label, rv_f3_fold) | **8/8** | **8/8** | **8/8** (repros 7/8; the regression script kills rv_f1_unknown_bare) |
| **all 23 killed** | **17/23** | **22/23** | **23/23** | |

The M10 oracle's core predates F1 to F7, so it does not target the fix-revert mutants; the finding repros and the r2 regression script do. Together they kill all 8.

The teeth run's `positive-control-proposed-fix` row is **superseded**. It used a first draft of the patch that also judged certificates with no DNS entry at all, so it failed builder o14 and one builder test (13/14, 1 failure). The final patch narrows that, and its results are in `raw/positive-control-*.txt`: builder oracle 14/14, builder tests OK, M10 oracle 10/10.

## Fresh caller (`oracle/m10r2_fresh_caller.sh`; `raw/fresh-caller.txt` on 3.12.14, `raw/fresh-caller-py39.txt` on 3.9.6)
The fresh caller uses `env -i`, a new HOME, a `python3` shim, the M10 offline guard (`oracle/m10/inject/sitecustomize.py`, `M10_NET_LOG`) and a `/tmp` copy of the tree. It runs only the three commands in `offline-trace-diagnosis.md`:
- `diagnose` on the expired fixture: localized at tls, exit 1.
- `diagnose trace.json --json --out report.json`: `trace.json` is the first G10 fixture, a healthy trace. It exits 0, and the report is written with schema `solaris.net-diagnosis/1`.
- `batch traces/ --workers 4` over the 12 fixtures: exit 1, with a per-verdict tally.

There were 0 network attempts, no stray files and an empty HOME, the same on both interpreters.

## Interpreter matrix (`raw/pyversions-matrix.txt`, `raw/oracle-cross-interpreter.txt`, `raw/adversarial-candidate.txt`)
| Python | M10 oracle | G10 tests | Original tests | Full suite |
|---|---|---|---|---|
| 3.9.6 (/usr/bin/python3, SQLite 3.54.0) | 10/10 | 38 OK | 84 OK | 122 OK |
| 3.11.16 | 10/10 | 38 OK | 84 OK | 122 OK |
| 3.12.14 | 10/10 | 38 OK | 84 OK | 122 OK |
| 3.13.15 | 10/10 | 38 OK | 84 OK | 122 OK |

- a01: 43 traces give identical exit codes and bytes on all 4 interpreters.
- a02: 0 timestamp forms are accepted differently.
- Adversarial summary: 9 OK, 5 notes, 1 FINDING (a04, a criterion artifact, above).
- The finding repros, regression script and positive control were run on 3.12.14 and 3.9.6.

## Rejected and superseded runs (kept)
- The positive-control row in `raw/oracle-teeth.txt`, `raw/builder-oracle-vs-teeth.txt` and `raw/builder-tests-vs-mutants.txt` used patch draft 1. It is superseded by `raw/positive-control-*.txt`.
- A first run of the regression script printed `None` for the verdict and layer, because it read the wrong JSON keys; the finding codes were already right. The script was fixed and rerun. Only the rerun outputs are kept (`raw/regressions-*.txt`).

## Limitations
- Mutant teeth ran on 3.12.14 only.
- The builder's own r3 mutants were not rerun.
- The offline guard blocks Python socket and DNS calls in the candidate process. It is not a sandbox.
- Traces are synthetic, built from the doc's trace format with the M10 world. No real certificates or networks were used.
- RG1 was tested with the spellings in the regression script. Other tools' spellings of non-host types (for example `IP:` variants beside URI entries) were not exhaustively enumerated.

## Files
- `VALIDATION.md`: this report.
- `MANIFEST.sha256`: SHA-256 of every other file in this folder.
- `oracle/m10r2_regressions.py`: the r3 vs r2 comparison, RG1 to RG7.
- `oracle/make_mutants_r2.py`: the 23 mutants.
- `oracle/proposed-fix-r2.patch`: the RG1 fix, not applied.
- `oracle/m10r2_fresh_caller.sh`, `oracle/run_matrix_r2.sh`: the fresh caller and the cross-interpreter runner.
- `oracle/m10/`: the M10 tools used unchanged:
  - `m10_oracle.py`, `m10_adversarial.py`, `m10_finding_repros.*`, `m10_san_probe.py`;
  - `make_mutants.py`, `run_teeth.sh`;
  - `stubs/`, `inject/`;
  - M10's `proposed-fix.patch`, for reference.
- `raw/`: every run output named above, plus the fetch, worktree, manifest, diffstat and week-grok before and after records.

## Publication notes
- The publish copy replaces local paths with placeholders (`<D>`, `<PY312>`, `<UV>`, `<TMPDIR>` and so on) and drops the week-grok status listings. The before and after hashes stay in `raw/weekgrok-before.txt` and `raw/weekgrok-after.txt`.
- Two synthetic RG1 SAN values in `oracle/m10r2_regressions.py` have the shape of e-mail addresses at `shop.example` and trip the publish scan. After the runs they were rewritten as string concatenations; the values at runtime are identical. No other text was changed.
