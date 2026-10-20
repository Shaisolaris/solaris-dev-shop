# M39 r4 validation of G39 r4 97d3d05 (Grok self-validation, not independent review)

Verdict: **PASS. M39 r3 P3-1 and P3-2 are fixed, and there is no P1 or P2.** Grok checked a Grok build made in the
same batch by the same agent. This is not independent review and accepts nothing.

## Binding (raw/binding-verify.txt)
- Candidate 97d3d05d92daa452c3eab668aa821fafd0d25bfa on review/grok-g39-delivery-drill, re-checked on the remote.
- It is one commit on top of r3 9ab3562, a fast-forward.
- G39-r4.patch equals the regenerated diff; MANIFEST.sha256 equals the diff set (3 files).

## Findings status
| M39 r3 item | Status | Evidence |
|---|---|---|
| P3-1 `..` spellings inside ROOT silently unbound | fixed | M39 r3 probes R01 and R06 now pass: 6/6 on all four Pythons (r3: 4/6) |
| P3-2 absolute input outside ROOT skipped without a note | fixed | M39 r4 probes S01 and S03: listed as `unbound_inputs` in the record and in verify, with a note |
| Older P3-2 input rewritten by the run is plain GO | open (documented, decision for root) | unchanged |
| Older P3-3 verify exits 0 for GO_WITH_GAPS and EVIDENCED_NO_ORDER | open (documented, decision for root) | unchanged |

## Probe written for this pass (oracle/m39r4_probe.py): 6/6 on all four Pythons; 1/6 at r3
| Row | Check |
|---|---|
| S01 | `..` through a symlinked folder that points outside ROOT: not bound to a ROOT file; listed as unbound in the record and in verify |
| S02 | `..` through a symlinked folder inside ROOT: bound to the file the OS reads, and a change to it is caught |
| S03 | `--src=../../outside/o.csv`: listed as unbound, with the verify note |
| S04 | a missing `..` path is not listed; the record carries an empty list |
| S05 | `..` into .delivery is never bound as an input |
| S06 | control: a fresh record verifies GO |

- Disclosed authoring fix: in my first S04 and S05 the probed spelling came first. The shared reader reads its first
  argument, so the run itself exited 1. I put the real input first. No tool behaviour was involved.
- G39 r4 resolves `..` with realpath, not the lexical normpath that M39 r3 proposed. S02 shows why: the lexical form
  would bind a different file when a symlink precedes the `..`. The lexical mutant fails S02.

## Teeth (scripts/m39r4_teeth.py, results/teeth.txt)
Every mutant is caught by the G39 tests and by at least one probe.
| Mutant | Caught by the probes |
|---|---|
| lexical normpath | R01, R06, S02 |
| `..` branch removed | R01, R06, S01, S02, S03 |
| unbound not recorded | S01, S03 |
| verify does not surface it | S01, S03 |

## Regression (results/pyversions.txt, results/builder-oracle.txt)
- M39 r2 contract: 4/4.
- M39 oracle: 8/9. The miss is D02, the intended r2 change, as in M39 r2 and r3; the oracle was not edited.
- G39 tests OK; drill PASSED; drill_oracle 18/18; naive 12/18; no-op 0/18.
- Full suite on fresh clones: 311 OK on all four Pythons (results/full-suite-matrix.txt).
- The checkout was clean after every run. No browser was launched.
