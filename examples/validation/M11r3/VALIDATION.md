# M11 r3 validation of G11 r3 (incident SLO: expected telemetry sources, silent-source minutes)

**Grok self-validation, not independent review.** The same operator family built G11 and wrote this check. The r3
change is builder design (the handback says no validator patch was used).

## Binding
- Candidate: `13ba7055537e305732856aea3c74ff28f0848be8` (review/grok-g11-incident-slo), fast-forward from G11 r2
  `62fd4b88ba48a0f82576db4d4af5a2cf325f46c0` (validated by M11 r2 bc1d0f6); G03 d4d98f2 and G10 f79be61 are
  ancestors and unchanged on the remote; main 02ba9c5 unchanged. Nothing in the chain is superseded.
- Handback patch sha256 784882b2...f5ef equals `git diff --binary 62fd4b8 13ba705`; manifest 13/13, 0 mismatches,
  manifest set equals diff set (raw/binding-verify.txt).
- All runs on rsync copies of a detached worktree; candidate never modified; week-grok record and listing
  identical before and after (raw/weekgrok-before.txt, raw/weekgrok-after.txt).

## Verdict: PASS, no residual above OBS
M11 r2 P3-1 (silent source not detected) is fixed: a source retired, added or replaced inside the window makes the
minutes without it partial; they are left out, listed and named per source, and the SLO is not reported met
(T02-T04, T13). A breach in the complete minutes is still reported (T07). M11 r2 P4-1 is fixed (the doc now names
telemetry_minutes_multi_source) and P4-2 is fixed (names trimmed, collapsed and case folded, T09; two spellings, a
declared duplicate and an unnamed record beside a declared list are refused with exit 2, T10-T12).

Recorded, not graded (all documented, and the builder's open questions):
- A source retired or added inside the window looks silent outside its lifetime under the inferred basis
  (T02, T03; doc: "the label stands until someone confirms it"). Recovery works: splitting the window at the
  change and declaring each part's sources gives two clean met reports (T05a, T05b). Declaring a list without
  a source that still reports is refused rather than silently dropping it (T06).
- One partial minute blocks met (doc); errors seen only while a source is silent are not impact minutes (T08),
  and a rollback decision with a source silent after the change is insufficient_evidence (T15a; with every
  source reporting, do_not_rollback, T15b).
- O17: the reader sees one label per silent source with its count and coverage, the per-source silent and partial
  ranges, and the import counts.

## Oracles
- oracle/m11r3_sources.py (new, v2, 19 core rows plus OBS): written from the r3 doc text; my own expected-source,
  normalization, partial-minute and status rules in Fractions. T01 clean control; T02 retired; T03 added; T04
  replaced; T05 recovery by split and declare; T06 declared list missing a reporter; T07 breach still reported; T08
  errors only in partial minutes; T09 normalization; T10-T12 refusals; T13 declared but never reporting; T14 one
  unnamed source; T15 decision rule 3; T16 40 random lifetimes and outages; T18 a missing range beside a retired
  source. Disclosed: an authoring fix before scoring (T14 compared the tool's display name "(unnamed)" with my
  None); v1 crashed on the noop control (an extra check read a missing key, now caught and failed), and v1 teeth
  on 3.13.15 were 48/49 with alone_is_all_silent alive, so v2 added T18. v1 and its results are kept
  (oracle/m11r3_sources_v1.py, results/v1).
- Regression, r3-contract editions (disclosed): oracle/m11_oracle.py generated telemetry under a rotating source
  label (one reporter per minute), which the r3 rule reads as silent reporters (10/22 on r3 unchanged); it now
  uses one label, the same change the builder made to its fixtures and generator. oracle/m11r2_sources.py S07
  dropped one source of a minute at random, which r3 reads as partial; the gap now drops the whole minute.
  Nothing else changed; the r2 editions are kept as *_r2contract.py.
- oracle/m11r3_all.py combines the three for teeth.

## Matrix (results/pyversions-matrix.txt), same on 3.9.6, 3.11.16, 3.12.14, 3.13.15
- tests.test_g11_capability 11 OK; full suite 192 OK.
- Builder oracle ACCEPTED 14/14 (seed 1811); naive REJECTED 2/14; noop REJECTED 0/14.
- M11 oracle (r3-contract edition) 22/22, naive 3/22, noop 3/22; r2 per-source oracle (r3-contract edition) 8/8,
  naive 1/8; r3 sources oracle 19/19, naive 0/19, noop 0/19.
- No __pycache__ left in the copy; candidate status clean.

## Mutation tests (builder's 49 G11 r3 mutants copied unchanged, scripts/builder_mutants_g11r3.py)
Kill = any core result or OBS detail change against the unmutated baseline.
- 3.13.15: 49/49 (v2). 3.9.6: 48/49; survivor bytecode_written, the same Apple 3.9 pycache_prefix equivalence as
  r2 and as the builder's own 3.9 run. (v1 on 3.13.15: 48/49, alone_is_all_silent alive; results/v1.)

## Fresh caller (results/fresh-3.9.6.txt, results/fresh-3.13.15.txt)
README commands under env -i with a new HOME and a python3 shim: every exit, status, availability, burn,
coverage and decision as documented and identical to the r2 fresh caller (the relabelled fixtures did not change
any result); README.md refused exit 2; no new files, no __pycache__.

## Not done
No real incident telemetry (all synthetic); no M2, promotion, PR or merge.

## Publication note
One stored control result (results/oracle-naive-3.12.14.json, the naive stub's stderr tail) contained part of a
local interpreter path; it is replaced by `[local-path]` in the published copy only. No result value changed.
