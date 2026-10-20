# M15 r4: G15 r4 7e7f361 (Grok self-validation, not independent review)

Verdict: **PASS with one P3.**
- The root finding is fixed: an interleaved burst can no longer produce a causal claim.
  - With a declared `randomization` contract, every burst I injected made the experiment invalid.
  - Without a contract, a significant randomized result is `association_only`, never causal.
- No P1 or P2. One P3 (a documentation limit) and observations.
- This is Grok checking a Grok build. It is not independent review and accepts nothing.

## What is being checked
- M15 r3 validated 64c3cc7.
- 7e7f361 (G15 r4, root QA) adds rule 7:
  - A causal claim needs a per-unit sha256_bucket assignment contract that the tool recomputes for every cohort unit.
  - Without a contract, a significant randomized result is association_only.
  - The fixture is regenerated to follow the contract.
- Binding (raw/binding-verify.txt):
  - 7e7f361 is the current remote head of review/grok-g15-experiment-readout.
  - The G15-r4.patch equals `git diff --binary 64c3cc7 7e7f361`.
  - The handback's MANIFEST covers the handback folder itself (it is not a repo-file manifest). It checks clean
    there.

## Probe written for this pass (oracle/m15r4_probe.py)
- **Setup:** my own packages, 31 days at 60 units a day, about 1,860 units. Arms come from my own implementation of the
  documented rule. No true effect unless stated. 20 seeds per scenario.

| Row | Scenario | Result on r4 |
|---|---|---|
| B1 (root) | 40 all-treatment, 90%-converting units interleaved into one day, with contract | invalid_experiment in 20/20; no causal claim |
| B2 | the same burst without contract | never causal |
| B2b (OBS) | a 50-unit burst without contract | 5 of 20 runs were association_only; the rule 5 guards missed the burst there, and rule 7 stopped it becoming causal |
| B3 (OBS) | a 6-unit burst with contract (expected escape 1/64 per run) | invalid in 19/20; 1 no difference |
| B4 | A/A with contract | verified 20/20; 1 causal false positive (alpha 0.05) |
| B5 | a true effect from 20% to 30% | difference_detected and causal in 20/20 |
| B6 | a 30/70 split with a true effect | verified and detected |
| B7 | wrong salt declared | invalid, about half the units mismatched |
| B8 | malformed contracts, or a contract on an observational package | exit 2 |
| B9 | non-ASCII unit ids | verified (the UTF-8 rule matches) |

- **Scores:** 8/8 scored rows on 3.9.6, 3.11.16, 3.12.14 and 3.13.15. On r3 64c3cc7 the score is 1/8: r3 refuses the
  `randomization` field and has no causal guard.

## Earlier oracles (oracle/r3/, unchanged M15 r3 battery, m15r3_all.py)
- **Score:** 23/29 core on r4, against 28/29 on r3.
- **What the 6 new failures are:** every one is a case where a randomized package without a contract now gets
  association_only where the r3-era oracle expected difference_detected. That is 7 cases across X02, X06, D06, S01,
  S02 and S07.
- **Why they are expected:** the old oracle builds randomized packages with no contract, and rule 7 deliberately stops
  calling those causal. This is the intended change, not a regression.
- **The remaining D06 case** (invalid_experiment against no_detectable_difference) already failed on r3. It is the one
  M15 r3 adjudicated.

## Builder checks
- **readout_oracle:** ACCEPTED 18/18 on all four Pythons. The naive stub scores 2/18 and the no-op 1/18, both rejected
  (results/builder-oracle.txt).
- **Full suite on fresh clones:** 142 OK on all four Pythons. Browser 0.

## Finding
- **P3-1: the contract checks the arms of the units that are present, not the units that are missing, and the doc does
  not say so.**
  - B10 (OBS): with no true effect, I removed 25% of converting control units from the assignment log (about 46 units,
    about 5% of control).
  - The contract still verified, SRM did not fire, and the readout gave difference_detected with a causal claim in 9
    of 20 seeds.
  - The message reads "randomized assignment verified for all N cohort units".
  - This is not new in r4: r1 to r3 made the same causal claim on such data without any contract. It is not the
    burst class in the root finding.
  - But rule 7's wording ("the data did not come from the declared randomization" is the only failure it names)
    invites reading "verified" as complete.
  - Suggested: say in rule 7 and in the trace that the contract cannot detect units missing from the log, and that
    differential loss is guarded only by SRM, with its limited power.
  - Better, if the assignment system can supply it: a per-day expected count, or a roster hash.

## Observations
- B2b shows the rule 5 allocation guards still miss some large interleaved bursts. Rule 7 is what keeps those from
  becoming causal. Packages without a contract never get causal claims now. That is conservative, and existing users
  must add a contract to get causal output.

Browser launches for this pass: 0.
