# Quality OS - product / design / QA / security / legal assurance

Status: L4-oriented evidence and gate contract  
Roadmap: `skill-solaris-product-quality-hardening`  
Engine: `quality_os.py` (this directory)  
Engine version: `1.0.2`

Tests: `tests/test_assurance_packets.py`, `tests/test_closure_hardening.py`
Upstream standard (2026-07 wave skill-lkl): `../QUALITY-SECURITY-STANDARD.md`

## Purpose

Quality is a **state machine with gates and evidence**, not a council chat.
Product and assurance capabilities produce typed requirements, design, test,
security, privacy, accessibility, compliance, and release evidence with real
blocking thresholds and human authority boundaries.

## Risk classification

| Level | When |
|-------|------|
| informational | Internal note, no user/data impact |
| standard | Project-local change, no sensitive data |
| elevated | User-facing **or** PII **or** multi-package blast |
| high | External users, financial/health/legal data, mutations, regulatory |
| critical | Production incident, S0/S1 security, irreversible external effect |

Computed by `classify_risk()` from blast radius, data sensitivity, user-facing,
external mutation, regulatory flags, and release-candidate status.

## Specialist gates (accountable roles)

| Defect kind | Accountable gate | Independent verifier |
|-------------|------------------|----------------------|
| functional | qa-engineer | code-reviewer |
| ux | ui-ux-designer | qa-engineer |
| accessibility | qa-engineer | ui-ux-designer |
| security | security-auditor | code-reviewer |
| privacy | compliance-auditor | security-auditor |
| legal_risk | legal-advisor | compliance-auditor |
| compliance | compliance-auditor | legal-advisor |
| requirements | product-manager | business-analyst |
| design | ui-ux-designer | qa-engineer |
| performance | performance-engineer | code-reviewer |
| release | delivery-lead | qa-engineer |

Gates become mandatory when deliverable risk meets `GATE_THRESHOLDS` for that kind.

## Evidence schema (minimum)

Every completed gate must attach an evidence object:

```json
{
  "gate": "security",
  "role": "security-auditor",
  "summary": "STRIDE on auth change; no critical findings open",
  "artifacts": ["reports/threat-model.md", "fixtures/scan-summary.json"],
  "blocking_open": 0,
  "timestamp": "2026-07-23T00:00:00+00:00"
}
```

Release packets must list `completed_gates[]` and `evidence{kind: …}` for each
required specialist dimension.

Version 1.0.1 enforces this documented shape: exact gate/key agreement, nonblank
role and summary, and a nonempty array of nonblank artifact references.
`blocking_open`, when supplied, must be a nonnegative integer; a positive value
blocks. Malformed packets return `INVALID_PACKET`; malformed gate receipts return
`INVALID_GATE_EVIDENCE`. Missing evidence retains `MISSING_GATE_EVIDENCE`.
Legacy summary-only, string, or artifact-only receipts must be corrected.

A `pass` is a check of declared receipts against declared risk and dimensions.
It does **not** authenticate the role, inspect referenced artifacts, prove tests
ran, or authorize an external action. A receipt is tied to the current revision
only when the packet names its `subject` (see Revision binding below).
The host must assess actual risk, execute the specialist work, inspect its output,
and obtain the owner's approval where required. No files, URLs or commands named
in a receipt are opened or executed by this validator. Omitted blockers and false
risk declarations cannot be detected from syntax alone.

`run` and `suite` are fixture commands: `expectations.outcome="fail_gate"` can
make a negative fixture succeed when the expected gate fires. That suite success
is test evidence, never permission to release. Call `evaluate_artifact_packet`
for the underlying packet decision; it does not apply fixture expectations.

## Revision binding (changed source invalidates a prior pass)

A packet may name the artifact it is about, and each receipt what its reviewer examined:

