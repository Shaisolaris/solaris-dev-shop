# M40 validation of G40 r2 0f593a1 (Grok self-validation, not independent review)

Verdict: **FAIL (one P2)**. A fresh install from the wheel outside the checkout works on 3.11, 3.12 and 3.13, 3.9 is
refused by Requires-Python, and the wheel's package and metadata checks all pass. But the tool's wheel-smoke builds
inside the checkout it promises never to edit, and a stale build left there is packed into the next smoked wheel while
the smoke reports pass. This is Grok checking a Grok build. It is not independent review and accepts nothing.

## Binding (raw/binding-verify.txt)
- Candidate 0f593a1d1903aa05c126473c2310364310856147: b0c5737 merges G39 r2 05378c4 into G40 r1 8428c90 (tree d35e416
  equals `git merge-tree --write-tree 8428c90 05378c4`, so no hand edit), then the bytecode follow-up.
- G40-r2-followup.patch sha256 609dc954 equals `git diff --binary b0c5737 0f593a1`. G40-on-G39r2.patch (79c67074) is
  `git diff 05378c4 0f593a1`, the whole final candidate over G39 r2 including the follow-up; applied to G39 r2 it
  reproduces the 0f593a1 tree exactly. The handback calls it "G40's change on the new base", which is the same thing
  stated loosely. MANIFEST.sha256 17/17 match and equals the diff set over G39 r2.
- Prerequisite chain: G39 r2 is an ancestor. G39 r2 itself sits on superseded G05 and G19 heads and fails M39 r2
  (P2-1, a4182208); G40 inherits both, and its rebase rule (merge the new G39 head) will apply.

## Fresh install from the wheel, outside the checkout (results/fresh-install-wheel.txt)
Wheel built offline from a clean `git archive` of 0f593a1 with 3.11.16 and its own setuptools 82.0.1
(`pip wheel . --no-deps --no-build-isolation`, PIP_NO_INDEX=1), sha256 192ea7b4. Installed with `--no-index` into a new
venv per interpreter, run from an empty folder outside the checkout under env -i with a new HOME:
- 3.11.16, 3.12.14, 3.13.15: install OK; `solaris-intake self-test`, `intake --explain ...` (assign and clarify cases)
  and `skills playwright --json` all exit 0; the package imports from site-packages; the run folder stays empty.
- 3.9.6: install refused, "requires a different Python: 3.9.6 not in '>=3.10'", matching the docs.
- Not claimed and not working: `solaris-intake --version` (exit 2) and `python -m solaris_intake` (exit 1). Observation.

## Package and metadata (results/wheel-metadata.txt, oracle/m40_wheel_meta.py)
14/14 on the clean wheel: Name, Version 0.61 and Requires-Python >=3.10 equal pyproject.toml; License MIT; Summary equals
the description; no runtime requirements; entry point `solaris-intake = solaris_intake:main`; every RECORD hash and size
true and RECORD lists every member; no bytecode; no employees, tests, examples or checkout control-plane paths; members
equal the source package files and their bytes; pure py3-none-any tag. The wheel from the stale-build probe fails two of
these (an extra member not in the source).

## Findings
- **P2-1 wheel-smoke edits REPO, and a stale build there is shipped and passed.** It runs `pip wheel REPO`, so
  setuptools writes build/ and solaris_dev_shop.egg-info (19 entries) into the checkout, contrary to the docstring
  "Never edits REPO" (A06). A file left in build/lib (for example from an earlier build of a since-removed module) is
  packed into the next smoked wheel, installed, and the smoke still says pass with 0 findings (A07, results/
  probe-wheel-smoke.txt). The builder's own suite and oracle leave the same 2 entries in a clean copy on 3.11+
  (pyversions matrix, "build/egg-info in copy: 2"); the handback reports only 0 pycache. So the fresh-install evidence
  the tool produces can come from a wheel that is not the clean source. Negative control: G40 r1 8428c90 fails A06 to
  A08 too (and A01 on 3.11, the bytecode bug the follow-up fixed).
- **P3-1 `--outside` inside the checkout is accepted** and the report still says "outside the checkout"; it writes the
  venv and wheels into REPO (A08).
- **P3-2 Offline reproduction of the documented outcome.** On an offline host whose interpreter has no setuptools
  (3.12.14 and 3.13.15 here), wheel-smoke exits 2 and the README's `portability_oracle.py  # ACCEPTED 8/8` gives
  REJECTED 5/8 (results/fresh-caller.txt, PIP_NO_INDEX=1). docs/install.md does not say the wheel build needs network
  or an installed setuptools. The intake router itself runs offline once installed (verified above).
- **P4-1** The offline failure message is a cut pip tail (". Nothing was written.") while `--outside`/wheels was created.
- **P4-2** `skill-copy` without `--dest` leaves a g40-skill-* folder in TMPDIR each run.

