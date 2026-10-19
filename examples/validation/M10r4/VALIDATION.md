# M10 r4: recheck of the G10 rework r5 "Offline network diagnosis"

**Kind:** Grok self-validation (the same bot as the G10 builder). This is not independent review, which the QA2
contract still requires.

**Verdict: PASS.**
- Candidate: rework commit `865734eb290bb6cce89a142bad8811cbe1583766` on branch `review/grok-g10-network-diagnosis`.
  Its parent is r4 `69c6081` and its base is `02ba9c5`.
- Fixed: both M10 r3 findings, Q1 (P3) and Q2 (P3). No regression was found.
- Remaining: one P3, a residual of Q2 that already existed at r4 (V1 below). Q3 (P4) is unchanged and documented.
- No P1 or P2, so no proposed-fix patch is needed.

Runs: host macOS arm64, 2026-10-18, 19:28 to 19:44 PT.

## Binding (`raw/binding-verify.txt`, `raw/fetch.txt`)
- FETCH_HEAD equals the full SHA, fetched at 19:28:30 PT.
- `G10-r5.patch` is byte-identical to the 69c6081..865734e diff.
- `MANIFEST.sha256` (r5) verifies 25/25, and its file set equals the 02ba9c5..865734e diff set.
- The r5 change touches 6 files (+98/-12): netdiag.py, offline-trace-diagnosis.md, learnings, the G10 README, the builder
  oracle, and tests (+56 lines, now 47 G10 tests).

## Isolation
- The candidate ran from a detached worktree `/tmp/m10r4-eval`. The r4 tool was extracted with `git show` to
  `/tmp/m10r4-old` for comparison. The candidate worktree's status was empty before and after.
- week-grok was checked read-only, with branch, HEAD 02ba9c5, index hash and status hash compared:
  - unchanged from the M25 after-record at 19:26:10 PT, through `raw/weekgrok-mid.txt` (19:34:48 PT), to
    `raw/weekgrok-after.txt` (19:43:45 PT);
  - no separate before-record was taken at 19:28. The 19:26:10 M25 record is the closest earlier state.

## M10 r3 findings

| r3 finding | r5 result | Evidence |
|---|---|---|
| Q1 (P3): keytool `URIName`/`OIDName`/`Other-Name` and certutil `URL=` hide a real mismatch | **Fixed** | below |
| Q2 (P3): `DNS:a.example, api.shop.example` gives a false `TLS_NAME_MISMATCH` | **Fixed** | below |
| Q3 (P4): sub-microsecond truncation | **Unchanged**, as documented | q04 gives the same observations as r3 |

**Q1 evidence:**
- All 12 q01 spellings give `TLS_NAME_MISMATCH`, and the control holds (`raw/probes-r3-on-r5-*.txt`: 33 HOLDS, 0 GAP,
  identical on 3.9.6 and 3.12.14).
- The case and spacing variants (s03: `URINAME:`, `uriname:`, `url=`, `URI Name:`, `oidname=`, `OTHER-NAME:`,
  `DirectoryName:`) also give a mismatch, where r4 gave `TLS_ALERT`.
- The unknown-type note no longer advises rewriting a non-host value as DNS (s04).

**Q2 evidence:**
- q02 holds: the bare second name covers, giving `TLS_ALERT`.
- All five q02 controls are unchanged, including a DirName with commas.
- The no-space form `DNS:a.example,api.shop.example` now covers too (s05; r4 gave a mismatch).
- The mismatch detail now lists host names only (s04, closing the r3 cosmetic note).

**Regressions:**
- The M10 r2 regression script, r5 against r4 (`raw/regressions-r5-vs-r4-*.txt`), prints the same result on both tools
  for all 34 cases, on 3.9.6 and 3.12.14.
- Matrix (`raw/pyversions-matrix.txt`, `raw/oracle-cross-interpreter.txt`, `raw/adversarial-candidate.txt`):
  - G10 47, original 84 and full 131 tests are OK on 3.9.6, 3.11.16, 3.12.14 and 3.13.15.
  - The M10 oracle gives 10/10 ACCEPT on all four.
  - Adversarial: a01 shows identical bytes for 43 traces on 4 interpreters, and a02 shows 0 timestamp forms that
    differ by interpreter. a04 is the known criterion artifact, not a finding.

## Findings

### V1 (P3, residual of Q2, already at r4): a bare covering name after a non-host entry in one pasted line gives a false `TLS_NAME_MISMATCH`

Repro: `PY oracle/m10r4_probes.py PY NEW OLD oracle/m10`, section s01. Target `api.shop.example`, alert
`bad_certificate`.

| SAN item | r5 | r4 |
|---|---|---|
| `DNS:other.example, URI:spiffe://shop.example/x, api.shop.example` | `TLS_NAME_MISMATCH` | `TLS_NAME_MISMATCH` |
| `DNS:other.example, Registered ID:1.2.3.4, api.shop.example` | `TLS_NAME_MISMATCH` | same |
| `DNSName: other.example, URIName: spiffe://x, api.shop.example` (keytool order) | `TLS_NAME_MISMATCH` | same |
| control `..., URI:spiffe://x, DNS:other2.example` / `..., other2.example` | `TLS_NAME_MISMATCH` (correct) | same |

**Why it happens.** r5 splits a DNS, IP or bare piece at its own commas, but keeps a non-host piece whole so that
DirName values keep their commas. The bare `api.shop.example` after a URI or Registered ID is therefore glued into the
non-host value and ignored. The result is a confident, wrong mismatch whose detail says
`certificate host names ['other.example'] do not cover`.

