# Release-candidate inventory (release_candidate.py)

Assembles one honest picture of a proposed release from the programme's own records and the repository's
release metadata. It decides nothing: acceptance comes from root's acceptance records, and only root applies
version metadata, tags and releases after the final gates.

```bash
T=employees/quality-security/assurance/release_candidate.py
python3 $T inventory . --queue WORK-QUEUE.json --acceptance ACCEPTANCE-*.json --candidates candidate-index.json --git
```

## Dispositions

| Disposition | Meaning |
|---|---|
| accepted | an acceptance record names the current candidate commit (or accepted work outside this repository) |
| acceptance_stale | accepted at one commit, but the candidate index now names another; the reviewed revision is not the one that would ship. With `--git`, says whether the candidate descends from it |
| candidate_only | a candidate exists, no acceptance record |
| excluded | the queue marks the goal excluded or rejected; it never appears in `included_if_released` |
| missing | neither a candidate nor an acceptance record |

## Metadata reconciliation

pyproject `version` must equal the top CHANGELOG heading, and the skill count in the pyproject description
must equal the number of `employees/*/*/SKILL.md` files and the entries in `control-plane/skills.json`. A
mismatch is a reason, never fixed here.

## Gate

The computed gate is READY only when every selected goal is accepted or excluded, every required final goal
is accepted, no two acceptance records conflict, the metadata agrees, and the queue's `release_gate` names a
`candidate_commit`, `checks_revision` and `reviewed_revision`. Otherwise NOT_READY with every reason (exit 1).
`applied` is always false. The proposed version is one minor step from the current version and is not
written anywhere. Steps the tool cannot do are listed under `blocked_on_root_or_owner`.

## Limits

It reads files and, with `--git`, local commit ancestry. It does not run CI, verify manifests byte for byte,
check branding hashes or decide acceptance. A READY report is an input to root's final gate, not a release.
