# G41 release candidate and metadata reconciliation (partial)

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

## Partial by design

This build is honest about the present: the cohort is not accepted, so a live run reports NOT_READY. It
proposes 0.62 from 0.61 and applies nothing. Version apply, catalog or roster changes, multi-OS CI, branding
check, PR replies, tag and release are root's (or the owner's) and are listed as blocked. POSIX, Python 3.9+.
