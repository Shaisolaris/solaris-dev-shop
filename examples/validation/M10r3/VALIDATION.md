# M10 r3: recheck of the G10 rework r4 "Offline network diagnosis"

**Kind:** Grok self-validation (same bot as the G10 builder). Not independent review. An independent reviewer is
still required by the QA2 contract.

**Verdict: PASS** against rework commit `69c60819eccadd6c7df4fcc514914efa11d86742` (branch
`review/grok-g10-network-diagnosis`, parent `be36f86`, base `02ba9c5`). All three M10 r2 findings are fixed:
- RG1 (P2): the real name mismatch is reported again;
- RG3 with RG4 (P4): RFC 3339 fractions of any length are accepted, and a nanosecond expiry is judged;
- E1 (P4): the builder oracle now kills `wildcard_any_depth`.

There is no P1 or P2 finding, so no proposed-fix patch is needed. There are two P3 findings (Q1, a residual of
RG1, and Q2, a regression) and one P4 (Q3). This follows the M13 r2 precedent, where a pass with a P3 regression
was a PASS.
- The manifest (`<D>/grok-output/G10/MANIFEST.sha256`) verified 25/25. Its file set equals the diff
  02ba9c5..69c6081, and `G10-r4.patch` equals the be36f86..69c6081 diff byte for byte (`raw/manifest-verify.txt`).
- The r4 RG1 code is exactly M10 r2's `proposed-fix-r2.patch` applied to be36f86. The only other `netdiag.py`
  changes are the RG3 hunks (`raw/rg1-fix-identity.txt`).
- The full suite is 127 OK (43 G10 + 84 other) on 3.9.6, 3.11.16, 3.12.14 and 3.13.15 (`raw/pyversions-matrix.txt`).
- The M10 oracle is 10/10 ACCEPT on all four (`raw/oracle-cross-interpreter.txt`), and the builder oracle is 14/14.
- The M10 adversarial suite matches r2: a01 shows identical bytes on 4 interpreters, and a02 shows 0 timestamp forms
  that differ by interpreter. a04 is the known criterion artifact, not a finding (`raw/adversarial-candidate.txt`).
- The M10 finding repros F1 to F8 print the same results as at r3 (`raw/finding-repros.txt`).

Runs were on host macOS (arm64) on 2026-10-18, between 17:36 and 18:03 PT. Unrelated builder jobs ran on the same
host at the same time.

## Isolation
- The commit was fetched read-only into the programme repo, and FETCH_HEAD equals the full SHA (`raw/fetch.txt`).
  Then `git worktree add --detach /tmp/m10r3-eval 69c6081...`. The r3 tool was extracted with `git show` to
  `/tmp/m10r3-old`, for comparison only. Nothing was cloned onto another machine.
- The builder's worktree was not written. Branch, HEAD, index hash and status hash are identical before (17:36:44
  PT) and after (18:03:42 PT), and the status listing is byte-identical. The checks are read-only and use
  `git --no-optional-locks status`.
- Mutants ran in `/tmp` copies, and every candidate run went through the M10 offline guard. The candidate worktree's
  status was empty before and after.

## M10 r2 findings
| r2 finding | r4 result | Evidence |
|---|---|---|
| RG1 (P2) non-host SAN type hides a real mismatch | **Fixed** for openssl spellings: URI, email, othername, DirName with a comma and Registered ID all give `TLS_NAME_MISMATCH`, and both controls are unchanged. The certutil `RFC822 Name=`, `Other Name:`, `Directory Address:` and `Registered ID=` spellings and keytool `RFC822Name`, `EDIPartyName` and `X400Address` also work. **Residual: Q1** | `raw/regressions-r4-vs-r3-*.txt` RG1, `raw/probes-r3-*.txt` q01 |
| RG3 (P4) 7 to 9 fraction digits refused | **Fixed**: they exit 0. `+0000`, the basic format, a missing zone and the leap second stay refused. Non-ASCII digits are refused the same way on all 4 interpreters (q03x) | RG3, q03 |
| RG4 (P4) nanosecond `not_after` | **Fixed**: `TLS_CERT_EXPIRED` | RG4, fresh caller c |
| E1 (P4) builder oracle accepts `wildcard_any_depth` | **Fixed**: o13 rejects it (teeth below) | `raw/teeth-3.12.14.tsv` |

Every other regression case (RG2, RG5, RG6, RG7) prints the same r4 and r3 results.

## Findings
### Q1 (P3, residual of RG1): keytool and certutil spellings of URI and other non-host types still hide a real mismatch
Repro: `PY oracle/m10r3_probes.py PY NEW OLD oracle/m10`, section q01. Target `api.shop.example`, alert
`bad_certificate`, SAN `DNS:other.example` plus one entry:

