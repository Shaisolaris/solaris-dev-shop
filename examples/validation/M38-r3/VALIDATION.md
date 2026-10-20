# M38 r3 validation of G38 r3 b542851 (Grok self-validation, not independent review)

Verdict: **FAIL (one P2, the M38 r2 P2-1 class still open).** Every M38 r2 case is fixed: restrictions written with
the guarded words in a copyright line, and added terms in the Apache appendix, are no longer accepted. But the r3
guard is a word list, and ordinary restrictive wording that avoids those words still comes out as MIT, consistent,
exit 0. This is Grok checking a Grok build. It is not independent review, accepts nothing and is not a legal opinion.

## Own-patch disclosure
G38 r3 generalises my own M38 r2 proposed-fix.patch. I wrote a new probe (oracle/m38r3_probe.py) aimed at the word
list rather than reusing only my M38 r2 oracle, which the fix was shaped to pass.

## Binding (raw/binding-verify.txt)
- Candidate b5428517178c032cea8af6bd7ef626e8db4a07b4 on review/grok-g38-authority-consistency (remote re-checked,
  unmoved), fast-forward from r2 01c9afb.
- G38-r3.patch sha256 fa59f5b1...18e7 equals `git diff --binary 01c9afb b542851`; MANIFEST.sha256 33/33 match.
- Evaluated in a detached clone; `git status --porcelain --ignored` empty after every run.

## M38 r2 findings, status at r3
| M38 r2 item | Status | Evidence |
|---|---|---|
| P2-1 restrictions in copyright lines or the Apache appendix | fixed for every M38 r2 case; class still open (P2-1 below) | M38 r2 oracle R10 copyright and appendix subs pass on all four Pythons |
| P4-1 `--out` naming an existing folder gives a traceback | fixed | R10 `provenance_out_existing_folder_exit_2` passes |
| P4-2 other pyproject license forms reported undeclared | fixed | builder test; O11 detail |
| P4-3 bold README `**GPL-3.0**` not read | open (not in r3 scope) | the only failing M38 r2 oracle sub (11/12) |

## Finding
- **P2-1 A restriction in the MIT copyright line that avoids the guarded words is still accepted as MIT.** Each line
  below replaces the clean fixture's copyright line, and `provenance_check.py check` gives license MIT, result
  consistent, exit 0 (probe R1 to R5, same on 3.9.6, 3.11.16, 3.12.14, 3.13.15):
  - "Copyright (c) 2026 Oracle Test Holdings, noncommercial purposes" (`\bcommercial` does not match inside one word);
  - "..., which cannot be resold" (`\bnot` does not match inside "cannot");
  - "..., for academic research purposes exclusively";
  - "..., personal usage";
  - "..., redistribution never allowed".
  The docstring says the guard is "not a parser: a restriction worded without these words still passes", so this is
  disclosed. It stays P2 because the output still states the text is the MIT license, which is the exact M38 and
  M38 r2 P2 harm, and the wording above is plain, not adversarial. Controls: a plain holder and "All rights reserved."
  stay MIT (C1, C2); "commercial use prohibited" is caught (R6).

## Proposed fix (not applied)
proposed-fix.patch (provenance_check.py only): a holder is a name, so after its first comma only a company suffix
(inc, llc, ltd, gmbh, corp, co, plc, ag, sa, bv) or "and contributors" / "et al" may follow; any other comma clause
keeps the line in the compared text, so the text is unrecognised. Positive control on a copy (fix-positive-control.txt):
probes 8/8, M38 r2 oracle 11/12 (only P4-3), G38 tests OK, authority_oracle 8/8, the repository itself still
consistent with 65 declarations. Residual even with the fix: a restriction with no comma and no guarded word
("Copyright 2026 Acme noncommercial") would pass; listing the dropped copyright lines in the report for a human to read
would close that.

## Oracles and results (results/pyversions.txt)
| Python | m38r3 probes | M38 r2 oracle | G38 tests |
|---|---|---|---|
| 3.9.6 | 3/8 | 11/12 (P4-3) | OK |
| 3.11.16 | 3/8 | 11/12 | OK |
| 3.12.14 | 3/8 | 11/12 | OK |
| 3.13.15 | 3/8 | 11/12 | OK |

Builder authority_oracle (results/builder-oracle-3.9.6.txt): ACCEPTED 8/8; naive REJECTED 1/8; no-op REJECTED 1/8.
Full suite on fresh clones (results/full-suite-matrix.txt): 174 tests OK on all four Pythons; browser processes 0.

## Not done in this pass
Builder mutants not re-scored. No browser was launched.