## Proposed fix (P2-1 and P3-1; not applied)
proposed-fix.patch (host_portability.py only): refuse `--outside` at or under REPO (exit 2); build from a private copy of
REPO under the work folder that skips build, dist, *.egg-info, caches and bytecode; flag any solaris_intake member that
has no source file (`wheel_member_not_in_source`). Positive control (results/fix-positive-control.txt, results/
controls.txt): applies cleanly; REPO gains 0 entries; a stale build/lib file is not packed; `--outside` inside REPO exits
2 and creates nothing; M40 oracle 8/8 on 3.11.16; builder G40 tests OK and portability oracle 8/8 on 3.13.15 and 3.9.6.

## Oracle and results
oracle/m40_oracle.py, written from M40.md, G40.md, docs/install.md and the tool docstring: A01 python-bounds (also an
unseen 3.10-only script caught on 3.9), A02 skill-copy broken lone copy and bad roles, A03 --out, A04 wheel member
inspection, A05 wheel-smoke clean control, A06 to A08 the findings above, A09 3.9 refusal. Wheel rows are scored only
where an offline build is possible (3.11.16 here: 5/8); on 3.12.14 and 3.13.15 (no setuptools) 4/4 with wheel rows
recorded as skipped; on 3.9.6 5/5 including A09. Builder: G40 tests OK, portability oracle 8/8, naive and no-op rejected
on all four Pythons (the builder oracle and suite build wheels with pip build isolation, which fetched setuptools from
the package index; that network use is the builder's harness, disclosed).

## Teeth
Builder G40 r2 mutants (9, unchanged copy): 8/9 killed on 3.13.15, 3.9.6 and 3.11.16. hp_role_escape_ok survives my
oracle (a `..` role that resolves to a real employee is not among my bad roles) and is killed by the builder's tests.
- teeth-3.11.16.log: hp_role_escape_ok SURVIVED
- teeth-3.13.15.log: hp_role_escape_ok SURVIVED
- teeth-3.9.6.log: hp_role_escape_ok SURVIVED
- builder tests: hp_role_escape_ok builder tests: KILL FAILED (failures=1) FAIL: test_role_rejects_parent_segments (tests.test_g40_capability.G40Direct.test_role_rejects_parent_segments)

## Disclosures
- Authoring fixes, both before teeth (results/oracle-authoring-fixes.txt): the O05 skip text mislabelled the version
  check (detail text only), and m40_wheel_meta.py crashed instead of reporting a member not in the source.
- The fresh caller runs the README lines verbatim except that the builder-owned path /tmp/g40-out in the wheel-smoke
  line is replaced by a private folder, and PIP_NO_INDEX=1 keeps it offline.
- results/fresh-install-wheel.txt: the provider list printed by self-test was trimmed to "providers list trimmed for the
  publication scan" because one provider name trips the publication scanner; the scanner was not changed.
- Collision check: no builder directory touched; week-grok before and after records.

## Pyversions matrix
```
ls: /tmp/m40mx-JJqwLD/build: No such file or directory
== 3.9.6 | g40: OK (skipped=1) | full: Ran 313 tests in 185.539s  OK (skipped=1)   | builder-oracle: ACCEPTED 8/8 | builder-naive: REJECTED 6/8 | builder-noop: REJECTED 3/8 | m40-oracle: M40 ORACLE 5/5 scored PASS | pycache in copy: 0 | build/egg-info in copy: 0
== 3.11.16 | g40: OK | full: Ran 313 tests in 165.786s  FAILED (failures=1)  FAIL: test_oracle_accepts_real_api_and_rejects_stubs (test_g19_capability.ProbeAndOracle.test_oracle_accepts_real_api_and_rejects_stubs)  | builder-oracle: ACCEPTED 8/8 | builder-naive: REJECTED 5/8 | builder-noop: REJECTED 2/8 | m40-oracle: M40 ORACLE 5/8 scored FAIL | pycache in copy: 0 | build/egg-info in copy: 2
== 3.12.14 | g40: OK | full: Ran 313 tests in 176.052s  OK   | builder-oracle: ACCEPTED 8/8 | builder-naive: REJECTED 5/8 | builder-noop: REJECTED 2/8 | m40-oracle: M40 ORACLE 4/4 scored PASS | pycache in copy: 0 | build/egg-info in copy: 2
== 3.13.15 | g40: OK | full: Ran 313 tests in 156.270s  OK   | builder-oracle: ACCEPTED 8/8 | builder-naive: REJECTED 5/8 | builder-noop: REJECTED 2/8 | m40-oracle: M40 ORACLE 4/4 scored PASS | pycache in copy: 0 | build/egg-info in copy: 2
candidate status lines: 0
```