| Extra entry (tool) | r4 | r3 |
|---|---|---|
| `URIName: spiffe://...` (Java keytool) | `TLS_ALERT` | `TLS_ALERT` |
| `OIDName: 1.2.3.4` (keytool) | `TLS_ALERT` | `TLS_ALERT` |
| `Other-Name: ...` (keytool) | `TLS_ALERT` | `TLS_ALERT` |
| `URL=spiffe://...` (Windows certutil) | `TLS_ALERT` | `TLS_ALERT` |
| controls: openssl `URI:`, certutil `Other Name:`, keytool `RFC822Name:` and 5 more (8 in all) | `TLS_NAME_MISMATCH` | `TLS_ALERT` |

`NON_HOST_TYPE_RE` lists openssl names and some certutil names, but not keytool's `URIName`, `OIDName` or
`Other-Name`, nor certutil's `URL`. So these count as "not understood" and block a confident mismatch. The note
then advises "paste them as DNS:<name> or IP:<address>", which is wrong advice for a URI.

The doc states this fail-safe ("a new non-host spelling outside it is not understood"). But F1's fix claims keytool
and Windows spellings, and the URI is the most common non-host type in workload certificates, which is why RG1 was
P2. With these two tools the RG1 symptom remains. It is P3 rather than P2 because it fails safe, is documented, and
openssl, the most common source of pasted SANs, works.

Suggested fix, not a patch: add `uri ?name`, `url`, `oid ?name` and `other-name` to `NON_HOST_TYPE_RE` and
`TYPED_SPLIT_RE`. Also say "not a host name type" in the note instead of suggesting DNS.

### Q2 (P3, regression): a typed one-line list with a bare name after the first entry now gives a false `TLS_NAME_MISMATCH`
SAN item `DNS:a.example, api.shop.example`, target `api.shop.example` (q02):
- r4 gives `TLS_NAME_MISMATCH` (high confidence), with the detail "certificate names ['dns:a.example,
  api.shop.example'] do not cover api.shop.example" and no note.
- r3 gives `TLS_ALERT`, which is correct: the bare second name covers the host.

The new `_san_parts` splits a typed list only before a known type prefix, which keeps DirName commas together, so
the bare second name is glued to the first entry. Untyped lists, typed lists with every entry typed (with or without
spaces), and DirName lists all still work (q02 controls).

It is P3, not P2: the result is a wrong confident diagnosis, but the spelling mixes a typed and a bare entry in one
item, which hand-edited input produces and tool output rarely does.

Suggested fix: after the typed split, split any piece that contains a comma and is not a DirName or
Directory Address value. The `rg1_split_every_comma` mutant shows that splitting every comma is wrong, since the
builder tests and o14 kill it.

### Q3 (P4): sub-microsecond `not_after` and `captured_at` are compared after truncation
With not_after `...59.9999995Z` and captured_at `...59.9999999Z`, the certificate is truly expired at capture. r4
compares the truncated values, which are equal, so it is not judged expired (`TLS_ALERT`, q04).

This is the documented limit "two times that differ only past the sixth digit compare as equal". It only matters
within 1 microsecond of expiry, hence P4. The nanosecond expiry in RG4 and the fresh caller is judged correctly.
The same limit appears in G13 r3 (M13 r3 T1).

### Notes
- When a one-line list does not cover the host, the mismatch detail prints the whole list item as one "name"
  (`['dns:ledger-old.example, uri:..., email:...']`), although the entries were parsed separately. This is cosmetic.
- The builder's equivalence claim for `r4_rg3_no_truncate` holds. On 3.11, 3.12 and 3.13, `fromisoformat` already
  truncates 7 to 9 digits; on 3.9.6 it raises `ValueError` (`raw/rg3-no-truncate-equivalence.txt`). The
  corresponding mutant here, `rg3_no_truncate`, survives every scorer on 3.12 and is killed by the builder oracle and
  tests on 3.9.6.

## Mutation teeth (`raw/teeth-3.12.14.tsv`; r4 mutants also on 3.9.6, `raw/teeth-r4-mutants-3.9.6.tsv`; `oracle/m10r3_teeth.sh`, `oracle/tally_m10r3.py`)
There are 30 mutants:
- **M10 r2's 23** (`oracle/make_mutants_r2_on_r4.py`). One anchor moved with RG1 and was re-pointed with the same
  meaning: `rv_f1_no_list_split` never splits a one-line list.
