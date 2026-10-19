# M11 r2: Grok self-validation of G11 r2 (incident SLO, per-source telemetry)

This is Grok self-validation, not independent review. The same agent family built and validated it.

- Candidate: G11 r2 `62fd4b88ba48a0f82576db4d4af5a2cf325f46c0` on `review/grok-g11-incident-slo`, a fast-forward
  from r1 `36c1ed1686f013e382eddffa40151073ec0d8d28` (scored by M11 `10b5f8b`: PASS with P3-1, P4-1, P4-2).
- Prerequisites unchanged: G03 r3 `d4d98f2`, G10 r6 `f79be61`, main `02ba9c5`. Nothing superseded. Patch sha256 equals
  `git diff --binary 36c1ed1 62fd4b8`; manifest 13/13, 0 mismatches (`raw/binding-verify.txt`).
- The candidate was never modified; every run used an rsync copy in a private temp dir. week-grok before/after
  records are identical. Pass window 03:14 to about 03:37 PT, 2026-10-19.
- The fix is the builder's own design, not from a Grok patch (M11 r1 supplied no patch: P3 only).

## Verdict: PASS with residuals. P3-1 and P4-1 (M11 r1) are fixed; P4-2 is now documented.

| Instrument | 3.9.6 | 3.11.16 | 3.12.14 | 3.13.15 |
|---|---|---|---|---|
| G11 tests / full suite | 10 OK / 191 OK | same | same | same |
| builder oracle (seed 1811) real / naive / noop | 13/13 / 2/13 / 0/13 | same | same | same |
| M11 oracle (r2-contract edition) real / naive / noop | 22/22 / 3/22 / 3/22 | same | same | same |
| new per-source oracle `m11r2_sources.py` real / naive | 8/8 / 1/8 | same | same | same |

- Fresh caller (env -i, new HOME, README commands only) on 3.9.6 and 3.13.15: identical, fixture decisions as
  documented, bad input exits 2, `--out` written, no stray files or bytecode.
- Teeth (36 builder mutants, unchanged, scored by `m11r2_all.py` = M11 oracle + per-source oracle):
  3.13.15 35/36; 3.9.6 34/36. Survivors: `multi_source_stat_off` on both (non-equivalent: the builder's
  `tests.test_g11_capability` fails on the mutated copy; my oracles do not read the undocumented
  `import.telemetry_minutes_multi_source` stat, see P4-1) and `bytecode_written` on 3.9.6 only (equivalent
  under Apple 3.9.6's pycache_prefix).

## Regression: the r1 contract changed, two M11 rows re-expressed (disclosed)

The first matrix run used the M11 oracle unchanged and scored 20/22: E07 (re-delivery under a `replay` source must
equal a single import) and E09 (a second collector's different count is a conflict) encoded the r1 rule. The r2 doc
reverses both on purpose ("Do not give a re-delivery or a mirror of the same traffic a different source name: it would
be added"; "Different counts from different sources are not a conflict"). That reversal is the P3-1 fix. I re-expressed
E07 (re-delivery under the same source) and E09 (conflict from the same source) and kept the r1 forms as OBS rows
E07o and E09o, which now show the summed totals. Everything else is unchanged. The first run and its teeth are kept
in `results/r1-contract/` (not evidence for the verdict); the original oracle is `oracle/m11_oracle_r1contract.py`.

## New per-source adversarial cases (expectations from incident-slo.md, Fractions, half-even six decimals)

- S01 three load balancers, errors on one only: summed values exact, three impact minutes. PASS.
- S02 four sources with equal counts: all four count. S03 a source re-delivers its own minutes: counted once. PASS.
- S04 one source reports two counts: the whole minute (both sources) is left out and labelled. PASS.
- S05 unnamed records are one source and are summed with a named one; two unnamed counts conflict. PASS.
- S06 an r1-style bundle without sources keeps r1 semantics. PASS.
- S07 property test, 40 random bundles (1 to 4 sources, unnamed mixed in, gaps, repeats, conflicts, shuffled). PASS.
- S08 traffic split across two sources gives the same SLO, impact and decision as the combined single source. PASS.
- M11 r1 probe `probes/p_per_source.py` (r1 P3-1 / P4-1): reproduced through S01/S02/S08; r1 `met` 1.000000 is now
  the exact summed value.
- Harness error (disclosed): v1 of S01 also asserted `breached`; my arithmetic was wrong (120 bad of 54000 is met at
  0.99). Fixed before scoring; v1 kept as `oracle/m11r2_sources_v1.py` and `results/kept/sources-v1-3.9.6.json`.

## Findings

- P3-1 (M11 r1, conflict rule hides error minutes): fixed (S01, S04, S08).
- P4-1 (M11 r1, equal per-source counts merged): fixed (S02).
- P4-2 (M11 r1, burn window from the change's minute): now stated under Limits. Closed as documented.
- P3-1 (new) Source dropout is silent. O09: two load balancers, one silent for 30 of 60 minutes. Every minute
  counts as measured, coverage 1.000000, total 45000, and there is no label. Errors on the silent balancer cannot be
  seen, and nothing tells the reader that half the traffic is missing. The doc's "nothing silently dropped" and
  coverage rules work per minute, not per source. A suggested direction (no patch, since this is P3): list the
  sources seen across the window, and label any minute that is missing a source seen elsewhere.
- P4-1 (new) `import.telemetry_minutes_multi_source` is emitted but not documented.
- P4-2 (new) Source names are compared as exact strings. `lb-0` and `LB-0 ` are two sources and are added (O10).
  This is consistent with the doc, but a trimming or case slip doubles the traffic.
- OBS: an empty-string source (O11) and a non-string source (O12) are refused with exit 2 (fail closed). A mirror
  under a new name is added (O13), as documented.

## Layout

`oracle/` (M11 oracle r2-contract edition and the r1 original, per-source oracle and v1, combined), `probes/`
(r1 probe), `scripts/` (matrix, teeth, fresh caller, builder mutants copy), `results/`, `raw/`.

## Publish redaction (disclosed)

In the published copy only, two naive-stub stderr tails on 3.12.14 (`results/oracle-naive-3.12.14.json` and
`results/r1-contract/oracle-naive-3.12.14.json`) had a local interpreter install path. Its prefix is replaced with
`[local-path]`; the rest of the traceback is unchanged. The local evidence keeps the original. Same handling as M11 r1.
