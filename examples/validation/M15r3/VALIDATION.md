# M15 r3 validation of G15 r3 (experiment readout: sliding-window allocation scan)

**Grok self-validation, not independent review.** The same operator family built G15 and wrote this check. The r3
fix is builder code (the handback says no validator patch was used this round); the r2 drift fix being regressed
here came from my own M15 patch, as disclosed in M15 r2.

## Binding
- Candidate: `64c3cc706c753b1c3676b1ef6a433c4706b3e62f` (review/grok-g15-experiment-readout), fast-forward from G15
  r2 `6c51c3c07558d766d49ad25bd0953285c4568455` (validated by M15 r2 3a368d2), on r1 78daf30 and G13 r3 5666e7b;
  main 02ba9c5 unchanged. Nothing in the chain is superseded.
- Handback patch sha256 78329953...7bc5 equals `git diff --binary 6c51c3c 64c3cc7`; manifest 7/7, 0 mismatches,
  manifest set equals diff set (raw/binding-verify.txt).
- All runs on rsync copies of a detached worktree; candidate never modified; week-grok record and listing
  identical before and after (raw/weekgrok-before.txt, raw/weekgrok-after.txt).

## Verdict: PASS with one P3 residual
The r2 residuals are fixed: the r2 P3-1 shape (a one-day all-variant burst inside healthy weeks) is now
invalid_experiment with no causal claim (S05), and the scan is independent of cohort.start (S03, r2 P4-1).
My own implementation of the doc's scan reproduces the tool's windows_tested and worst-window p-value exactly in
every scored case, including a 30/70 plan and tied timestamps.

| id | severity | finding |
|---|---|---|
| P3-1 | P3 | Bursts spread through a day's normal traffic escape at sizes the doc implies are caught, and then the readout allows a causal claim. With 60 units a day, zero true effect and an all-variant high-converting burst added across one day (O09, 20 runs each): 30 units caught 2/20 with 8/20 causal claims; **40 units caught 4/20 with 9/20 causal claims**; 60 units caught 17/20 with 3/20 causal claims. The doc says "about 30 units or fewer can pass, depending on how much normal traffic is interleaved", which reads as a limit near 30; interleaved, the practical limit is nearer 60. Bursts that replace the day's traffic behave as documented (20: 0/20, 30: 16/20, 40 and 60: 20/20). The doc does call the scan a guard, not proof, so this is a documented gap that is understated, not a broken contract; no fix patch is required. Options: state the interleaved miss rate in the doc, or the time-window scan from the builder's open question 1. |

Recorded, not graded:
- False invalidation (O08, S08): 0 of 300 healthy null runs invalidated (150 at 50/50, 150 at 30/70, 60 units a day
  for 28 days, true lift 0.03), consistent with the documented 0.5% union bound and the builder's 0.05-0.23%. With
  0/300 the 95% upper bound is about 1%, so this sample cannot by itself prove the 0.5% figure.
- Single-run S01 outcomes around the limit vary by seed (a 25-unit replacing burst caught, a 30-unit one not); the
  O09 rates above are the better reading.
- A 10-unit replacing burst gave difference_detected with zero true effect in one seed; at 20 units 2/20 runs did.
  That is near the 5% false-positive rate of the effect test itself, not a scan property.
- Regression: r2 drift oracle 5/6 on r3. The one difference (D06 case 9, a 49-day spike) is invalid on r3 because the
  new scan catches it; probes/d06_under_r3_rule.py regenerates that case and my scan rule calls it a mismatch
  (min p 1.493e-09), so this is the documented r3 rule, not a regression.

## Oracles
- oracle/m15r3_scan.py (new, 9 core rows plus 2 OBS): written from the r3 doc text; my own exact binomial (minlike)
  and window schedule. S01 replacing bursts of 10-60 units; S01b 40 and 60 caught; S02 interleaved and midnight
  bursts of 20-60; S03 alignment (start moved 0 to 6 days 13 h: one distinct scan result); S04 clean 50/50 and 30/70
  controls and a 30/70 reverse burst; S05 the r2 residual shape; S06 40 tied timestamps; S07 40 random shapes;
  S08 false-invalidation bound; O08 null runs; O09 power curve. Authoring fix before scoring (disclosed): S05 first
  tested the claims dict for emptiness instead of claims.causal.
- Regression: oracle/m15_oracle.py (M15 v3) and oracle/m15r2_drift.py, unchanged copies from M15 r2.
- oracle/m15r3_all.py combines the three for teeth (slow OBS rows skipped).

## Matrix (results/pyversions-matrix.txt), same on 3.9.6, 3.11.16, 3.12.14, 3.13.15
- tests.test_g15_capability 15 OK; full suite 139 OK.
- Builder oracle ACCEPTED 16/16 (seed 1515); naive REJECTED 2/16; noop REJECTED 1/16.
- M15 v3 oracle 15/15 (naive 2/15, noop 2/15); r2 drift oracle 5/6 (D06 explained above); r3 scan oracle 9/9 (naive
  0/8 and noop 0/8 on the fast rows, checked on 3.9.6 during authoring).
- No __pycache__ left in the copy; candidate status clean.

## Mutation tests (builder's 50 G15 r3 mutants copied unchanged, scripts/builder_mutants_g15r3.py)
Kill = any core result or OBS detail change against the unmutated baseline.
- 3.13.15: 50/50. 3.9.6: 49/50; survivor bytecode_written, the same Apple 3.9 pycache_prefix equivalence as r2 and
  as the builder's own 3.9 run.

## Fresh caller (results/fresh-3.9.6.txt, results/fresh-3.13.15.txt)
README fixtures under env -i with a new HOME and a python3 shim: clean-aa no_detectable_difference, retention-lift
difference_detected, sample-ratio-mismatch invalid_experiment, README.md refused exit 2, --out written; no new
files, no __pycache__. Identical to the r2 fresh caller.

## Not done
No real experiment data (all synthetic); no M2, promotion, PR or merge.
