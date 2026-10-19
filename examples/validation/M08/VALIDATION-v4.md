# M08 v4 addendum: Grok self-validation of G08 52cb49d (not independent review)

Written by the Grok Bot executor at 02:00 PT on 2026-10-19. The candidate was not modified.

**Why this file exists:** while this pass was still running, a commit was published at 01:53 PT on review/grok-m08-validation (5f934f3, VALIDATION.md and HANDBACK.md in this folder). That commit was built from this folder's intermediate v3 results. I did not make that commit and I did not overwrite it. This addendum records the final v4 results, which that commit does not contain. It was pushed at 02:02 PT, on the owner's instruction, as a fast-forward on top of 5f934f3.

**Grading status:** this file supersedes 5f934f3's grading (VALIDATION.md and HANDBACK.md in this folder). The repeat-deploy receipt is graded P3 here, not P4, and the core counts and teeth numbers here replace v3's 9/9 and 26/33 and 25/33. VALIDATION.md is kept unchanged as the record of the 01:53 commit.

## What changed after v3
- **New row D12 (core),** added after the v3 teeth run showed gaps; disclosed. It covers re-pinned artifacts: a relabelled REVISION, a secret-like file and a symlink, each with the digest re-pinned in the plan and approval. It also covers an approval whose action alone is changed, live data at the wrong schema version, an empty required live file, and an existing release folder with other content. Every case exits 2 with the tree byte-identical.
- **Oracle v4:** core 10/10 on 3.9.6, 3.11.16, 3.12.14 and 3.13.15. Controls: naive 4/10, noop 3/10.
- **Teeth v4,** using the builder's 33 mutants on 3.11.16 and 3.13.15: my oracle kills 31/33 on both, with identical kill sets. The two survivors:
  - required_files_empty_ok: my empty-file case is refused earlier by the live-release digest check; it fails the builder tests.
  - no_snapshot_verify_EQUIV: the builder marked it equivalent, and it passes the builder tests.
  - Rows that depend on timing are not counted as kills: D06, D10 and D10_timing, plus the guard ids D06 and D10 after a harness crash seen once on 3.11.16 in v3.
- **Unchanged:** builder G08 tests 10 OK, full suite 142 OK and builder oracle 16/16 on all 4 interpreters. The fresh caller matched every documented exit on 3.9.6 and 3.13.15, with no __pycache__.

## Findings (my severity)
- **P3-1, concurrent deploys** (documented as unsupported: "One deployer at a time; no lock").
  - Two overlapping deploys of r3-broken started 4 to 12 ms apart. In 4 of 27 trials (results/race/followup-3.9.6.txt), both callers got exit 1 ("health check failed; rolled back"). Yet r2 is live with schema version 3, totals multiplied by 100, and no pending journal.
  - In that state (rollback-after-race-3.9.6.txt):
    - `recover` exits 0 with "nothing to recover";
    - the approved rollback is refused (exit 2) because live health fails;
    - a repeat deploy of r2 exits 0 with "nothing changed".
  - So the documented recovery paths cannot heal it, and both receipts are false.
  - The sweep (results/race/sweep-3.9.6.txt) also shows 1 of 62 trials left on the broken r3 with a pending journal. In 49 of 62 r2-twice trials both callers report "deployed".
- **Is it a P2 for the goal spec? My decision: P3, not P2.**
  - The G08 acceptance criteria are all single-deployer: a valid deploy and rollback succeed, and missing authority or rollback refuses before mutation. All of them hold, including under SIGKILL.
  - The limit is documented in the doc, the README and the handback.
  - The target is a disposable fixture.
  - The damaged state is caught by the next preflight: it refuses, so nothing more is built on it.
  - It would become P2 if the owner reads the QA2 line "realistic operational scale/concurrency/failure variant" as required behaviour. A per-target lock is the obvious fix. No patch is included, since none is required below P2.
- **P3-2, a repeat deploy gives a success receipt without checking health or approval** (single deployer, results/repeat-unhealthy-3.9.6.txt). After r2 is live, an outside writer sets the schema version to 3, and preflight then exits 2. Even so, `deploy plan-r2.json` exits 0 ("already live with this artifact; nothing changed"), both with the approval and with no approval at all. Nothing is mutated, and the doc does say a repeat "changes nothing". But exit 0 reads as a success receipt while the health precondition fails, which is the false-receipt case M08 targets. The 01:53 commit graded this P4.
- **P4-1, rollback approval is reusable.** The same rollback-to-r1 approval file was accepted again after a redeploy of r2 (D07b). Approvals carry no deploy id or expiry.
- **Observation, not graded:**
  - D06 SIGKILLs an approved rollback 10 times per interpreter, under parallel load from the teeth runs. In 1 or 2 of the 10 on 3.11.16, 3.12.14 and 3.13.15, r2 was still live at schema 2, but preflight and a second rollback were both refused.
  - It did not reproduce in 150 trials on 3.9.6 (results/rollback-kill-diag-3.9.6.txt), and I did not find the cause. v1 of that diagnosis stopped on a completed rollback, where a refusal is expected (kept as rollback-kill-diag-v1).
- **Strengths:**
  - Refusals leave the whole tree identical (files, folders and links), across D02's 15 cases, D07's 8 and D12's 7.
  - Preflight writes nothing.
  - Crash drills at every phase are refused until `recover`, and `recover` restores the release and data, after which a redeploy works.
  - In 16 real SIGKILLs, each timed to land just after the deploy journal appeared, the target always ended consistent (3 left a pending journal and were recovered).
  - Failed migrations and broken releases restore both release and data.

## Harness errors (disclosed)
- **v1:** the D02 target-outside case used "../w/env", which resolves back inside the plan folder.
- **v2:** the SIGKILL timing mostly missed the deploy window. v3 waits for the journal to appear.
- **v4a:** re-pinning crashed because the tool's `digest` refuses symlinks. v4b falls back to the fixture builder's digest rule.
- All earlier outputs are kept under results/kept/.

## Prerequisites
- G08's parent is exactly G03 r3 d4d98f2180ed9b92fd058a2350285f60f83b877d, and the G03 branch head is unchanged (not superseded).
- G03 r3 is M03 r3 PASS (1020f11).
- The diff equals G08.patch (fd66c679...), and all 32 manifest entries match.
