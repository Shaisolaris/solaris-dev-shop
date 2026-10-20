# M42 validation of G42 48bfa86 (Grok self-validation, not independent review)

Verdict: **PASS (no P1, P2 or P3; two P4 observations).** The day 7 stack binds the newest head of every
prerequisite, the G38 merge kept every line from both sides, each cross-check fires when the thing it guards is broken,
and a fresh-clone `--run all` gives INTEGRATED. This is Grok checking a Grok build. It is not independent review and
accepts nothing.

## Binding (raw/binding-verify.txt)
- Candidate 48bfa8614d31332ca483d94ba413ef5ba6bce3a0 on review/grok-g42-daily-integration (remote re-checked,
  unmoved), parent prerequisite merge a188179.
- G42.patch sha256 45452f17...5b7b equals `git format-patch --stdout a188179..48bfa86`; MANIFEST.sha256 9/9 match and
  equals the diff set. The G42 commit touches only its writable set. The five shared daily integration files are
  byte-identical to G30 r2 135d95f.
- All 11 prerequisite commits in plan.json are the current remote branch heads (checked 2026-10-19 PDT).

## Checks I wrote for this pass
- **Merge union (oracle/m42_union.py, results/union-check.txt).** For the four G42 prerequisite merges, every file both
  parents changed: lines added by either side, and base lines both kept, are all in the merge. Only 3ed5aec (G38 r3)
  has such files (6); 0 lines lost. Authoring note: the first run reported 2 lost lines that were JSON list items
  whose trailing comma changed when a neighbour was added; the check now ignores trailing commas (disclosed).
- **Cross-check probes (oracle/m42_probe.py).** On copies of the tree: clean copy, no finding; broken G04 handoff, x1;
  pyproject license changed to Apache-2.0, x2; boundary_probe.py removed or not compiling, x3 (x1 also fires because
  the G39 drill runs that script); legal-advisor contract stops naming the G38 test, x4; G37 report drops its
  not-legal-advice text, x4. 7/7 on all four Pythons. Authoring note: P3 and P4 first expected x3 alone; I allowed x1
  after confirming drill.py runs boundary_probe.py.
- **Live run.** Fresh clone at 48bfa86, Python 3.9.6, `daily_integration.py check --plan examples/capabilities/G42/plan.json
  --run all`: VERDICT INTEGRATED, rc 0, clone clean after (results/live-run-all.txt).

## Oracles and results (results/pyversions.txt)
| Python | m42 probes | G42 tests | integration oracle | naive | no-op | cross_checks |
|---|---|---|---|---|---|---|
| 3.9.6 | 7/7 | OK | 13/13 | 1/13 | 0/13 | CLEAN |
| 3.11.16 | 7/7 | OK | 13/13 | 1/13 | 0/13 | CLEAN |
| 3.12.14 | 7/7 | OK | 13/13 | 1/13 | 0/13 | CLEAN |
| 3.13.15 | 7/7 | OK | 13/13 | 1/13 | 0/13 | CLEAN |

Both merged contracts (legal-advisor, security-auditor) parse. Full suite on fresh clones (results/full-suite-matrix.txt):
388 tests OK on all four Pythons (2 skipped on 3.9.6); browser processes 0.

## P4 observations
- P4-1 x3 requires the security-auditor script list to be exactly boundary_probe.py and provenance_check.py, so a
  legitimate third script would be reported as a finding. It fails closed.
- P4-2 x4 checks that the legal-advisor contract text contains the two test paths, not that the contract wires them
  to a capability. Adequate for this stack.

## Context, not a finding
G42 does not stack G20, G22 or G30. G22 h1 8bc3553 (published this batch) is not in G42; G42 does not need it.
Builder mutants not re-scored. No browser was launched.
- results/live-run-all.txt and .json: one self-test line listing engine provider names was shortened for the safety scan; nothing else edited.