`email:..., api.shop.example` holds only because no DNS entry is left, which makes the whole item "not understood".
s05 records the DirName form (`DirName:/C=GB, O=Shop, api.shop.example`) as an observation, since a DirName value is
ambiguous there.

**Why P3.** It is the same class and rationale as Q2: mixed hand-edited input that tool output rarely produces. It is
not a regression of r5.

**Suggested fix (not a patch).** Split a non-host piece at `", "` when the next chunk has no `=` and no `:` type prefix,
so DirName RDNs such as `, O=Shop` stay together. URI, email and Registered ID values contain no spaces, so `, ` ends
them. The `q2_split_nonhost_too` mutant shows that splitting every comma of a non-host piece is wrong: it is killed by
the builder oracle, the builder tests and both probe sets.

## Mutation teeth (`raw/teeth-3.12.14.tsv`, `raw/teeth-3.12.14-tally.txt`; `oracle/m10r4_teeth.sh`, `oracle/tally_m10r4.py`)

There are 37 mutants:
- **M10 r2's 23** (`oracle/make_mutants_r2_on_r4.py`): all anchors are unchanged on r5.
- **M10 r3's 7** (`oracle/make_mutants_r4.py`): `rg1_split_every_comma` was re-pointed at r5's new split block with the
  same meaning, so every comma splits.
- **7 new r5 mutants:**
  - `q2_rv_bare_split`, `q2_split_nonhost_too`;
  - `q1_rv_types`, `q1_no_url`, `q1_no_oidname`;
  - `q1_note_old`, `detail_all_san`.

| Scorer (3.12.14) | all 37 | r2 23 | r3 7 | r5 new 7 |
|---|---|---|---|---|
| M10 oracle (10, predates r3) | 17 | 17 | 0 | 0 |
| Builder oracle (14) | 35 | 23 | 6 | 6 |
| Builder G10 tests (47) | **36** | 23 | 6 | **7** |
| M10 r3 probes (pattern) | 12 | 3 | 4 | 5 |
| M10 r4 probes (pattern) | 12 | 2 | 3 | **7** |
| Union | **36** | 23 | 6 | **7** |

- **Only survivor on 3.12:** `rg3_no_truncate`. It is equivalent on 3.11+ (as in r3), and on 3.9.6 it is killed by the
  builder oracle (o14) and the tests (7 errors) (`raw/teeth-rg3_no_truncate-3.9.6.tsv`).
- **Candidate and baseline:** the candidate passes every scorer. The r4 tool is rejected by the builder oracle, the
  tests (27 failures) and both probe sets.
- **Stubs:** all four are rejected by both oracles. The tests column is n/a for stubs.
- **Not killed by the builder oracle, but killed by the tests and my r4 probes:** `detail_all_san` (cosmetic detail
  text).

## Fresh caller (`oracle/m10r4_fresh_caller.sh`; `raw/fresh-caller-3.12.14.txt`, `-3.9.6.txt`)

The run uses env -i, a new HOME, a `python3` shim, the M10 offline guard, a `/tmp` copy of the tree, and only the
three documented commands. It ran 4 new traces built with M10's trace helpers, against a hand answer written before
the run:
- a: keytool `DNSName` that does not cover, plus `URIName` and `OIDName`, should give `TLS_NAME_MISMATCH` with an
  "ignored" note;
- b: `DNS:ledger-old.example, pay.ledger.example` should give `TLS_ALERT`;
- c: certutil `DNS Name=` covering plus `URL=` should give `TLS_ALERT`;
- d: should be healthy.

All four match on both interpreters, and the results are identical apart from the interpreter line. `batch` reported
4 traces (healthy=1, localized:tls=3). There were 0 network attempts, no stray files and an empty HOME.

## Harness disclosures

**Probes v1 versus v2.**
- v1 of `m10r4_probes.py` used address-shaped synthetic values: an `email:` value and a `Principal Name=` value
  containing an at sign. The publish scan flagged them in the outputs.
- v2 uses plain strings instead (`email:ops`, `Principal Name=svc`). The tool classifies these entries by type prefix,
  so behaviour is the same.
- Check: the candidate's HOLDS/GAP pattern is identical under v1 and v2, and so is every mutant's kill status, 12 of
  37 both ways (`raw/teeth-r4probes-v2-recheck.txt`). The teeth table's r4-probe column was computed with v1.
- The v1 outputs are kept unpublished.

**Publish attempt.** A first local commit of this folder was made before the scan result was read. It was deleted
before any push (the branch never reached the remote), and the folder was re-staged after the fix.

## Limitations
- The full mutant set ran on 3.12.14 only, and `rg3_no_truncate` also ran on 3.9.6. There were no Linux or Windows
  runs, and Python 3.10 is not on the host.
- The keytool and certutil spellings are written from those tools' documented output formats. Real tool output was
  not captured on this host.
- The builder's own r5 mutants were not rerun. My 37 are an independent set.
- The offline guard blocks Python socket and DNS calls only. It is not a sandbox. All data is synthetic.

## Files
- `VALIDATION.md`: this report.
- `oracle/m10r4_probes.py`: s01 to s05.
- `oracle/make_mutants_r4.py`, `oracle/m10r4_teeth.sh`, `oracle/tally_m10r4.py`, `oracle/m10r4_fresh_caller.sh`.
- `oracle/`: the M10 r3 tools (probes, regressions, matrix, r2 mutants, `m10/`), copied unchanged for reproducibility.
- `raw/`: every run output named above.
