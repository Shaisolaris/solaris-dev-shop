# M09 validation of G09 (Kubernetes configuration before rollout)

**Grok self-validation, not independent review.** The same operator family built G09 and wrote this check. M09.md
names Muse as owner; this pass does not stand in for Muse's review.

## Binding
- Candidate: `edfa64d4d86532d18164e37175c7b0e4d734d0e0` (review/grok-g09-k8s-manifest-check), parent
  `ddebe98707219aa2638cd424777b1255413d9ceb` (G08 r2, validated by M08 r2 9ed30c3). main 02ba9c5 and G03 d4d98f2
  unchanged. Nothing in the chain is superseded.
- Handback patch sha256 8955a556...d3b4 equals the candidate diff; manifest 16/16 entries, 0 mismatches, manifest
  set equals diff set (raw/binding-verify.txt).
- Everything ran on rsync copies of a detached worktree at edfa64d. The candidate was never modified; the
  week-grok record and listing are identical before and after (raw/weekgrok-before.txt, raw/weekgrok-after.txt).

## Verdict: PASS with one P3 residual
Known broken configurations are detected with file, line, path and reason; the clean control is accepted; every
result says static files only, no cluster contacted, nothing applied or deployed. No cluster runtime exists on
this host either, so nothing here is evidence of rollout behaviour.

| id | severity | finding |
|---|---|---|
| P3-1 | P3 | An anchor on a block-sequence mapping item (`- &c name: web`, a common hand-written form) is refused (exit 2, fail-closed, nothing reported clean) but names the **next** line and the wrong reason ("multi-line plain scalar") instead of the anchor's own line and "anchors, aliases and tags are not read". The doc says such constructs are "refused with their line". Anchors on scalars, keys and mapping values report the right line. Oracle row R10b (core FAIL on all four versions). Fail-closed, so no fix patch is required; a fix would check the item's first token for `&`/`*`/`!` before treating the rest as a mapping. |

Recorded, not graded (doc-consistent or the builder's open questions):
- O31: a single-replica Deployment gets no PDB warning (doc: PDB_MISSING is for more than one replica).
- O33: a Service with no selector gets no finding (endpoints may be managed by hand).
- P04: a Service in a namespace with no workload in the files gets only SERVICE_SELECTOR_UNRESOLVED (warning), the
  builder's stated open question. With a local workload in that namespace a non-matching selector is an error.
- O30 identical liveness/readiness probes warn; O32 a 50% PDB of 2 replicas is clean.
- On Python 3.11-3.13 one builder test (PyYAML agreement) is skipped because PyYAML is only installed for 3.9.6.

## Oracle (oracle/m09_oracle.py, v3, 60 core rows plus OBS)
Written from M09.md and k8s-manifest-check.md only; my own YAML emitter records the line of every field path, so a
row passes only if the planted code is on the right object, path and line and no other error appears. Covers:
clean control; selectors (value typo, extra key, other namespace, cross-namespace with a local workload, omitted
namespace = default, cross-file, matchExpressions In/NotIn/Exists, missing workload selector); ports (named and
numeric targetPort, default targetPort, probe port names); readiness and probes (missing, zero handlers,
StatefulSet); PDBs that block eviction (minAvailable 3 of 3, 100%, maxUnavailable 0, 1 of 1), PDB selecting
nothing, PDB_MISSING; HPA; quantity arithmetic (0.5Gi vs 384Mi, 1025Mi vs 1Gi, 1001M vs 954Mi); images;
duplicates; unusable input exit 2; resources (missing, limits standing in, memory limit, LimitRange full and
partial, no false RESOURCES_DEFAULTED without a LimitRange); refused YAML (anchors in four positions, nested
tab, 3000-deep nesting) with exit 2, no traceback and the planted line; static-only claims; recovery (fix the
planted mistake, rerun clean); a 30-bundle property test; a 60-namespace scale case.

Disclosed oracle evolution: v1 (41 rows) teeth 27/43 showed doc rules it never exercised, so v2 added R01-R12;
v2 teeth 37/43 left res_limit_not_request, anchor_ok and tab_ok alive, so v3 added R07b, R10b and OBS O34.
Harness error fixed before scoring: R09b first used 1000M vs 954Mi, which is not an excess. v1 and v2 oracles
and all their results are kept (oracle/m09_oracle_v1.py, oracle/m09_oracle_v2.py, results/v1, results/v2).

## Matrix (results/pyversions-matrix.txt), same on 3.9.6, 3.11.16, 3.12.14, 3.13.15
- tests.test_g09_capability 15 OK; full suite 159 OK.
- Builder oracle ACCEPTED 17/17; naive REJECTED 3/17; noop REJECTED 2/17.
- M09 oracle 59/60 (R10b, P3-1); naive control 0/60; noop control 10/60.
- No __pycache__ left in the copy; candidate status clean.

## Mutation tests (builder's 43 G09 mutants copied unchanged, scripts/builder_mutants_g09.py)
Kill = any core result or OBS detail change against the unmutated baseline.
- 3.13.15: 39/43. 3.9.6: 39/43 (same four survivors).
- Survivors: anchor_ok, bool_yes_string, block_clip_off (YAML reader internals; the builder's own tests kill all
  three, results/v2/survivors-builder-tests-3.13.15.txt), and seq_item_line_shift_EQUIV (labelled equivalent by
  the builder; its tests do not kill it either). anchor_ok's guard is redundant with a later check for every
  anchor position the oracle tries; bool_yes_string and block_clip_off change values no check reads.

## Fresh caller (results/fresh-caller.txt)
README demo verbatim under env -i with a new HOME on 3.9.6 and 3.13.15: clean exit 0; broken exit 1 with the five
documented lines 32, 38, 55, 66, 83 in text and JSON; README.md refused exit 2 with its line; builder oracle
ACCEPTED 17/17; noop REJECTED 2/17. Tree byte-identical after, no __pycache__. The only HOME entry is Apple
Python 3.9's own Library/Caches/com.apple.python (interpreter, not the tool).

## Not done
No cluster, kubectl, kind or minikube run (none present); no M2, promotion, PR or merge.
