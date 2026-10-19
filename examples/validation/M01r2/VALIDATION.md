# M01 r2: Grok self-validation of the G01 repair (fixture runner fails closed)

Grok self-validation. This is not independent review: the same agent family wrote the M01 r1
findings this repair answers. Treat every verdict here as input for an independent reviewer.

**Verdict: PASS with residuals.** F1 to F6 from M01 r1 are fixed on their reproductions, with no
regression found. Two new residuals turned up: one P3 and one P4, so no P1 or P2. One behaviour change
(F3) is a contract decision for the owner.

## Candidate binding

- Branch `review/grok-g01-fixture-runner`, head deb06f66201f1752a659214a2e1c915a4a7991af
  ("G01 repair r1: M01 findings F1-F6"). Its parent 45e779b is the delivered G01.
- `raw/binding-verify.txt`:
  - The 45e779b diff against main 02ba9c5 is byte-identical to G01.patch (sha256 85a506e6...).
  - Its per-file blobs match the M01 r1 binding.
  - G01-r1.patch equals the 45e779b..deb06f6 diff.
  - MANIFEST.sha256 at deb06f6 checks 4/4, and its file set equals the 02ba9c5..deb06f6 diff set.
- Repair scope: 45e779b..deb06f6 touches ASSURANCE.md, quality_os.py (+133/-16) and
  tests/test_fixture_runner.py (+156, no lines removed).

## Method

- **r1 oracle** (`oracle/m01_oracle.py`, unchanged from r1): 12 core and 14 gap checks, run via the CLI
  only.
  - Run on the repair under 3.11.16, 3.12.14 and 3.13.15.
  - Run on the delivered G01 (45e779b) under 3.12.14 as the comparison.
- **New r2 probes** (`oracle/m01r2_adversarial.py`, y01 to y09) target the repair itself:
  - kind-key synonyms that score below the 0.8 near-miss ratio;
  - legal fields on an unwrapped packet;
  - an unreadable subfolder;
  - a symlinked fixture file;
  - a bare planted defect with a misspelled field;
  - controls for note keys and for a negative packet fixture.

  The probes ran on all three interpreters and on 45e779b.
- **Builder suite:** `python -m unittest discover -s tests` on 3.11.16, 3.12.14 and 3.13.15.
- **Fresh caller** (`oracle/m01r2_fresh_caller.sh`, 3.13.15):
  - Environment: env -i, a new HOME, a `python3` shim and a socket-blocking sitecustomize.
  - Commands: transcribed by hand from ASSURANCE.md "## Commands".
  - Suite dirs: two. One holds the r1 x01 fixture and one holds the r2 y01 fixture, each next to a valid
    negative packet.
- **Teeth** (`oracle/make_mutants_r2.py`, `oracle/run_teeth_r2.sh`, 3.12.14):
  - Mutants: 32 exact single-occurrence mutants. 13 are the r1 mutants re-anchored on deb06f6, and 19 are
    new, one per repair guard. The generator asserts count == 1.
  - Controls: the candidate and a no-op control.
  - Scorers: the M01 oracle (core and gaps), tests/test_fixture_runner.py and the full builder suite.
  - Setup: everything ran in a detached scratch worktree, and the hash was restored after each mutant.

## Results

| | repair deb06f6 | delivered 45e779b |
|---|---|---|
| r1 core c01 to c12 | 12/12 on 3.11.16, 3.12.14, 3.13.15 | 12/12 (3.12.14) |
| r1 gaps open x01 to x13 | 0/13 on each | 13/13 |
| r2 probes holding (y01 to y07) | 4/7 on each, identical across interpreters | 3/7 |
| builder suite | 99/99 OK on each | not rerun (91 in r1) |

Fresh caller (`results/fresh-caller-r2-3.13.15.txt`):
- All documented commands exit 0, and the builder tests pass.
- The offline guard blocks a socket connect.
- The x01 suite dir now reports ok false, 1/2 (r1: ok true, 2/2).
- The y01 suite dir reports ok true, 2/2. This is S1 below, reproduced through the documented command.

## r1 findings rechecked

| r1 | status at deb06f6 | evidence |
|---|---|---|
| F1 (P2) misspelled contract key gives a false pass | fixed on all r1 variants (x01 to x04, x12) | gaps closed; fresh-caller x01 suite now fails; y04 control |
| F2 (P3) vacuous expectations | fixed: role with no findings gives GATE_MISROUTE; gate_codes require fail_gate, must be non-empty, and every code must fire | x05 to x07 |
| F3 (P3) legal fixture without expectations always passes | fixed by a **behaviour change** (see "Owner decision") | x08; builder test_f3 |
| F4 (P4) tracebacks on malformed fields and deep JSON | fixed: type checks, and RecursionError or any Exception becomes INVALID_PACKET | x09 to x11 |
| F5 (P4) suite skips .JSON and symlinked dirs | fixed: case-insensitive suffix; a symlinked dir is a failing entry | x13, x14 |
| F6 builder test gaps | fixed: mut_kind_precedence and mut_exp_keys are now killed by tests/test_fixture_runner.py | teeth table |

## Owner decision: F3 behaviour change

A legal fixture without `expectations` is now read as `outcome: "fail_gate"`. Before the repair it could
never fail. Now clean legal text with no expectations **fails** the suite (EXPECTED_GATE_NOT_FIRED), and a
fixture must say `{"outcome": "pass"}` to assert that text is allowed.