```json
{
  "subject": {"revision": "9b3e7d1c5a2f...", "digests": {"src/auth.py": "<sha256>", "ui/index.html": "<sha256>"}},
  "evidence": {"security": {"gate": "security", "role": "security-auditor", "summary": "...",
                            "artifacts": ["reports/sec.md"],
                            "reviewed": {"revision": "4f1c2a9e0b7d...", "digests": {"src/auth.py": "<sha256>"}}}}
}
```

A revision is a lowercase git commit id (7-64 hex; an abbreviated id of 7+ characters matches the full id)
or `sha256:<64 hex>`. Digests map relative paths to sha256. With a `subject`, each receipt is:

| State | When | Result |
|-------|------|--------|
| current | `reviewed.revision` is the subject revision and no listed digest differs | passes |
| carried_forward | another revision, but every file in `reviewed.digests` is unchanged in the subject | passes, noted |
| stale | a listed file's digest differs (even under the same revision label), or the revisions differ without digest cover | `STALE_GATE_EVIDENCE` |
| unbound | no `reviewed`, or nothing comparable with the subject | `UNBOUND_GATE_EVIDENCE` |

`evidence.revision_binding.gates` gives each gate's state, both revisions, the changed files (first 20) and
an `action` naming the gate to re-run and the revision to run it on. Without a `subject`, receipts that name
different revisions are `REVISION_CONFLICT`; packets with no binding at all behave exactly as before.
A malformed `subject` is `INVALID_PACKET`; a malformed `reviewed` is `INVALID_GATE_EVIDENCE` (bounded
messages; at most 10000 paths). Evaluation still opens nothing: digests are declared values.

`quality_os.py digest ROOT PATH... [--revision REV]` prints the sha256 of actual files (a folder is walked in
sorted order) as a binding object for `subject` or `reviewed`. It refuses with exit 2 a path that leaves
ROOT, any symlink, a non-regular or oversized file (64 MiB), and an empty result. It reads; it runs nothing.

Findings: `can_close_finding` / `close_finding` take `subject_revision` and `verified_revision`. With a
subject, a non-waived closure needs `verified_revision` (else `MISSING_VERIFIED_REVISION`) matching the
subject (else `STALE_CLOSURE_EVIDENCE`; a malformed one is `INVALID_REVISION`); the closure records
`closed_at_revision`. `closure_is_current(finding, revision)` reports `STALE_CLOSURE` (verified at another
revision; conservative, any other revision counts), `UNBOUND_CLOSURE` (closed without a revision and
without a waiver), or `NOT_CLOSED`. A closure that records a `waiver_id` is waiver-governed: `closure_is_current` returns current at any revision, and `reopen_finding` refuses with `WAIVER_GOVERNS`.
`reopen_finding` returns a non-waiver closed finding to open with a reason of 12+ characters
(`REOPEN_REASON_REQUIRED`), clearing the closer and revision and keeping the earlier evidence plus a reopen
note, so closing again needs new independent evidence. A valid waiver closes a waived finding at any
revision until it expires; expiry and revocation stay with `validate_waiver`.

What this cannot do: tell whether a reviewer really examined the named revision (receipts stay
declarations), or run git; callers supply revisions and digests from the artifact they release.

## Findings → orders

- Findings carry severity (S0-S4/info), defect kind, evidence, accountable role,
  verifier role, and closure criteria.
- `finding_to_order` / `convert_findings_to_orders` produce deduplicated orders
  (key = defect_kind + normalized title; highest severity wins).
- Orders are owned by the accountable role; closure still requires independent
  verification for blocking severities (S0-S2).

## Self-approval ban (hard control)

**A role cannot close its own unresolved blocking finding.**

- Accountable role self-close → `SELF_APPROVAL_FORBIDDEN`
- Missing independent evidence → `MISSING_CLOSURE_EVIDENCE`
- Wrong verifier → `INDEPENDENT_VERIFIER_REQUIRED`
- Allowed closers for blocking findings: declared `verifier_role`,
  `human-owner`, or `chief-of-staff` **with** independent evidence.

Version 1.0.2 fails closed on closure input (`can_close_finding`,
`close_finding`):

