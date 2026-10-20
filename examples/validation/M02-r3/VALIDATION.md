# M02 r3: G02 r3 and r4 on the current head 90a5ec9 (Grok self-validation, not independent review)

Verdict: **PASS after one repair.**
- The first run on G02 r3 8fdae9c found a P2 regression. The repair was a fast-forward builder fix, G02 r4 90a5ec9.
  This recheck passes on it.
- Remaining: one P4 and observations.
- This is Grok checking a Grok build. It is not independent review and accepts nothing.

## What is being checked
- The last M02 (r2) validated bbe682b.
- Since then:
  - 8fdae9c "G02 r3 ... (root QA)": blank-looking and disguised UNRESOLVED answers; deep or corrupt journal and lock.
  - 90a5ec9 G02 r4: the repair below.
- Binding (raw/binding-verify.txt):
  - 90a5ec9 is the current remote head of review/grok-g02-activation.
  - The G02 r4 patch equals `git diff --binary 8fdae9c 90a5ec9`. The manifest matches.

## Probe written for this pass (oracle/m02r3_probe.py)
Inputs were chosen here, not copied from the G02 tests.
- **P01:** 10 blank-looking answers not in the r3 tests (Hangul jungseong filler, CGJ, Khmer inherent vowels, a
  variation selector alone, a tag space, and others).
- **P02:** 8 disguised spellings of UNRESOLVED (fullwidth, ZWSP inside, a combining mark on a letter, a filler prefix,
  a soft hyphen, math bold, circled, and one with a trailing note).
- **P03:** 5 controls that must stay recorded (accented, CJK, arrow, a mid-text "unresolved", a decomposed accent).
- **P04:** 7 deep, unclosed, huge-int or non-UTF-8 journal and lock shapes, through activate and resume.
- **P05:** lone surrogates through the API and a Latin-1 byte through the CLI.
- **P06:** a regression row against r2. 7 answers that start with UNRESOLVED and go on.

Results:

| Head | Probe score | Failing rows |
|---|---|---|
| G02 r4 90a5ec9 | 6/6 on 3.9.6, 3.11.16, 3.12.14, 3.13.15 | none |
| G02 r3 8fdae9c | 4/6 | P02, P06 |
| G02 r2 bbe682b | 2/6 | |

results/regress-r4-r3-r2.txt shows the per-answer table for the three heads.

## Finding on G02 r3, fixed in G02 r4
- **P2-1 (regression): answers that start with UNRESOLVED and go on were recorded as real deploy models.**
  - On 8fdae9c, these finished `complete` with the text recorded as the deploy model:
    - "UNRESOLVED ask the owner"
    - "Unresolved until the owner decides"
    - "unresolved pending call"
  - "U" plus a combining acute was also recorded.
  - At r2 bbe682b the three phrases were `partial` / UNRESOLVED.
  - Cause: r3's `_answer_token` deleted all spaces before matching `^unresolved\b`, so the word boundary was gone.
    NFKC also composed U plus the accent into Ú.
  - The M02 r2 oracle still scores 15/15 on 8fdae9c (results/m02r2-oracle-on-r3-8fdae9c-3.9.6.txt), so it did not
    catch this.
  - P2: the owner's unanswered question is silently treated as answered and onboarding reports complete.
  - Repair: G02 r4 90a5ec9 (see grok-output/G02-r4).
    - The fold now keeps spaces, uses NFKD and drops combining marks.
    - The new test fails 8 subtests on 8fdae9c.

## Builder and earlier checks on 90a5ec9
- **G02 activation_oracle:** 11/11 on all four Pythons. Controls: no-op 0/11 and partial 2/11, both rejected.
- **M02 r2 oracle:** 15/15 on all four Pythons. Its controls: echo 0/15 and no-op 0/15, both rejected.
- **Full suite on fresh clones:** 134 OK on all four Pythons. Browser processes 0 (results/full-suite-matrix.txt).

## Residuals
- **P4-1:** placeholder answers are taken as real deploy models.
  - "TBD", "?", "-" and "n/a" finish complete and are recorded as the deploy model.
  - This was not in the root finding. G02 documents only blank or UNRESOLVED as no answer.
  - Suggested: treat a short list of placeholders as no answer, or flag them in STATUS.md.
- **OBS-1:** a Cyrillic homoglyph spelling of UNRESOLVED ("UNR" plus Cyrillic E plus "SOLVED") is recorded as an
  answer. Confusable folding is out of scope for the finding.
- **OBS-2:** "Unresolved items: none; deploys via Vercel" is now treated as no answer, since it starts with the word.
  This fails closed: the owner is asked again. It was the same at r2.

Browser launches for this pass: 0.
