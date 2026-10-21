# G41 release candidate and metadata reconciliation

Tool: `employees/quality-security/assurance/release_candidate.py` (rules: `release-candidate.md` beside it).
It inventories every selected goal against root's acceptance records and the candidate index, reconciles
release metadata (version, CHANGELOG, skill counts) and computes the release gate without changing anything.

## Run it

```bash
python3 examples/capabilities/G41/inventory_oracle.py                                                  # ACCEPTED 10/10
python3 examples/capabilities/G41/inventory_oracle.py --tool examples/capabilities/G41/naive_inventory.py  # REJECTED 5/10
python3 examples/capabilities/G41/inventory_oracle.py --tool examples/capabilities/G41/noop_inventory.py   # REJECTED 0/10
```

Checks: o1 clean control READY (exit 0), o2 nothing accepted NOT_READY, o3 candidate moved after acceptance
(acceptance_stale), o4 version and CHANGELOG disagree, o5 skill counts disagree, o6 a rejected goal stays out,
o7 nothing written and the proposal not applied, o8 gate revisions unset, o9 conflicting acceptance and invalid
input (exit 2), o10 `--git` ancestry on a real local repository. `naive_inventory.py` trusts the queue status
and skips metadata; `noop_inventory.py` answers READY.

## Read-only release gate

An unaccepted or stale cohort reports NOT_READY. READY means the supplied acceptance, candidate index and
metadata agree; the tool does not authenticate the supplied approvals or run hosted CI. Candidate, checks
and review assertions must name the same full 40-hex revision. Root still verifies the actual files, test
results and permissions before publication.

Version proposals are advisory: for example, 0.61 proposes 0.62. Nothing is applied. Version changes,
catalog/roster reconciliation, supported CI, branding checks, tags and publication remain the release
owner's actions. Tested on POSIX, Python 3.9+.
