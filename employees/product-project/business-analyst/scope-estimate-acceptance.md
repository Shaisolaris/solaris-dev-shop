# Scope, estimate and delivery acceptance (G31)

Tool: `scope_acceptance.py` (stdlib, Python 3.9+, local files only). It reads a scope package and reports
whether a proposal is ready for the owner to send, and later whether delivery evidence meets every
acceptance criterion. It drafts nothing for a customer and signs nothing; the owner decides.

```bash
python3 scope_acceptance.py check PACKAGE [--json] [--out FILE]      # 0 ready, 1 blocked, 2 invalid
python3 scope_acceptance.py accept PACKAGE DELIVERY [--json] [--out FILE]   # 0 accepted, 1 not accepted, 2 invalid
python3 scope_acceptance.py verify RESULT PACKAGE [DELIVERY]          # 0 identical, 1 different, 2 invalid
```

## Package (schema `solaris.scope-package/1`)

- `engagement`: id, customer, owner, as_of, currency.
- `inputs`: what the customer actually said or wrote (id, text, source, date). `assumptions`: what we
  assume (same fields plus `confirmed` true or false). Nothing may be dated after `as_of`.
- `requirements`: id, text, `traces` (input or assumption ids), `depends_on`, `capability`,
  `estimate_hours` {low, likely, high} as decimal strings, `acceptance` [{id, criterion, measure}],
  optional `optional: true`, optional `conflicts_with` (ids of other requirements it contradicts).
- `capabilities`: id, name, `demo` {path, sha256} pointing to a JSON run record inside the package folder
  with `capability`, `exit_code`, `result`, `ran_at`.
- `ambiguities`: id, `about` (requirement or criterion ids), question, escalated_to, status open or
  resolved, and for resolved a `resolution` {text, source, date}.
- `rate`: per_hour, source, date. `capacity` (needed for a date commitment): a G17 resource decision
  `package` and stored `result`, the `option` and `milestone` to rely on.
- `proposal`: `scope` (requirement ids), `exclusions`, `estimate` (range: hours {low, likely, high} and price
  {low, high}; fixed: hours and price), `commitments` [{id, kind scope|estimate|date|feature|sla|other,
  text, refs, value for dates}].

## Findings (any finding blocks; exit 1)

| code | rule |
|---|---|
| invented_commitment | a commitment with no refs or unknown refs; a scope, feature or sla commitment naming no in-scope requirement |
| out_of_scope_commitment | a commitment naming a requirement that is not in scope |
| untraced_requirement | an in-scope requirement with no known input or assumption |
| missing_dependency | an in-scope requirement depends on one that is out of scope |
| silent_exclusion | a non-optional requirement is neither in scope nor in `exclusions` |
| undemonstrated_capability | no capability, no demo, demo file missing or changed (sha256), record for another capability, run not passing (exit_code 0 and result pass), or run dated after as_of |
| no_acceptance_criteria | an in-scope requirement with nothing that defines done |
| unescalated_ambiguity | vague wording (listed in the tool's `VAGUE`, such as real-time, seamless, scalable, fast, asap, tbd) in a requirement or criterion, or a criterion with no measure, with no ambiguity entry about it |
| open_ambiguity | an escalated ambiguity still open; also listed under `escalations` with its owner |
| unresolved_conflict | two in-scope requirements contradict each other, or one contradicts an input or assumption it traces, and no ambiguity entry about every requirement involved exists (see Contradictions) |
| conflicting_commitment | a commitment's own text takes one side of an opposite-term family that an in-scope requirement, criterion or traced input, or another commitment's text, takes the other side of, with no resolved ambiguity about that commitment and that requirement or other commitment |
| commitment_on_blocked_requirement | a commitment resting on a requirement with an open, unescalated, untraced, undemonstrated or unresolved-conflict finding |
| estimate_mismatch | stated hours differ from the sum of in-scope estimates, or price differs from hours x rate rounded half up to cents |
| unsupported_fixed_estimate | a fixed estimate below the high sum, with an open ambiguity in scope, or resting on an unconfirmed assumption (and any estimate commitment to it) |
| unsupported_date | no capacity evidence, the stored G17 result differs from a rerun, the option is not feasible in the G17 downside, or its downside finish (calendar start + 7 x finish week - 1 day) is after the committed date |

## Contradictions (owner-resolution boundary)

The tool does not judge whether free text is coherent. It finds two bounded kinds of contradiction:

- declared: a requirement's `conflicts_with` names another in-scope requirement;
- opposite terms: one text uses a term from one side of a documented family and another text of the same
  proposal uses the other side. Texts are in-scope requirement texts, their acceptance criteria and measures,
  the inputs and assumptions they trace, and commitment texts. Families (`OPPOSITES` in the tool):
  availability (24/7, around the clock, any hour ... vs office hours, business hours, closed outside ...),
  connectivity (offline vs online only), hosting (on-premises vs SaaS, cloud only), sign-in (no login,
  anonymous vs login required) and retention (never stored, deleted immediately vs kept for, retained for).
  Terms match whole words, case-insensitively.

A contradiction never becomes a plain commitment. It needs an ambiguity entry whose `about` lists every
requirement involved, escalated to the person who decides. With no entry it is `unresolved_conflict`
on each requirement, and commitments resting on them are blocked. With an open entry it is `open_ambiguity`
and listed under `escalations` with its owner. With a resolved entry the proposal may be ready, but
each commitment resting on those requirements, or on an input one of them traces, lists the ambiguity under `qualified_by`, so the proposal
states the owner's resolution. `conflicts` in the JSON lists every contradiction found, its evidence,
status, ambiguity ids and owner.

Every report carries `coherence`: what was checked, and that general consistency of free text was not.
The owner confirms that before sending. Contradictions phrased outside the families and not declared are
not found.

Unconfirmed assumptions are allowed in a range estimate; they are reported under `conditions` and per
commitment as `conditional_on`, so the proposal can state them.

## Acceptance (schema `solaris.scope-delivery/1`)

`accept` first runs `check`; a blocked scope cannot be accepted (`scope_not_ready`). Each result names a
criterion, outcome pass or fail, a date not after the delivery `as_of`, and evidence {path, sha256}. A
requirement is accepted only when every criterion has a passing result whose evidence file still matches
(`missing_evidence`, `evidence_mismatch`, `criterion_failed`). Unknown or repeated criteria are invalid.

## Recovery

`--out` writes through a temporary file and an atomic rename, refuses to overwrite the package or delivery
file, and a failed or invalid run leaves an earlier result untouched. `verify` reruns the package and names
any field that differs, so an edited or truncated result is detected.
