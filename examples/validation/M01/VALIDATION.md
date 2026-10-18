# M01: Grok self-validation of G01 (fixture runner fails closed)

Grok self-validation. This is not an independent review. It was produced by the same
agent family that built G01 and must not be read as one.

Verdict: **FAIL** (one P2 residual in the false-pass class G01 targets; no regressions).
The contract G01 added holds in full (fresh oracle core 12/12 on the candidate versus 4/12 on
base 02ba9c5) on Python 3.11.16, 3.12.14 and 3.13.15. The P2 is pre-existing on base, so G01
did not introduce it, but G01 states that a misspelled fixture kind must not count as a
passing fixture, and a misspelled fixture_kind *key* still does.

## Candidate binding and its limit

- G01 has **no published commit**. It exists only as a handback (uncommitted changes on
  week-grok at 02ba9c5). This pass validates the exact bytes of `G01.patch`
  (sha256 85a506e6f3fcc43c15184d3d229c9b4fa34313da1d6555af683b4e407257a6e0) applied to
  base 02ba9c571b10ad1dba792d2ac5534bcad3171e67 in a detached scratch worktree.
- The builder shipped no SHA256 manifest. The per-file manifest in
  `raw/candidate-binding.txt` was computed by M01 (quality_os.py 2c55de60...,
  tests/test_fixture_runner.py 2d0563ce..., ASSURANCE.md c4ac6f69..., docs/install.md
  ee9ea539...). The week-grok working copies matched those hashes at the time of the
  check. If G01 is later committed with different bytes, this result does not carry over.
- Not repeated here: the earlier evidence (the handback's 7 new tests and 91/91 on 3.12, the
  8/18 to 18/18 probe, the earlier review's four questions and the install.md check). Only
  new gaps and new evidence are reported.

## Method

- `oracle/m01_oracle.py`: a fresh black-box oracle written from ASSURANCE.md's fixture
  contract, not from the builder tests. It drives `quality_os.py run` and `suite` through
  the CLI only, on fixtures generated in temp dirs, with a minimal environment. It has
  12 core checks (the contract G01 claims) and 14 adversarial gap checks.
- The oracle was run on the candidate on 3.11.16, 3.12.14 and 3.13.15, and on base 02ba9c5
  on 3.12.14. Results are in `results/cand-*.json` and `results/base-3.12.json`.
- Builder suite (`python -m unittest discover -s tests`): 91/91 OK on 3.11.16 and 3.13.15
  (new) as well as 3.12.14 (`results/suite-*.txt`). CI covers 3.10, but no 3.10 interpreter
  exists on this machine, so 3.10 was not run.
- Fresh caller (`results/fresh-caller.txt`): env -i, new HOME, a `python3` shim to 3.13.15,
  and an offline guard (a socket-blocking sitecustomize). It ran the commands verbatim from
  ASSURANCE.md "## Commands" (self-test, run, suite, audit, route security, unittest -v),
  with the fixture paths given as absolute paths. All exit 0; 91/91 OK.
- Teeth (`oracle/make_mutants.py`, `results/teeth.tsv`): 13 exact single-occurrence mutants,
  each reverting or weakening one G01 guard, plus a stub (the base engine) and a no-op
  control. Each was scored with the M01 oracle core, the builder's
  tests/test_fixture_runner.py and the full builder suite.

## Results

| | candidate 3.11 / 3.12 / 3.13 | base 02ba9c5 (3.12) |
|---|---|---|
| core checks c01 to c12 | 12/12 on each | 4/12 (c04, c07, c09, c10 already held) |
| gap checks open (x01 to x13) | 13/13 on each | 13/13 (all pre-existing) |
| x14 symlinked fixture subdirectory | not followed on any interpreter (total 1) | same |

Teeth (14 non-control mutants; the control survives everywhere, as it should):

| scorer | killed | survivors |
|---|---|---|
| M01 oracle core | 12/14 | mut_outcome_set ("fail" accepted as an outcome; c06 does not try "fail"); rv_missing_dir (message-only: the zero-fixtures error still fails the suite with rc 1, so it is equivalent at the ok/rc level) |
| builder tests/test_fixture_runner.py | 12/14 | mut_kind_precedence (`kind` read before `fixture_kind`); mut_exp_keys (`decision` accepted as an expectation key) |
| builder full suite | 12/14 | same two as the line above |

Together the scorers kill all 14. One mutant (mut_kinds_empty) had an ambiguous first anchor
(2 occurrences). It was rejected by the generator's assertion before any run, re-anchored,
and run on its own: killed by all three scorers.

## Findings

### P2

**F1. A misspelled fixture-contract key still produces a silent false pass.**
`evaluate_path` validates the *value* of `fixture_kind`/`kind` and the keys inside
`expectations`, but not the fixture's own top-level keys. When the kind key is misspelled,
or the `packet` or `expectations` wrapper key is, the fixture silently becomes an
unwrapped packet with no expectations. A closure or legal fixture with a misspelled field
silently drops that field.
- x01: `{"fixture-kind" | "Fixture_Kind" | "fixturekind" | "fixture_knid" | "fixtureKind":
  "closure", "finding": <accountable security-auditor>, "closer_role": "security-auditor",
  "expect_blocked": false}` gives rc 0, ok true, `gate_codes: []`. The self-approval control
  is never evaluated.
- x02: `{"pakcet" | "Packet" | "packets": <packet missing its security gate>,
  "expectations": {"outcome": "pass"}}` gives rc 0, ok true.
- x03: `{"packet": <passing packet>, "expectation" | "Expectations" | "expected":
  {"outcome": "fail_gate"}}` gives rc 0, ok true. The stated expectation is dropped.
- x04: `{"fixture_kind": "legal", "txt" | "Text" | "legal-text": "I am your attorney; file
  this lawsuit now."}` gives rc 0, ok true. The text evaluated is empty.
- x12: a duplicate `fixture_kind` key (closure, then packet) takes the last value, giving a
  passing packet.
- The fresh caller reproduces x01 through the documented `suite` command: a two-file dir
  holding a valid negative packet and the x01 fixture reports ok true, 2/2.
- Scope: this is distinct from the handback's disclosed limitation (unknown packet fields
  such as `dimenions` inside `evaluate_artifact_packet`, left for G05). F1 concerns the
  fixture runner's own keys and can be fixed in the runner without touching the packet API.
