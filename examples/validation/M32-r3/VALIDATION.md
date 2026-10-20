# M32 r3 validation of G32 r3 (durable suppression, format-character handles) (Grok self-validation, not independent review)

Validator: Grok, the same agent family that built G32. This is self-validation, not independent review.

- Candidate: G32 r3 `b69f3289f360ed0dc5d722f025940815787ff1af` on review/grok-g32-consent-followthrough, one
  commit on G32 r2 2d85d94. It answers the root finding: suppression was lost after a CRM identity or history
  merge (M32 r2 P3-2), and invisible format characters created a new identity (M32 r2 P3-1).

## Verdict
PASS with two P3 findings and one P4. No P1 or P2, so no repair. M32 r2 P3-1 and P3-2 are closed. M32 r2 P4-1 is
closed (the doc now names aliases and look-alikes as not matched). Nothing is sent in any run.

## Method
- Probe `oracle/m32r3_probe.py` was written from the r3 doc before reading the r3 tests. Each case uses its own
  temp state folder, runs `run --json`, and checks exit codes, drafted actions, notes and state bytes. 15 scored
  cases, plus OBS rows that record behaviour.
- The prior M32 and M32 r2 oracles were rerun on r2 and r3.
- The builder's followthrough_oracle and its naive and no-op controls ran on four Pythons. The full suite ran on
  fresh clones on four Pythons.

## Results
- **Probe:** 15/15 on r3 on 3.9.6, 3.11.16, 3.12.14 and 3.13.15. 2/15 on r2.
- **Prior oracles:** M32 14/14 core and M32 r2 18/18 core on r2 and r3.
- **Builder oracle:** 11/11 on four Pythons. naive and no-op each 1/11.
- **Full suite:** 167 OK on four Pythons at b69f328. Browser 0.
- **Binding:** remote head equals b69f328; handback patch equals a regenerated diff; manifest matches
  (raw/binding-verify.txt).

## What the root fix does (all pass on r3, fail on r2)
- Q01, Q02: after an opt-out, a merge that re-imports the person under a new record id and drops the old history
  gives no drafts, also with a case, width or spacing variant of the handle.
- Q03: a duplicate import that differs only by a zero-width space, zero-width joiner, soft hyphen, BOM, LRM or word
  joiner is refused (exit 2). Q04: the ZWSP variant after a history-dropping merge stays suppressed.
- Q05: a durable marketing opt-out still allows the support ack. Q06: a durable hard bounce suppresses.
- Q07: an opt_in after the merge is flagged consent_review_required and changes nothing.
- Q08: a refused run leaves the state byte-identical. Q09: reruns do not duplicate rows. Q10: a state folder from
  before r3 (no suppression file) works.

## Findings
- **P3-1: invisible characters outside category Cf still mint a new identity.** Q13: after an opt-out and a merge
  that drops history, a handle carrying U+034F (combining grapheme joiner), U+FE0F (variation selector), U+3164
  (Hangul filler) or U+2800 (braille blank) gets a live `welcome` draft. A duplicate import with them is accepted.
  The doc only promises format characters, so this is a doc gap, not a broken promise. Suggested fix: strip
  Unicode Default_Ignorable_Code_Point characters (or refuse handles that contain them), or say in the doc that
  only category Cf is ignored.
- **P3-2: a damaged suppression file is ignored silently.** Q11: if person_suppressions.jsonl has an unreadable
  line and the history no longer carries the opt-out, the person gets a `welcome` draft with exit 0 and no note.
  Q12: a garbage line is skipped with no note. The doc refuses a journal that does not verify, so the
  consent-critical file is held to a lower bar. Drafts are never sent, so a person still reviews them. Suggested
  fix: refuse (exit 2) or at least report unreadable suppression rows.
- **P4-1: the doc says a CRM identity merge keeps the suppression, but suppression is keyed by handle.** Q14: a
  merge that both changes the handle and drops the history gives a `welcome` draft. No tool could link these
  without the history. The doc should say the suppression follows the handle.

## Files
- oracle/m32r3_probe.py
- results/: probe per Python, probe on r2, prior oracles per revision, builder oracle, suite matrix
- raw/binding-verify.txt
