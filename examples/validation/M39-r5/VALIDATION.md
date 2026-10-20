# M39 r5 validation of G39 r5 3f09063 (Grok self-validation, not independent review)

Verdict: **PASS. The older M39 r2 P3-2 (rewritten input was a plain GO) and P3-3 (verify exit 0 for the non-clean
verdicts) are fixed, and there is no P1, P2 or P3.** Grok checked a Grok build that the same agent made in the same
batch. This is not independent review, and it accepts nothing.

## Binding (raw/binding-verify.txt)
- Candidate: https://github.com/Shaisolaris/solaris-dev-shop/commit/3f0906314894de4a91c1a16802762549fd4303e1 on
  review/grok-g39-delivery-drill.
- Checked on a fresh clone from GitHub: one commit on top of r4 97d3d05, a fast-forward.
- G39-r5.patch equals the regenerated diff, and the MANIFEST code section equals the diff set (3 files).

## Findings status
| Item | Status | Evidence |
|---|---|---|
| Older P3-2: input rewritten by the run is plain GO | fixed | T01, T02, T03: NO_GO without accept_gaps, GO_WITH_GAPS with it, files named |
| Older P3-3: verify exits 0 for GO_WITH_GAPS and EVIDENCED_NO_ORDER | fixed by opt-in `--strict` (default kept) | T05: strict mapping is 0, 3, 4, 1, 2. T06: default unchanged |
| M39 r3 P3-1, P3-2 (fixed in r4) | still fixed | M39 r3 probes 6/6, M39 r4 probes 6/6 |

- The design choice on P3-3 checks out.
  - Flipping the default would fail the in-repo drill_oracle rows and the frozen M39 r2 and r3 checks, which read
    exit 0 for these verdicts.
  - No in-repo caller gates on the exit code. The COO and delivery-lead SKILL text require the verdict word GO.
  - The `default_mapping_changed` mutant below shows the drill/compat breakage directly.

## Probe written for this pass (oracle/m39r5_probe.py)
- 7/7 on all four Pythons.
- 3/7 at 97d3d05 (results/probe-r5-at-97d3d05.txt): T01, T02, T03 and T05 fail there.
- It is self-contained. It uses a bin/ tool script, a delivered G04 order from the G39 fixtures, and spellings the
  G39 tests do not use.

| Row | Check |
|---|---|
| T01 | `--src=inp.csv` rewritten by the run, delivered order: NO_GO without accept_gaps, GO_WITH_GAPS with it, text names the file |
| T02 | a file in an `--inputs` folder removed by the run is a named gap |
| T03 | a SQLite `-journal` sidecar rewritten by the run holds data, so it is a gap |
| T04 | false-positive guard: a `-shm` index next to a bound db and a file that appeared during the run are listed, not gaps (GO) |
| T05 | `--strict`: GO 0, GO_WITH_GAPS 3, EVIDENCED_NO_ORDER 4, NO_GO 1, invalid 2 |
| T06 | compatibility control: the default exit mapping is unchanged |
| T07 | control: a run that reads its inputs without changing them is a clean GO |

## Teeth (scripts/m39r5_teeth.py, results/teeth.txt)
The G39 tests catch every mutant, and so does at least one probe row.

| Mutant | Probe rows that catch it |
|---|---|
| rewrite never recorded | T01, T02, T03, T05 |
| verify ignores the rewrite | T01, T02, T03, T05 |
| every change is a rewrite (no appeared-file or -shm rule) | T04 |
| every sidecar exempt (-wal, -journal too) | T03 |
| rewrite gap dropped unless exit 1 | T01, T02, T03, T05 |
| --strict uses the default mapping | T05 |
| --strict gives exit 0 for GO_WITH_GAPS | T05 |
| default mapping changed to non-zero for non-clean verdicts | T01, T06 |

- Disclosed: one mutant was renamed after the run, in both the script and results/teeth.txt, from
  `rewrite_counts_without_accept_gaps` to `rewrite_gap_dropped_unless_exit_1`. The new name says what the edit does.
  The mutation and its results did not change.

## Regression (results/pyversions.txt, results/full-suite-matrix.txt)
- Same on 3.9.6, 3.11.16, 3.12.14 and 3.13.15:
  - M39 r5 probes 7/7, M39 r4 probes 6/6, M39 r3 probes 6/6, M39 r2 contract 4/4.
  - M39 oracle 8/9. The miss is D02, the intended r2 change, as in r2 to r4; the oracle was not edited.
  - G39 tests OK; drill PASSED; drill_oracle 18/18; naive 12/18; no-op 0/18; checkout clean.
- The four new or changed G39 tests fail at 97d3d05 (results/new-tests-at-97d3d05.txt).
- Full suite on fresh clones of the GitHub head: 314 OK on all four Pythons. No browser was launched (0 seen).

## Residuals (none blocking)
- P4-1: the `-shm` exemption goes by file name. A non-SQLite file named `X-shm` beside a bound `X` would also be
  exempt. SQLite `-shm` files hold no data, so a real database is not affected.
- OBS: the COO and delivery-lead SKILL text do not mention `--strict`. They already require the verdict word GO.
- OBS: G42 r4 1611581 carries the G39 r4 blobs. A G42 refresh is needed for it to carry r5.
