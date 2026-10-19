# G05 evidence that survives changed source

The assurance engine (`employees/quality-security/assurance/quality_os.py`) can now tie gate receipts and
finding closures to the artifact revision they reviewed. A receipt whose reviewed files changed is stale and
names the gate to re-run; a receipt whose reviewed files are unchanged carries forward to the new revision;
waivers keep their meaning. Packets and closures that name no revision behave as before.
See ASSURANCE.md, "Revision binding".

## Defect on the base (before G05)

`python3 /path/to/defects_on_base.py <repo>` (kept with the handback) showed, on the unmodified engine:
receipts reviewed at one revision passed against another, a malformed revision went unchecked, a closure
could not name the revision it verified, and there was no way to reopen a closed finding.

## Fixtures

`fixtures/project-r1` and `fixtures/project-r2` are two revisions of a tiny synthetic project; only
`src/auth.py` differs, as `fixtures/revisions.json` declares. It also declares which folders each gate
reviewed: security `src`, functional `src` and `ui`, ux `ui` and `docs`. So after r2 the security and
functional receipts must be stale and the ux receipt must carry forward.

```bash
Q=employees/quality-security/assurance/quality_os.py
python3 $Q digest examples/capabilities/G05/fixtures/project-r2 src ui --revision 9b3e7d1c5a2f8e0b6d4c1a9f7e3b5d2c8a0f6e1b
```

## Oracle and controls

```bash
python3 examples/capabilities/G05/binding_oracle.py                                         # 16/16
python3 examples/capabilities/G05/binding_oracle.py --tool examples/capabilities/G05/naive_engine.py  # 6/16
python3 examples/capabilities/G05/binding_oracle.py --tool examples/capabilities/G05/noop_engine.py   # 3/16
```

The oracle checks the fixture declaration against the files on disk (o0), then derives every expectation
from it. `naive_engine.py` is the real engine with binding stripped (the pre-G05 behaviour); `noop_engine.py`
accepts everything. The pre-G05 engine itself scores 4/16. o14 runs a 5000-file subject with 11 gates.

Not run: whether a reviewer really examined the named revision (receipts are declarations) and git itself;
callers supply revisions and digests.
