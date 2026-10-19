# M25 r2: Grok self-validation of G25 r2 (device event protocol)

Label: Grok self-validation by the same bot that built and validates the programme. This is not independent review and not manager acceptance.

- Candidate: G25 r2 at a902bc43af1fcd977b0811c1ce6c205836ffdd23 (parent 822db7d), fetched 20:58:25 PT, checked out detached in a /tmp worktree. Not modified.
- Binding: candidate manifest OK 17/17; G25-r2 patch identical to `git diff` of the commit (6 files, +246/-29) (raw/binding-verify.txt).
- Scope: the r1 residuals S1 to S4, the two r1 surviving mutants (window_le, acked_only_claimed), and regressions.
- week-grok: before 20:58:24 PT and after 21:13:58 PT are identical (branch programme/grok-week-20261018, HEAD 02ba9c5, index c28a2f586b3e3001, status af8386300eb96552, 80 lines; full listing also byte-identical). Nothing was written in its working tree.

## Verdict: PASS with residuals

S1 to S4 are fixed, both former survivors are now killed, and there is no regression. No P1 or P2, so no proposed-fix patch.

## Results (identical on 3.9.6, 3.11.16, 3.12.14, 3.13.15)
| Instrument | Result |
|---|---|
| M25 oracle v2, core | 23/23 |
| M25 oracle v2, adversarial (findings only) | 17/17 |
| M25 oracle v1 (kept unchanged) | 23/23, adversarial 14/17; see adjudication |
| M25 r2 probes (graded) | 15/21; fails R01, R02, R06, R09, R10, D04 |
| Builder suite | 108 OK (84 base + 24 G25) |
| Builder protocol_oracle.py | candidate 12/12, noop 0/12, naive 1/12 |
| Fresh caller (env -i, new HOME, offline guard, doc commands only), 3.9.6 and 3.13.15 | exits 0, 1, 3, 1 as documented; resume equals the unbroken run (8e5d7b198fc7f7f2); network blocked |

Oracle adjudication (disclosed): v1 A06, A06b and A14 expected exit 2 for a damaged checkpoint; the r2 doc specifies exit 4. v2 accepts 2 or 4 and uses .get on A06b (v1 crashed with a KeyError there). v1 is kept as oracle/m25_oracle_v1.py. Probe v1 counted `resumed_from_line` in the R00 comparison, but it differs by design, so v2 excludes it; the v1 run is in raw/discarded-harness-error/.

## Residual fixes confirmed
- S1: an edited body without a recomputed hash exits 4 and nothing is written (R11); empty and truncated checkpoints exit 4 (R07, R08).
- S2: `--record` creates its folder; an existing file or symlink there exits 2 (D01, D02, D03, D05); fresh caller agrees.
- S3: buffer window next+1 to next+32: seq next+32 is buffered with no gap (W32), next+33 is a gap (W33).
- S4: whole-string id patterns for devices and commands (I01, I02); A15 and A16 hold.
- Former survivors: window_le is killed by the builder tests, builder oracle and Grok (K09, W33); acked_only_claimed is killed by the builder tests.

## Findings by severity
- P3, S1 residual: `lines` sits outside body_sha256 and is only type-checked. Editing it (+1000, or 0) is accepted with exit 1 (R01, R02): the report's inputs.event_lines becomes 1392 instead of 392, anomaly line numbers shift by 1000, and resumed_from_line is falsified (1250 or 0 instead of 250). The doc promises exit 4 for an edited checkpoint. Edits to `offset` or `events_prefix_sha256` are refused with exit 2 (R03, R04). An edited `tool_version` is accepted and gives the same report (R05, recorded).
- P4: a checkpoint that is valid JSON but not an object ("[]", "null", "\"text\"") exits 2 "belongs to another command log or tool", not 4 "damaged" (R06, R09, R10). It is still refused and nothing is written.
- P4: `--record afile/sub` where `afile` is a file gives a NotADirectoryError traceback and exit 1 (D04), not the documented exit 2.
- P4, test gap: 3 non-equivalent mutants survive every instrument, including the builder tests: r2_applied_ge_off, r2_counts_check_off, r2_ack_owner_off. Each guard in check_snapshot is reached only by a forged checkpoint with a recomputed hash. Distinguishing inputs (results/distinguish-3.9.6.txt): applied=0 below the claim count, a string count, and an ack of another device's command are each refused with exit 4 by the candidate but accepted with exit 1 by the matching mutant.
- Owner decision: a command that was rejected and then reported done claims nothing; the doc does not say which wins (L03).
- LIMIT, documented: a forged checkpoint with a recomputed hash is accepted (claims 24 instead of 55, L01; duplicates +777, L02). The doc states the hash is not a signature.

## Teeth (results/teeth-tally-3.9.6.txt)
35 mutants (r1 set with window_le and window_unbounded re-pointed, plus 14 r2 mutants), 4 shards on 3.9.6, 0 errors. A kill is any deviation from the candidate baseline on that instrument.
- Builder tests kill 29; builder oracle 22; Grok core and probes 23; union 30/35.
- Survivors: 2 expected-equivalent controls (claimed_only_EQUIV, isfinite_off_EQUIV) and the 3 non-equivalent ones above. Union on non-equivalent mutants is 30/33.

## Not done
- Teeth ran on 3.9.6 only (time budget); the other instruments ran on all 4 interpreters.
- 3.10 is not installed.