- Unknown severity (for example `s1` or `critical`), unknown status, blank
  `finding_id`/`accountable_role`, or non-array evidence → `INVALID_FINDING`.
  An unknown severity is no longer silently treated as non-blocking.
- Blank closer → `INVALID_CLOSER_ROLE`. A blank or self-equal `verifier_role`
  no longer admits a closer; only `human-owner`/`chief-of-staff` remain.
- Closure evidence must be an array of nonblank strings; a bare string,
  object, `None` or blank item → `INVALID_CLOSURE_EVIDENCE` (for every
  severity). For blocking findings an empty array →
  `MISSING_CLOSURE_EVIDENCE`, and evidence that only repeats the finding's
  existing evidence → `NON_INDEPENDENT_CLOSURE_EVIDENCE`.
- These closer and evidence shape checks run before the status branch, so they
  also apply to `waived` findings. A valid waived closure needs: a nonblank
  string closer (any role, including the accountable role, because the
  human-authorised waiver is the closure basis), evidence that is a list or
  tuple of nonblank strings (an empty list is allowed), and a waiver that
  passes `validate_waiver`. No extra fix evidence is required for a waiver.
- Severity and status are type checked as strings before any lookup, so a
  list or dict value returns `INVALID_FINDING` instead of raising. Closure
  fixtures whose finding fields (other than `evidence`) are not strings return
  `INVALID_PACKET`.
- Evidence is declared text. It is never opened, fetched or executed, and a
  pass does not prove the verification actually ran.
- Optional `as_of` (aware `datetime`) fixes the clock for waiver expiry.

## Waivers and dissent

Waivers require:

1. Written justification (≥12 chars)
2. `human_authority: true` (strictly the boolean `true`)
3. Approver **≠** accountable role and approver **≠** requester
4. Explicit `expires_at` that parses as ISO 8601 and is in the future

`propose_waiver` and `validate_waiver` enforce these at creation and at use.
A `waived` finding closes only through a waiver that passes `validate_waiver`
at closure time; otherwise the codes are `WAIVER_REQUIRED`, `INVALID_WAIVER`,
`WAIVER_FINDING_MISMATCH`, `WAIVER_NOT_ACTIVE`, `HUMAN_AUTHORITY_REQUIRED`,
`WAIVER_JUSTIFICATION_REQUIRED`, `WAIVER_SELF_APPROVAL_FORBIDDEN`,
`WAIVER_EXPIRY_INVALID` or `WAIVER_EXPIRED`. Naive timestamps are read as UTC.
`human_authority` and role names are declared values: the engine cannot
authenticate who approved, so the host must confirm owner authority.
Closure fixtures (`run` with `fixture_kind: closure`) with a missing or
malformed `finding`/`waiver` return `INVALID_PACKET` instead of crashing.

Council dissent: any REFUTED/DISSENT/HOLD vote → outcome `HOLD`. PASS only when
there is at least one CONFIRMED and zero dissent.

## Legal and compliance boundaries

- Outputs are **informational only** - never binding legal advice.
- `legal_file` and other high-stakes actions → human confirmation; never auto-allow.
- Binding patterns (`I am your attorney`, `file this lawsuit`, …) →
  `LEGAL_BINDING_PROHIBITED`.
- Legal discussion requires disclaimer markers.
- Sources need dates; default max age **365 days** or source-specific
  `max_age_days`. Stale → `LEGAL_SOURCE_STALE` + human review trigger.

## Commands

```bash
python3 employees/quality-security/assurance/quality_os.py self-test
python3 employees/quality-security/assurance/quality_os.py run packet.json
python3 employees/quality-security/assurance/quality_os.py audit
python3 employees/quality-security/assurance/quality_os.py route security
python3 employees/quality-security/assurance/quality_os.py digest PROJECT src ui --revision COMMIT
python3 -m unittest discover -s tests -v
```

## Hard controls

- No production deployment from this module.
- No credentials, tokens, private health/finance/personal content in fixtures.
- No self-approval of blocking findings.
- No legal filing or binding advice.
- Synthetic fixtures only.