The change is documented in ASSURANCE.md and pinned by test_f3. It changes the contract for any existing
legal fixture that relied on the old reading. The repo ships no assurance fixtures, so nothing in-tree
breaks. I flagged it in r1 as a contract decision, and accepting it is the owner's call, not mine.

## Findings (new in r2)

### P3

**S1. A legal fixture whose kind key is a synonym, or missing, is evaluated as a passing packet.**
(y01, y03)

- y01: `{"fixture_type": "legal", "text": "I am your attorney; file this lawsuit now."}` gives rc 0, ok
  true, `gate_codes: []`.
- y03: the same text with no kind key gives the same result.
- How it happens:
  - `fixture_type` scores about 0.75 against `fixture_kind`, under the 0.8 near-miss ratio, so the fixture
    falls through to the unwrapped-packet path.
  - That path refuses only closure and defect fields (NON_PACKET_FIXTURE_KEYS), not the legal fields
    `text`, `requested_actions`, `sources` and `freshness_days`.
  - The packet engine ignores the unknown key `text`, and the fixture passes.
- Through the documented `suite` command, a dir holding y01 and a valid negative packet reports ok true,
  2/2.
- y02 holds, because `legal_text` is a real packet field and still triggers the legal gate.
- Why P3 and not P2:
  - `fixture_type` is not a near-miss of a contract key.
  - ASSURANCE.md says unknown packet keys are still ignored.
- Why it is still a finding: the code comment says a misspelled field of a "closure or legal fixture must
  not turn the fixture into a different, passing fixture", and closure fields already get that protection.
- Suggested direction (not a proposed fix, and not applied): add `text`, `requested_actions`, `sources`
  and `freshness_days` to NON_PACKET_FIXTURE_KEYS.
  - `raw/direction-check-y01-y07.diff`, `raw/direction-check-y01-y07.txt`: in the scratch tree, y01 and y03
    then hold.
  - The builder suite stays OK, r1 core stays 12/12 and the gaps stay 0/14.

### P4

**S2. A suite silently skips an unreadable subfolder.** (y07)

- A subfolder with mode 000 that holds a failing fixture leaves the suite at rc 0, ok true, 1/1, with no
  error.
- Cause: `os.walk(root)` has no `onerror`, so the folder disappears from the count. That is the same class
  as r1 F5, which the repair fixed for case and symlinked dirs.
- Suggested direction: pass `onerror` and record each error as a failing INVALID_PACKET entry. The same
  scratch check closes y07, with suite OK and core 12/12.

### Observations (not findings)

- y08: a symlinked fixture *file* that points outside the suite dir is evaluated and counted. ASSURANCE.md
  only covers symlinked directories.
- y09: a bare planted defect with a misspelled `severty` fails (rc 1), so it fails closed.
- `accountable_role` is compared with `findings[0]` only. Multi-finding role checks were not probed.

## Teeth (`results/teeth-r2-3.12.14.tsv`)

| scorer | killed (31 non-equivalent) | notes |
|---|---|---|
| builder tests/test_fixture_runner.py | 31/31 | full suite: same 31 |
| M01 oracle core (r1 contract) | 8/31 | kills only r1-guard mutants: kind precedence, unknown expectation, exp keys, outcome, role, role strip, empty suite, ok/error |
| M01 oracle gap checks (gap reopened) | 8/31 | f1_near_off, f1_norm_only, f1_ratio_095, f1_extra_off, f2_gate_any, f2_gate_nonempty_off, f2_gate_outcome_off, f5_case_suffix |
| M01 oracle core or gaps | 16/31 | |
| union of all scorers | 31/31 | |

- **Control:** f4_outer_recursion_off_EQUIV is an equivalent control. The generic `except Exception` still
  turns RecursionError into INVALID_PACKET. It survives every scorer, as expected.
- **Masking in my oracle.** It scores only ok and rc, so layered guards mask each other:
  - f2_role_vacuous: with no findings, the role branch indexes `findings[0]`, and the IndexError becomes
    INVALID_PACKET through the generic catch.
  - f1_dup_off: the last duplicate value gives a packet carrying closure fields, which the stray check
    refuses.
  - The f4 type-check mutants are masked by the generic catch.

  The builder tests check gate codes and messages, and they kill all of them.

## Harness disclosures

- The first oracle timing call passed a relative engine path. The oracle runs in a temp cwd, so it scored
  0/12. That result was discarded, and every scored run used an absolute path.
- The teeth TSV was first written with literal `\t` separators. It was converted to tabs afterwards, and
  no values changed.
- week-grok, read-only (`raw/weekgrok-before.txt` 18:53:59 PT, `raw/weekgrok-after.txt` 19:06:56 PT):
  - Branch, HEAD 02ba9c5 and the index hash are unchanged.
  - The status went from 69 to 70 lines. The added line is the untracked
    `employees/specialized/wordpress-master/wp_trace_diag.py` (mtime 19:03:56 PT). That is the builder's own
    concurrent work, not mine: none of my commands write to that tree.

## Not done

- Python 3.10, which CI lists, is not installed here. 3.9 is outside requires-python. Linux and Windows
  were not run (macOS arm64 only).
- Teeth ran on 3.12.14 only. The interpreter matrix covers the suite, oracle and probes.
- No proposed-fix patch: there is no P1 or P2. The S1 and S2 directions are scratch checks, not patches,
  and were not applied to the candidate or week-grok.
