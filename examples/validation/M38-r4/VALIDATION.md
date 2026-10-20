# M38 r4 validation of G38 r4 ba70b69 (Grok self-validation, not independent review)

Verdict: **PASS with one new P4 observation; M38 r2 P4-3 still open.** Restricted copyright lines, including wording
written for this pass that the builder tests do not use, are no longer read as MIT. Ordinary holders stay MIT, and every
copyright line that was set aside is now listed in the report for a person to read. This is Grok checking a Grok build,
built in the same batch by the same agent. It is not independent review, accepts nothing and is not a legal opinion.

## Own-build disclosure
G38 r4 was built by me from my own M38 r3 proposed patch plus a wider word list and the listed lines. I wrote a new
probe for this pass (oracle/m38r4_probe.py) with restrictions phrased differently from the builder tests and from my
M38 r3 probe, and I reran the M38 r3 probe and the M38 r2 oracle unchanged.

## Binding (raw/binding-verify.txt)
- Candidate ba70b6934a13f931b8533df9fa947802d610d15b on review/grok-g38-authority-consistency (remote re-checked), a
  fast-forward of one commit from r3 b542851.
- G38-r4.patch equals `git diff --binary b542851 ba70b69`; MANIFEST.sha256 3/3 match; manifest set equals the diff set
  (provenance_check.py, provenance-integrity.md, tests/test_g38_capability.py).
- Evaluated in a detached clone; `git status --porcelain --ignored` empty after every run.

## M38 r3 findings, status at r4
| M38 r3 item | Status | Evidence |
|---|---|---|
| P2-1 restrictions avoiding the guarded words read as MIT | fixed | M38 r3 probe 8/8 on r4 (3/8 on b542851); m38r4 probe core 13/13 (6/13 on b542851) |
| residual: no comma and no listed word | disclosed and now visible | X01: "Copyright 2026 Acme for students and teachers" is MIT but listed in license_copyright_lines and the text report |
| M38 r2 P4-3 bold README `**GPL-3.0**` not read | open (not in r4 scope) | the only failing M38 r2 oracle sub, 11/12 |

## Probe (oracle/m38r4_probe.py, results/probe-*)
- R01 to R08, each must be unrecognised with exit 1: ", strictly non-commercial", ", resale is not permitted",
  " (noncommercial)", ", internal evaluation", "; academic use", ", students only", " selling prohibited",
  ", which may not be sold". All pass on r4.
- C01 to C05, each must stay MIT with exit 0 and appear in license_copyright_lines and in the text report: "Acme, Inc.
  All rights reserved.", "Jane Doe and other contributors", "(c) symbol Acme BV", "Acme Inc, et al", and two copyright
  lines (both listed).
- Core 13/13 on r4 and 6/13 on b542851, Python 3.9.6, 3.11.16, 3.12.14 and 3.13.15.

## Oracles and results (results/pyversions.txt)
| Python | m38r4 probe (core) | M38 r3 probe | M38 r2 oracle | authority_oracle | G38 tests |
|---|---|---|---|---|---|
| 3.9.6 | 13/13 | 8/8 | 11/12 (P4-3) | ACCEPTED 8/8 | 21 OK |
| 3.11.16 | 13/13 | 8/8 | 11/12 | ACCEPTED 8/8 | 21 OK |
| 3.12.14 | 13/13 | 8/8 | 11/12 | ACCEPTED 8/8 | 21 OK |
| 3.13.15 | 13/13 | 8/8 | 11/12 | ACCEPTED 8/8 | 21 OK |

Repository self-check (results/repo-self-check.txt): consistent, 65 declarations, MIT, and the one copyright line
"Copyright (c) 2026 Solaris Dev Shop" is listed. Full suite on fresh clones (results/full-suite-matrix.txt): 176
tests OK on all four Pythons; browser processes 0. Builder mutants (84/84 killed) are in the G38 r4 handback; I did not
re-score them.

## Findings
- **P4-1 (new) Company names that contain a guard word are now unrecognised.** X02: "Sellers Inc", "Purpose Labs",
  "Distributed Systems Inc", "Never Settle GmbH" and "Copy Corp" give license_unrecognized on r4 (all MIT on r3). "Acme
  Co., Ltd." and "Acme, Inc., et al" were already unrecognised on r3, because a period inside the holder is refused.
  These are false alarms in the safe direction: the tool says it cannot recognise the text and guesses nothing, and the
  listed-lines output lets a person clear it. Noted so the word list is not widened further without a holder allow-list.
- M38 r2 P4-3 unchanged.

## Authoring note (disclosed)
- C04 first used "Acme, Inc., et al". A period inside a holder is refused by the documented r3 rule, so it moved to the
  X02 observation and C04 now reads "Acme Inc, et al". The numbers above come from the rerun.

Browser launches for this pass: 0.
