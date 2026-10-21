# M38 r5 validation of G38 r6 e25d32c (Grok self-validation, not independent review)

Verdict: **PASS after one repair.** M38 r4 P4-1 (company names holding a guard word were unrecognised) and M38 r2
P4-3 (bold README `**GPL-3.0**` not read) are closed. The first build, G38 r5 f8f734c, read a mismatched pair such as
`**GPL-3.0*` as a license name; this probe found it (U01) and G38 r6 e25d32c fixes it. This is Grok checking a Grok
build made in the same batch by the same agent. It is not independent review, accepts nothing and is not a legal
opinion. No legal conclusion was changed: this is parsing of names and Markdown marks only.

## Binding (raw/binding-verify.txt)
- Candidate e25d32c0fdc3b39edf7df6acd56fa83294178465 on review/grok-g38-authority-consistency (remote re-checked),
  two fast-forward commits from r4 ba70b69 (r5 f8f734c, r6 e25d32c). Files: provenance_check.py,
  provenance-integrity.md, tests/test_g38_capability.py.
- `git status --porcelain --ignored` empty after every run.

## Probe (oracle/m38r5_probe.py, written for this pass, cases differ from the builder tests)
- C01 to C05: "Freedom Software Labs Ltd", "Modify Media LLC", "(c) Allow Partners AG", "Resale Analytics PLC",
  "Sold Out Records, LLC." stay MIT with exit 0 and are listed in license_copyright_lines.
- R01 to R07 stay unrecognised: "Personal Use Only LLC", "Not Transferable Ltd", "Non-Commercial Inc", five name
  words before Inc with a guard word, lower case "acme resale corp", a clause after the suffix, "Exclusively Licensed".
- M01 to M05: `__Apache-2.0__`, `` `GPL-3.0`, see LICENSE. ``, `*BSD-3-Clause*.` give license_mismatch; `**MIT**` and
  `_MIT_` are consistent and counted. U01: `**GPL-3.0*` is not read.
- Core 18/18 on r6 with Python 3.9.6, 3.11.16, 3.12.14 and 3.13.15; 17/18 on r5 f8f734c (U01); 8/18 on r4 ba70b69.
- Authoring note (disclosed): R04 first read "Acme Five Six Seven Eight Inc", which holds no guard word and was MIT on
  r4 too, so it tested nothing new. It now reads "Acme Sellers Six Seven Eight Inc". Numbers above are from the rerun.

## Builder evidence re-run (results/)
| Python | m38r4 probe core | M38 r3 probe | M38 r2 oracle | authority_oracle | G38 tests | full suite |
|---|---|---|---|---|---|---|
| 3.9.6 | 13/13 | 8/8 | 12/12 (was 11/12) | ACCEPTED 8/8 | 23 OK | 178 OK |
| 3.11.16 | 13/13 | 8/8 | 12/12 | ACCEPTED 8/8 | 23 OK | 178 OK |
| 3.12.14 | 13/13 | 8/8 | 12/12 | ACCEPTED 8/8 | 23 OK | 178 OK |
| 3.13.15 | 13/13 | 8/8 | 12/12 | ACCEPTED 8/8 | 23 OK | 178 OK |

The m38r4 X02 false alarms drop from 7/7 to 3/7: "Purpose Labs" (no suffix) and the two holders with a period inside
("Acme Co., Ltd.", "Acme, Inc., et al") stay unrecognised, as documented. The new builder tests fail at ba70b69
(both) and the emphasis test fails at f8f734c (results/new-tests-at-f8f734c-and-ba70b69.txt).

## Findings and residuals
- No P1, P2 or P3. U01 was found and repaired in this pass (r6).
- OBS X01: a company name holding a strong word ("Restricted Area Games Inc") is still unrecognised (safe direction).
- OBS X02 (disclosed residual, same class as M38 r4 X01): a capitalised restriction ending in a suffix that avoids the
  strong words ("Acme Never Sold Inc") reads MIT, but the line is listed for a person to read.
- Licensing judgment stays with the stronger lane; nothing here is a legal conclusion.

Browser launches for this pass: 0.