- `proposed-fix.patch` (sha256 2aec9e307685c70206453339a59da710f0d8f0b9d789760b13c7dda61612af79,
  not applied to the candidate) makes the runner refuse fixture keys that are near-misses of
  `fixture_kind`/`kind`/`packet`/`expectations` (case, separator, or difflib ratio >= 0.8).
  For a wrapped packet, closure or legal fixture, it refuses top-level keys outside that
  kind's fields (plus `description`/`name`/`notes`). For an unwrapped packet, it refuses only
  closure or defect payload fields. Packet field names are left to G05. No engine field name
  scores >= 0.6 against a contract key.
- Positive control (`results/proposed-fix-positive-control.txt`): `git apply --check` OK on
  the candidate tree. With the patch, x01 to x04 and x12 hold, core 12/12, no other check
  changes, and the builder suite stays 91/91 on 3.11.16, 3.12.14 and 3.13.15. The
  fresh-caller suite becomes ok false, 1/2.

### P3

**F2. Some expectations are accepted but never checked (vacuous).**
- x05: `accountable_role` is checked only when the result has findings. A passing packet
  with `{"outcome": "pass", "accountable_role": "nobody"}` passes, and so does a blocked
  legal fixture with `fail_gate` and `"accountable_role": "nobody"`.
- x06: `gate_codes` is checked only when `outcome` is `fail_gate`. With
  `{"outcome": "pass", "gate_codes": ["MISSING_SPECIALIST_GATE"]}`, or `gate_codes` alone,
  a passing packet passes.
- x07: for `fail_gate`, `gate_codes` matches when *any* listed gate fires, and `[]` matches
  every gate. ASSURANCE.md documents only "array of strings", so a fixture listing two
  required gates passes when one fires.
- Suggested direction (not patched; P3): refuse an `accountable_role` expectation on a
  result with no findings, refuse `gate_codes` unless the outcome is `fail_gate`, and either
  document any-of semantics or require a subset match with a non-empty list.

**F3. A legal fixture without expectations always passes.** (x08)
Blocked legal text is converted into a met `fail_gate`, and clean legal text passes, so the
fixture asserts nothing. The code comment says "suite requires explicit outcome", but the
code does the opposite. This is pre-existing and deliberately kept by
`test_valid_fixtures_unchanged`, so changing it is a contract decision for the owner.

### P4

**F4. Some malformed fields and deep JSON crash with a traceback instead of
INVALID_PACKET, and one crash takes down the whole suite report.**
- x09, all rc 1 with a traceback and no JSON on stdout:
  - `freshness_days: "abc"` gives ValueError.
  - `freshness_days: null` gives TypeError.
  - `defect: "security"` or `defect: [...]` gives AttributeError.
  - `text: [...]` gives TypeError.
- x10: 200000-deep JSON gives RecursionError, because load_json errors are caught only as
  OSError and ValueError.
- x11: a suite with one such fixture prints no report at all.
- This fails closed (rc 1), but the builder's own CLI helper asserts that no traceback
  occurs. It is pre-existing.

**F5. A suite silently skips some fixture files.** (x13, x14)
`rglob("*.json")` is case-sensitive, so `B.JSON` and `C.Json` holding failing fixtures are
skipped, and the suite reports ok true, 1/1. Symlinked subdirectories are not followed
either (the same on 3.11, 3.12 and 3.13). Suggested direction: match the suffix
case-insensitively, or report the skipped `.json`-like names.

**F6. Gaps in the builder tests.** `mut_kind_precedence` (reading `kind` before
`fixture_kind`) and `mut_exp_keys` (accepting `decision`, the key the handback names as the
motivating false pass) survive tests/test_fixture_runner.py and the full suite. The M01
oracle kills both (c03, c05).

## Harness disclosures

- The first base-engine run used a bare copy of quality_os.py outside the repo layout. It
  failed with IndexError (the engine resolves the repo root via `parents[3]`). That result
  was discarded before use, and base was rerun from a detached base worktree.
- All candidate, mutant and fix runs used separate detached scratch worktrees of base
  02ba9c5 with G01.patch applied. Mutants and the fix were never written to the candidate
  tree, and the mutant tree was restored to the candidate hash (2c55de60...) afterwards.

## Not done

- Python 3.10, which CI lists, was not run: no 3.10 interpreter is on this machine, and none
  was installed. Python 3.9.6 is outside requires-python >=3.10 and was not scored.
- Linux and Windows were not run (macOS arm64 only).
- No published G01 commit exists, so nothing was checked against a commit SHA. See the
  binding above.
- proposed-fix.patch is a proposal only. It was not applied to the candidate or week-grok.
