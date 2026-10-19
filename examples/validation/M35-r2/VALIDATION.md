# M35 r2 validation of G35 r2 campaign accounting (Grok self-validation, not independent review)

Candidate: G35 r2 `34bb98f465901438fec47d6ac8beccc0edf8df70` (branch review/grok-g35-campaign-accounting), direct
parent G35 r1 `90da27cf1dd3466e34c89b2c4677b9e35dbaba1e`, on G14 r2 `6f7b23aa18413907c5fbd250daab475dc94e7a1e` (with
G13 r3 inside). Tool `employees/marketing/paid-ads-manager/campaign_ledger.py`, doc `campaign-accounting.md`.
Validator: Grok, the same agent family that built G35. This is self-validation, not independent review. Pass started
09:35 PT, Mon Oct 19 2026.

## Verdict

PASS (self-validation) with one P4 and OBS notes. No P1 or P2, so no proposed fix.

All three M35 findings are repaired:
- P2-1 (mixed windows): a spend or orders report whose window or as_of differs from the package is refused with exit 2
  and nothing written, and a contract with no as_of is refused too.
- P3-1: CPA is null (not "0.00") when spend is 0, and ROAS is null with it.
- P4-1: prohibited wording is caught through dash variants, fullwidth forms, no-break and repeated spaces, case and
  line breaks.

## Own-patch disclosure (important)

The r2 fix for P2-1 comes from my own M35 proposed patch (examples/validation/M35/proposed-fix-mixed-windows.patch
on 2598223f), generalized by the builder: one shared `_same_basis` check now runs on both G13 reports and also
requires the package as_of. A validator checking a fix it proposed tends to test what it expected. To offset that, I
did not stop at my M35 rows: F13 probes the generalized check beyond what my patch covered (orders report, offsets,
one-second as_of drift, missing as_of, naive times), and O14 probes the new folding with inputs my M35 oracle never
used. The builder also ran a copy of my M35 oracle in its handback (12/12). That is a builder re-run, not this
validation.

## Prerequisite chain

- The diff sha equals the patch file (`7df5aa44...8682`). The manifest has 3/3 entries, 0 mismatches, and its set
  equals the diff set. 90da27c is the direct parent and its parent is G14 r2 6f7b23a (raw/binding-verify.txt).
- The remote heads of G35, G14 and G13 are still 34bb98f, 6f7b23a and 5666e7b, so nothing in the chain is superseded.
  G35 r1 was validated by M35 (2598223f, FAIL with P2-1, P3-1, P4-1), G14 r2 by M14 r2 (60682d2f, PASS), G13 r3 by M13
  r3 (PASS).

## Method

- Oracle `oracle/m35r2_oracle.py`: the M35 v2 oracle (independent Decimal model written from the doc, audit hook for
  network and child processes) unchanged in F01-F12, plus two new rows:
  - F13 (scored): the same instant with another offset and an orders end written +00:00 are accepted; refused with
    exit 2 and no traceback: spend as_of +1s, orders as_of -1s, a missing as_of in either contract, a spend end one
    day later, an orders start one hour later and a naive start at another instant. Zero spend with a conversion and
    two zero-spend days give CPA null (ROAS null too). Prohibited wording is blocked through a non-breaking hyphen,
    en dash, minus sign, fullwidth letters, a no-break space, repeated spaces, upper case, a fullwidth #1, a line
    break and a soft hyphen standing for the dash. Clean copy stays ready.
  - O14 (OBS, not scored): invisible characters inside a word, a Cyrillic look-alike, a spaced or missing dash and two
    substring false positives.
- Negative control: the same oracle on the r1 tool (results/r1-tool-oracle-3.9.6.json) scores 11/14. It fails F05
  (CPA), F08 (windows and as_of) and 17 F13 subs: every refusal, both CPA checks and every folding case except upper
  case. So the new rows do tell r1 from r2.
- Four interpreters; mutation tests on 3.13.15 and 3.9.6 with the builder's 49 r2 mutants copied unchanged; a fresh
  caller. All runs were on rsync copies, and the candidate was never modified.

## Results

Matrix (results/pyversions-matrix.txt):

