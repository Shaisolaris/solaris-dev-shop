# Daily integration evidence matrix

Tool: `daily_integration.py` (this folder). Oracle: `daily_integration_oracle.py`, with the naive and
no-op controls in `daily_integration_controls/`. Python 3.9+, standard library and `git` only.

A daily integration goal (G06, G12, G18, G24, G30, G36) stacks review candidates with prerequisite
merge commits and must hand root one matrix that says, for one exact HEAD and tree:

- which candidate commits are really in HEAD, and which named ones are not;
- that every file a candidate changed still has that candidate's blob (the newest candidate's when
  one builds on another), so a bad conflict resolution or a lost file is a `DRIFT` finding, and two
  unrelated candidates that disagree about a file are an `OVERLAP` unless the plan explains it;
- that the integration's own files stay inside its writable globs, and that the tree is clean
  before and after the runs (HEAD alone cannot identify uncommitted work);
- each candidate's acceptance as root recorded it: `ACCEPTED` only at the exact commit. A repaired
  candidate that descends from the accepted one is `ACCEPTED_OTHER_REVISION`: acceptance does not
  carry to a changed candidate. The tool never accepts anything;
- outside contributions with no commit in this repository (for example a design reply) bound to
  their acceptance record, and when supplied, to the reply readback and validation manifest hashes;
- the exit codes of each candidate's own tests and oracle, the plan's cross-goal checks, and with
  `--run all` the gates CI runs.

`INTEGRATED` (exit 0) means no finding. Anything else is `NOT_INTEGRATED` (exit 1) with the findings
listed, or `INVALID_INPUT` (exit 2, nothing written, a previous `--out` report kept). A gate the
interpreter cannot run (PyYAML missing for the metadata gate) is a finding unless the caller skips it
by name, and a skipped gate is listed under `not_run`.

Cross-goal checks belong to the integration goal (`examples/capabilities/<goal>/cross_checks.py`).
They compare two candidates' real behaviour on the same input. A cross-goal defect is reported as a
finding against the candidate that owns it; the integration goal does not edit another goal's files.

```bash
T=employees/quality-security/assurance/daily_integration.py
python3 $T check --plan examples/capabilities/G18/plan.json --run tests \
  --acceptance ACCEPTANCE-A.json --acceptance ACCEPTANCE-B.json --acceptance ACCEPTANCE-PR.json
python3 employees/quality-security/assurance/daily_integration_oracle.py -- python3 $T
```