- **7 new r4 mutants** (`oracle/make_mutants_r3.py`):
  - `rv_rg1_other_blocks`, `rg1_other_alone_mismatches`, `rg1_note_dropped`, `rg1_split_every_comma`;
  - `rv_rg3_six_digits`, `rg3_rounded`, `rg3_no_truncate`.

The fourth scorer is the r3 probes: a mutant is killed when its pattern of HOLDS and GAP lines differs from the
candidate's.

| Scorer | 3.12.14 all 30 | 3.12.14 r4 mutants (7) | 3.9.6 r4 mutants (7) |
|---|---|---|---|
| M10 oracle (10, predates r3) | 17 | 0 | 0 |
| Builder oracle (14) | **29** | 6 | **7** |
| Builder tests (43) | **29** | 6 | **7** |
| M10 r3 probes | 8 | 4 | 5 |
| Union | **29** | 6 | 7 |

- The candidate passes all four scorers. The r3 tool fails builder o14, 19 builder tests (plus 7 errors) and 14
  probes, while the M10 oracle accepts it.
- All four stubs are rejected.
- The only union survivor on 3.12 is `rg3_no_truncate`, which is equivalent on 3.11+ (see Notes) and is killed on
  3.9.6.
- E1 is closed: `wildcard_any_depth` is killed by the M10 oracle (o6a), the builder oracle (o13) and the tests.

## Fresh caller (`oracle/m10r3_fresh_caller.sh`; `raw/fresh-caller-3.12.14.txt` and `-3.9.6.txt`, identical except for the interpreter line)
The run uses `env -i`, a new HOME, a `python3` shim, the M10 offline guard and a `/tmp` copy of the tree, and only
the three documented commands. The data is 4 new traces, built with M10's trace helpers, not the candidate. The hand
answer was written before the run:
- a: an mTLS one-line list `DNS:ledger-old.example, URI:..., email:security-team` (v2; v1 used an address-shaped value, same result, kept unpublished) for `pay.ledger.example` should give
  `TLS_NAME_MISMATCH` with an "ignored" note;
- b: a covering DNS entry beside a URI should give `TLS_ALERT`, not a mismatch;
- c: a nanosecond expiry before a nanosecond capture should give `TLS_CERT_EXPIRED`;
- d: a 9-digit captured_at should be healthy.

All four match on both interpreters. `batch` reports 4 traces (healthy=1, localized:tls=3). There were 0 network
attempts, no stray files and an empty HOME.

## Rejected and superseded runs (kept in `raw/superseded/`)
- **Probes v1** expected a 10000-digit fraction to parse. The tool refuses any time string over 64 characters by
  design, with a clear message, so v2 expects exit 2 there and adds a 40-digit case that parses. Only v2 is cited.
- **Teeth v1:** a relaunch helper missed the already-running 3.12 runner, because the pattern used an absolute path
  while the runner was started with a relative one. Two M10 runners then ran concurrently and shared per-subject
  scratch folders, so 18 subjects were scored twice and the scratch could collide. Both were stopped, the v1 TSV was
  set aside unused (`teeth-3.12.14-v1-two-concurrent-runners.tsv`), and the 3.12 teeth were rerun from scratch with
  one runner. The stop used `pkill -f` on the oracle script names. Only my processes were seen with those names,
  but the pattern was broader than my own runner.

## Limitations
- The full mutant set ran on 3.12.14 only, and the 7 r4 mutants also ran on 3.9.6.
- No Linux or Windows runs, and Python 3.10 is not on the host.
- The keytool and certutil spellings in q01 are written from those tools' documented output formats. Real tool
  output was not captured on this host.
- The builder's own 42 r4 mutants were not rerun. My 30 are an independent set.
- The offline guard blocks Python socket and DNS calls only. It is not a sandbox.
- All data is synthetic.

## Files
- `VALIDATION.md`: this report.
- `oracle/m10r3_probes.py`: q01 to q04.
- `oracle/make_mutants_r3.py`: the 7 r4 mutants.
- `oracle/make_mutants_r2_on_r4.py`: the r2 mutants, with one anchor re-pointed. The original
  `make_mutants_r2.py` is kept for reference.
- `oracle/m10r3_teeth.sh`, `oracle/tally_m10r3.py`: the teeth runner and tally.
- `oracle/m10r3_fresh_caller.sh` and `oracle/m10r2_fresh_caller.sh` (for reference).
- `oracle/m10r2_regressions.py`.
- `oracle/run_matrix_r3.sh`.
- `oracle/proposed-fix-r2.patch`: M10 r2's RG1 fix, now in r4.
- `oracle/m10/`: the M10 tools, unchanged.
- `raw/`: every run output named above, plus the fetch, worktree, manifest and week-grok records.