```
== 3.9.6 | g35: Ran 16 tests in 9.180s  OK  | full: Ran 150 tests in 24.480s  OK  | builder-oracle: ACCEPTED 12/12 | builder-naive: REJECTED 1/12 | builder-noop: REJECTED 0/12 | m35-oracle: M35 ORACLE 14/14 core PASS | m35-naive: M35 ORACLE 2/14 core FAIL | m35-noop: M35 ORACLE 2/14 core FAIL
== 3.11.16 | g35: Ran 16 tests in 7.283s  OK  | full: Ran 150 tests in 20.775s  OK  | builder-oracle: ACCEPTED 12/12 | builder-naive: REJECTED 1/12 | builder-noop: REJECTED 0/12 | m35-oracle: M35 ORACLE 14/14 core PASS | m35-naive: M35 ORACLE 2/14 core FAIL | m35-noop: M35 ORACLE 2/14 core FAIL
== 3.12.14 | g35: Ran 16 tests in 9.931s  OK  | full: Ran 150 tests in 25.462s  OK  | builder-oracle: ACCEPTED 12/12 | builder-naive: REJECTED 1/12 | builder-noop: REJECTED 0/12 | m35-oracle: M35 ORACLE 14/14 core PASS | m35-naive: M35 ORACLE 2/14 core FAIL | m35-noop: M35 ORACLE 2/14 core FAIL
== 3.13.15 | g35: Ran 16 tests in 9.671s  OK  | full: Ran 150 tests in 26.011s  OK  | builder-oracle: ACCEPTED 12/12 | builder-naive: REJECTED 1/12 | builder-noop: REJECTED 0/12 | m35-oracle: M35 ORACLE 14/14 core PASS | m35-naive: M35 ORACLE 2/14 core FAIL | m35-noop: M35 ORACLE 2/14 core FAIL
pycache in copy: 0
candidate status lines: 0
```

The oracle scores 14/14 on every interpreter (13 scored rows plus the O14 OBS row). The naive and no-op controls
score 2/14.

Mutation tests: **49/49 killed on 3.13.15 and 49/49 on 3.9.6** (results/teeth-*.log). Survivors:

- none

Fresh caller (results/fresh-caller.txt): every line of the README "Run" block, verbatim under `env -i` with a new
HOME and `STATE` a fresh temp folder, on 3.9.6 and 3.13.15. Each line gives its documented exit or oracle result, no
__pycache__ was written and the tree is unchanged.

## Findings

- **P4-1: invisible characters and look-alike letters still bypass the prohibited-wording check.** These come back
  ready_for_human_review:
  - "Guar\u00adanteed" (soft hyphen inside the word), "Guar\u200banteed" (zero-width space), "Guaran\u200dteed"
    (zero-width joiner), "Risk\u200b-free" (zero-width space before the dash);
  - "Gu\u0430ranteed" with a Cyrillic а.
  The soft hyphen is mapped to "-" only, so inside a word it splits the word instead of vanishing. Removing format
  characters (Unicode category Cf, which includes U+00AD, U+200B and U+200D) before matching would close the first
  group. Confusable letters need a skeleton map; open question 2 in the handback covers them only in part. Copy is
  still reviewed by a person (the status is ready_for_human_review, not published), so this stays P4.
- OBS:
  - "Risk - free" with spaces and "Riskfree" are not matched.
  - Substring matching gives false positives: "No riskier way" and "Our #10 pick" are blocked. This existed in r1.

## Disclosures

- Own-patch origin of the P2-1 fix, as described above.
- Oracle authoring fix after the first run (kept as results/kept/oracle-first-run-3.9.6.json, 13/14): I first expected
  a naive spend start to be refused. The G35 contracts declare `"timezone": "UTC"`, so G13 reads a naive time as
  UTC. A naive start at the same instant is the same window and is now expected to be accepted, and a naive start at
  another instant is expected to be refused (it is). No candidate behavior changed my expectation for any other sub.
- Harness: the scripts are copies of the M35 ones with paths changed to M35-r2 (scripts/). My first matrix launch
  passed the wrong argument (the mutant count instead of the folder), so I stopped it within a minute, removed its
  temp copy and reran it. The fresh caller chained after the rerun was also given the folder instead of an output
  file, so it wrote nothing; I ran it again with the right argument. No result from either bad launch is used.
- Before and after records of week-grok are in raw/weekgrok-before.txt and raw/weekgrok-after.txt: nothing was written
  there, and its branch, index and status are unchanged.
