# M02 r4 validation of G02 r6 038f934

- Verdict: PASS after one repair (G02 r5 642362a had one P4 found by this pass; G02 r6 038f934 fixes it).
- M02 r3 P4-1 (placeholder answers recorded as the deploy model) and OBS-1 (look-alike UNRESOLVED read as an answer) are closed.
- This is Grok checking a Grok build. Grok self-validation, not independent review. It accepts nothing.

## What is being checked
- M02 r3 validated G02 r4 90a5ec9 and left P4-1 and OBS-1.
- Since then on review/grok-g02-activation (raw/binding-verify.txt):
  - 642362a G02 r5: whole-answer placeholders (TBD, ?, -, n/a and similar, or punctuation alone) and UNRESOLVED with Cyrillic or Greek look-alike letters are no answer.
  - 038f934 G02 r6: the repair below.

## Probe (oracle/m02r4_probe.py)
Written for this pass from P4-1 and OBS-1. Inputs chosen here, not copied from the G02 r5 test.
- R01: 21 placeholder spellings not in the G02 r5 test stay UNRESOLVED (partial, STATUS line).
- R02: 9 look-alike spellings of UNRESOLVED stay UNRESOLVED.
- R03: 10 real answers that mention a placeholder word (`AWS Amplify (region TBD)`, `Pending: Cloudflare Pages`, `TBD Corp private cloud`) are recorded unchanged.
- R04, R05: controls (no answer stays UNRESOLVED; `Vercel` is complete).

## Findings on G02 r5 642362a
- **P4 (fixed in r6):** `t.b.d.` and `T. B. A.` finished complete and were recorded as the deploy model, and `UNRESOLVE` plus Cherokee letter DA was read as an answer (results/probe-r5-642362a.txt).
- Harness error, disclosed: the first probe version (oracle/v1, results/probe-v1-r5-642362a.txt) used Cyrillic EN (looks like H), Cyrillic PE (looks like n), Cyrillic U (looks like Y) and Greek omicron in place of u. Those are not look-alikes of the letters they replaced, so their rows were not defects. v2 swaps them for real look-alikes.

## Results on G02 r6 038f934
- m02r4 probe 5/5 on 3.9.6, 3.11.16, 3.12.14 and 3.13.15 (results/probe-r6-four-python.txt).
- Existing reproducer, the M02 r3 probe: 6/6 on all four Pythons; its X01 observation row now shows the Cyrillic E, TBD, ?, - and n/a answers as partial with no deploy model (results/m02r3-reproducer-r6-four-python.txt).
- Full suite on fresh clones: 135 OK on all four Pythons (results/full-suite-matrix.txt). Browser processes 0.

## Residuals
- **OBS-1:** the look-alike fold is a short list (Cyrillic, Greek, Armenian, Cherokee, small capitals). Other scripts can still spell UNRESOLVED. A miss records text as the answer, which the owner sees in STATUS.md.
- **OBS-2:** the placeholder list is English only (`TBD`, `n/a`, `pending`, `unknown` and similar).
- **OBS-3 (from M02 r3, unchanged):** `Unresolved items: none; deploys via Vercel` is no answer, since it starts with the word. This fails closed.

Browser launches for this pass: 0.
