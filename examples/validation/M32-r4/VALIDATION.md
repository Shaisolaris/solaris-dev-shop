# M32 r4: affected recheck of G32 r4 3346efa (Grok self-validation, not independent review)

Validator: Grok, the same agent family that built G32. This is self-validation, not independent review.

- Candidate: G32 r4 `3346efac313f8508bb04c575277dca99dc6d2634` on review/grok-g32-consent-followthrough, a
  fast-forward of r3 `b69f328` (M32 r3: PASS with P3-1, P3-2 and one P4).

## Verdict
**PASS.** M32 r3 P3-1 and P3-2 are closed. No P1, P2 or P3. M32 r3 P4 (suppression keyed by handle) stands.

## Method
- Re-ran the unchanged M32 r3 probe (oracle/m32r3_probe.py) on r3 and on r4 (results/probe-*.txt). Probe 15/15 on both.
- Compared the OBS rows that recorded the two P3s.
- Checked G32's invisible-character list against the Unicode 15.1 data file.
- Ran four mutants that each undo one part of the fix.
- Four-Python tool and oracle matrix, full suite on fresh clones, binding check.

## Results
- **P3-1 closed.** On r3, a merge to a handle carrying U+034F, U+FE0F, U+3164 or U+2800 got a `welcome` draft, and
  a duplicate import with them was accepted (rc 0). On r4 the same rows give no draft, and the duplicate is
  refused (rc 2). The list in followthrough.py equals the 17 Default_Ignorable_Code_Point ranges of Unicode 15.1
  exactly, plus U+2800 (results/default-ignorable-ranges.txt). Cyrillic look-alikes are still not matched, as
  the doc says.
- **P3-2 closed.**
  - Q11: on r3, a corrupted suppression line plus dropped history gave a `welcome` draft (rc 0).
  - Q12: on r3, a garbage line was skipped silently (rc 0).
  - On r4 both refuse with exit 2: "person_suppressions.jsonl line N is not readable JSON; repair the file
    before running. Nothing was written."
- **Teeth (results/teeth.txt):** each mutant fails tests.test_g32_capability:
  - M1: no Default_Ignorable stripping;
  - M2: skip an unreadable JSON line;
  - M3: skip a malformed row;
  - M4: truncate a torn tail.
- **Four Pythons (3.9.6, 3.11.16, 3.12.14, 3.13.15):** G32 tests OK; oracle ACCEPTED 11/11; naive and no-op
  REJECTED 1/11, the same as r3. The full suite has 168 tests OK on all four. Browser launches: 0.
- **Binding (raw/binding-verify.txt):** the remote head equals 3346efa, the patch equals a regenerated diff of
  b69f328..3346efa, and the manifest matches.

## Observations
- OBS: a damaged suppression file now stops all drafting for that account until a person repairs it. This is
  the safe direction (nothing is sent in any case), and the doc says so.
- OBS: the G32 r4 handback discloses that a first push attempt was refused by the safety scan (email-shaped
  handles in the new test). The handles were rewritten before any push. The public history holds only the
  clean commit.

## Files
- oracle/m32r3_probe.py (unchanged from M32 r3)
- results/: probes on r3 and r4, teeth, Unicode range check, four-Python table, suite matrix, new test on r3
- raw/binding-verify.txt
