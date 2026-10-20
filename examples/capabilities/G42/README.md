# G42 day 7 daily integration

Revision r3 (final integration refresh) stacks every build goal at its newest remote head on v0.61 `02ba9c5`:
G01 h1 `aa0b083`, G02 r4 `90a5ec9`, G03 `d4d98f2`, G04 r3 `e9fa278`, G05 r4 `1b840cd`, G07 `0d6a78d`, G08 `ddebe98`,
G09 `edfa64d`, G10 `f79be61`, G11 `13ba705`, G13 `5666e7b`, G14 `6f7b23a`, G15 r4 `7e7f361`, G16 r8 `49aba3f`,
G17 `550f184`, G19 h1 `350d175`, G20 r3 `0d4db69`, G21 `822a9c1`, G22 h2 `29cd7fc`, G23 `0ff2641`, G25 `eb9c7c4`,
G31 r3 `fcf492a`, G32 r3 `b69f328`, G33 r4 `a4ae555`, G34 `de76fae`, G35 `34bb98f`, G37 h1 `e9b7a77`, G38 r4
`ba70b69`, G39 r3 `9ab3562`, G40 r4 `eabf69a` and G41 r3 `a1bd6c4` (its commit subject says r2 in error). The
goal heads are merged one by one on top of r2 `956792e` without rewriting it; plan.json names all 31.

Revision r4 (2026-10-20) merges seven newer heads on top of r3 `9d844d2`, one merge each, without rewriting it:
G09 h1 `1cab0f8`, G11 h1 `94a0de4`, G15 r5 `2a3310b`, G32 r4 `3346efa`, G34 h1 `6ad99da`, G39 r4 `97d3d05` and
G41 r4 `b881336`. None of the seven git merges touches a file changed on both sides; plan.json carries the new commits. G40 r4
and G41 r4 still carry G39 r3's three delivery-evidence files, so plan.json resolves those three overlaps in
favour of G39 r4.
G09 h1, G11 h1 and G34 h1 are hardening commits on top of accepted revisions and are not accepted themselves.
The union statement below holds for the r3 tree; r4 adds only the seven goals' own diffs to it.

The six daily integrations (G06 r2, G12 r2, G18, G24 r2, G30 r3, G36 r2) are not stacked as prerequisites: each
one's own plan test (`test_stack_binds_this_tree`) binds its exact tree, so their evidence folders fail on any
other tree. Every build they integrate is here at the same head, and this tree equals the union of all six
integration trees with only their own `examples/capabilities/GXX/` folders and tests removed (checked with
`git diff`). G18's carried G11 x2 cross-check finding is not changed here; it stays for root. There are no outside
contributions on this day (P03 and P04 stay bound by G24).

| Check | What it compares | Result on this stack |
|---|---|---|
| x1 | the G39 delivery drill with the repaired G02, G04, G05 and G19 tools | DRILL PASSED, 14 steps ok |
| x2 | G38 provenance on the integrated tree (G38's own fixtures excluded) | consistent, 65 declarations, all MIT |
| x3 | security-auditor contract after the G19 + G38 union, read by G40 skill-copy | both scripts present and compiling; only the 3 documented shared standards are outside the folder |
| x4 | what legal-advisor receives from G37 and G38 | both tests named; G37 not legal advice, G38 not a legal opinion |

No cross-goal defect was found on this stack. The checks are not blind: the tests swap in a failing drill, a
conflicting license declaration, a removed listed script, a skill copy missing a script and a G37 report with
no legal boundary, and each one is reported.

Interface defect found and reconciled in r3. The first r3 tree (4ef54ff) failed `--run all`: G05's oracle o13,
`tests.test_g05_capability` and the full suite failed on all four Pythons. G01's fixture-runner contract accepts
only each fixture kind's own top-level keys, and `expectations.gate_codes` only with `outcome: fail_gate`; G05 r3's
o13 closure fixture used the new `subject_revision` / `verified_revision` fields and `gate_codes` with
`expect_blocked: true`. Two fixes: G05 r4 `1b840cd` writes the fixture in the fail_gate form (G05's own file), and
this revision adds the two revision fields to the closure kind's keys in `quality_os.py` (the key table exists only
where G01 and G05 meet; assurance is G42's writable scope), with a note in ASSURANCE.md and two tests in
`tests/test_g42_capability.py` (`Interfaces`) that failed before the fix. A misspelled revision field is still
`INVALID_PACKET`.

Conflicts. r1 (G38 merge): the legal-advisor contract and learnings keep the G37 and the G38 entry, and the
security-auditor contract has one scripts list with `provenance_check.py` (G38) and `boundary_probe.py` (G19). r3,
each resolved as a union in its merge commit (nothing from either side dropped): ASSURANCE.md (G01 h1 fixture-runner
text, then the G05 r3 Revision binding section), handoff-work-orders.md (the exit 2 line lists every reason from
G04 r3 and G07), and the site-reliability-engineer contract (G09 and G11 forward tests) and COO contract (G11 and
G17 forward tests), each appending one list entry.

Forty-five overlaps are named in `resolved_overlaps`, each with its reason. Most are files where one candidate
carries an older copy and another builds on it (HEAD is the newest blob); the rest are files two or more goals
edit, checked line by line (HEAD keeps every line any side added; a line missing from an older copy is one a newer
candidate replaced).

No check here starts a browser or opens a network connection beyond the loopback server the G19 oracle starts.

```bash
python3 employees/quality-security/assurance/daily_integration_oracle.py -- python3 employees/quality-security/assurance/daily_integration.py  # ACCEPTED 13/13
python3 employees/quality-security/assurance/daily_integration_oracle.py -- python3 employees/quality-security/assurance/daily_integration_controls/noop.py  # REJECTED 0/13
python3 examples/capabilities/G42/cross_checks.py  # CROSS-CHECKS CLEAN (0 findings)
python3 employees/quality-security/assurance/daily_integration.py check --plan examples/capabilities/G42/plan.json  # VERDICT INTEGRATED
```

The last line runs no tests or cross-checks, so it only binds the stack. `--run all` also runs every
prerequisite's tests and oracle and the cross-checks.
