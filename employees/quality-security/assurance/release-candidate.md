# Release-candidate inventory (release_candidate.py)

Assembles one honest picture of a proposed release from the programme's own records and the repository's
release metadata. It decides nothing: acceptance comes from root's acceptance records, and only root applies
version metadata, tags and releases after the final gates.

```bash
T=employees/quality-security/assurance/release_candidate.py
python3 $T inventory . --queue WORK-QUEUE.json --acceptance ACCEPTANCE-*.json --candidates candidate-index.json --git
git ls-remote origin 'refs/heads/review/*' > heads.txt   # then add: --remote-heads heads.txt
```

## Dispositions

| Disposition | Meaning |
|---|---|
| accepted | an acceptance record names the current candidate commit (or accepted work outside this repository) |
| acceptance_stale | accepted at one commit, but the candidate index now names another; the reviewed revision is not the one that would ship. With `--git`, says whether the candidate descends from it |
| candidate_only | a candidate exists, no acceptance record |
| excluded | the queue marks the goal excluded or rejected; it never appears in `included_if_released` |
| missing | neither a candidate nor an acceptance record |
| not_selected | the queue sets `selected_for_week: false` and the goal is not a required final goal; listed, but it does not block the gate and is not included unless accepted |

## Remote heads (`--remote-heads`, with `--git`)

The candidate index can fall behind the review branches. Give a `git ls-remote` listing and every branch whose
name holds the goal id as a word (`review/grok-g19-...`) is compared with the goal's accepted commit and index
candidate. A head that descends from either and differs from both is a revision nobody indexed: an accepted
goal becomes `acceptance_stale` (with `newer_remote_heads`), and "candidate index is stale" is a gate reason.
A listed head that is not in REPO cannot be checked and is a gate reason too; fetch first. Heads on another
history (an older validation branch, for example) are ignored. The tool never fetches.

## Metadata reconciliation

pyproject `version` must equal the top CHANGELOG heading, and the skill count in the pyproject description
must equal the number of `employees/*/*/SKILL.md` files and the entries in `control-plane/skills.json`. A
mismatch is a reason, never fixed here.

## Gate

The computed gate is READY only when every selected goal (every goal the queue does not mark
`selected_for_week: false`) is accepted or excluded, no remote head is newer than the index (with
`--remote-heads`), every required final goal
is accepted, no two acceptance records conflict, the metadata agrees, and the queue's `release_gate` names a
`candidate_commit`, `checks_revision` and `reviewed_revision`. Otherwise NOT_READY with every reason (exit 1).
`applied` is always false. The proposed version is one minor step from the current version and is not
written anywhere. Steps the tool cannot do are listed under `blocked_on_root_or_owner`.

## Limits

It reads files and, with `--git`, local commit ancestry. It does not run CI, verify manifests byte for byte,
check branding hashes or decide acceptance. A READY report is an input to root's final gate, not a release.

Root gate correction: candidate_commit, checks_revision and reviewed_revision must each be a complete lowercase 40-hex commit and must agree. Mere presence of three unrelated values cannot make the inventory READY. These are root assertions; the tool does not authenticate hosted CI or independently perform review. Root still checks actual CI, manifests and working-tree state.
