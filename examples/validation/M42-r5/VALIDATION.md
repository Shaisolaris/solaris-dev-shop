# M42 r5: validation of G42 r5 2f3eabc, final integration with G39 r5 and G40 r5 (Grok self-validation, not independent review)

Validator: Grok, the same agent family that built G42. This is self-validation, not independent review, and accepts nothing.

## Verdict
**PASS. No P1, P2 or P3 is open.** M42 P4-1 and P4-2 stand, unchanged. Two new P4 observations (OBS-1, OBS-2) below.

## Binding (raw/binding-verify.txt)
- Candidate 2f3eabc995f83711e24e4b092ed53d5ae1f5f499 on review/grok-g42-daily-integration, re-checked on the remote.
- It fast-forwards r4 1611581 (M42 r4 PASS) with 5 commits: the G39 r5 merge fa83205 (G39 3f09063), the G40 r5
  merge a768362 (G40 99b49c6), their two first-parent sides, and the plan commit 2f3eabc.
- Plan G39 and G40 commits equal those goals' remote heads. 12 files change; their sha256 values are listed.
- The G42-r5 handback carries no patch or MANIFEST.sha256, so the binding is by commit SHA on the remote (OBS-2).

## Results at 2f3eabc
- **Union check (oracle/m42_union.py, results/union-check.txt):** fa83205 changes no file on both sides; a768362
  auto-merges docs/install.md: 4 lines added, 69 kept by both, 0 lost. UNION OK.
- **Overlap audit (oracle/m42r5_overlaps.py, new, results/overlap-audit.txt):** recomputed from git alone for all 54
  resolved_overlaps entries.
  - All 9 entries r5 adds or rewrites pass: HEAD holds the winning goal's blob and every losing copy is an older
    revision of that same file in the winner's own history (three G39 paths at the G39 r5 blobs, five G40 paths at
    the G40 r5 blobs, technical-writer SKILL.md at the G41 r4 blob, which builds on the G40 blob).
  - The heuristic flags 8 older entries (fleet-dispatcher handoff, assurance quality_os and ASSURANCE.md, four
    capability contracts). All 8 HEAD blobs are identical at r4 1611581, which M42 r3 and r4 passed. A spot check
    found the "lost" lines rewritten in place in HEAD (for example the G11 incident_slo contract line and the
    closure_is_current waiver handling). Not an r5 change.
- **Probe (oracle/mdaily_probe.py, unchanged): 8/9, the same as r4 (results/probe-2f3eabc.txt, probe-1611581.txt).**
  - H1 passes: every plan commit equals its goal's remote head (results/remote-heads-at-start.txt).
  - H3 lists the same five hand-resolved r1 and r3 merges disclosed since M42 r3. The two r5 merges are clean.
  - T0 to T4 and X1 pass.
- **Teeth (oracle/m42r5_teeth.py, results/teeth.txt): 6/6 as expected.** Fresh clone, plan edited without committing,
  so DIRTY_TREE also appears.
  - Control: rc 0, no findings.
  - Removing the six new G40/G41 entries gives OVERLAP on exactly those six paths; removing only the technical-writer
    entry gives OVERLAP on that path. The new entries are load-bearing.
  - Pinning G40 back to r4 eabf69a gives DRIFT on the five G40 r5 files.
  - Pinning G39 back to r3 9ab3562 gives DRIFT.
  - Limit case: pinning G39 back to r4 97d3d05 gives no DRIFT (OBS-1).
- **Four Pythons (results/pyversions.txt):** 3.9.6, 3.11.16, 3.12.14, 3.13.15: G42 tests OK; integration oracle
  13/13; naive 1/13; no-op 0/13; cross-checks clean; tree clean.
- **Live `--run all`:** fresh clone, root's acceptance files (results/live-run-all.txt). VERDICT INTEGRATED, rc 0,
  clone clean after. G39, G40 and G41 read as CANDIDATE.
- **Full suite on fresh clones, macOS, one Python at a time (oracle/suite_seq.sh, results/full-suite-matrix.txt):**
  827 OK on 3.9.6, 3.11.16, 3.12.14 and 3.13.15. The handback's parallel-run G40 timeouts on 3.11 to 3.13 do not
  occur when the suites run in sequence. No browser process was seen.
- **CI replay of every .github/workflows/ci.yml step:** Linux x86_64 on 3.10.22, 3.12.15 and 3.13.5
  (results/linux-*.txt), plus macOS arm64 on 3.12.14 (results/mac-312-2f3eabc.txt).
  - Every step is green: self-test, unittest (827 OK), wheel smoke, JSON, quality audit, manifests, catalog,
    symlinks, metadata. The tree is clean after. Windows was not replayed (no host).
- **G39 r5 and G40 r5 diffs, read in full:** G39 r5 makes an input the run rewrote a gap (never a clean GO) and adds
  verify --strict; G40 r5 adds --wheelhouse for offline wheel-smoke and names a missing build backend. Both stay in
  their own files; their own M passes are separate from this one.

## Findings
- **OBS-1 (P4, pre-existing tool limit, not an r5 change):** daily_integration.py does not compare a path named in
  resolved_overlaps with any blob, so a stale pin whose files already differ from the other copies (G39 back to r4)
  gives no DRIFT. The plan test, probe H1 and this overlap audit catch it instead. For root: an optional expected
  HEAD blob per resolved_overlaps entry would make the tool check it. daily_integration.py is unchanged in r5.
- **OBS-2 (P4):** the G42-r5 handback has no patch or MANIFEST.sha256, unlike r4; binding is by remote SHA.
- Handback P4 (G40 wheel-smoke needs a package index or a wheelhouse) confirmed: the CI wheel-smoke step is green
  with network access; offline use needs --wheelhouse.
- M42 P4-1 and P4-2 stand, unchanged.

## Notes
- No browser was launched. Nothing was pushed to main. Release stays NOT_READY. Accepts nothing.
