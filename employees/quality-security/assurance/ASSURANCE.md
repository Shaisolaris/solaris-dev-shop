# Quality OS - product / design / QA / security / legal assurance

Status: L4-oriented evidence and gate contract  
Roadmap: `skill-solaris-product-quality-hardening`  
Engine: `quality_os.py` (this directory)  
Engine version: `1.0.1`

Tests: `tests/test_assurance_packets.py`
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
ran, bind a receipt to the current revision, or authorize an external action.
The host must assess actual risk, execute the specialist work, inspect its output,
and obtain the owner's approval where required. No files, URLs or commands named
in a receipt are opened or executed by this validator. Omitted blockers and false
risk declarations cannot be detected from syntax alone.

`run` and `suite` are fixture commands: `expectations.outcome="fail_gate"` can
make a negative fixture succeed when the expected gate fires. That suite success
is test evidence, never permission to release. Call `evaluate_artifact_packet`
for the underlying packet decision; it does not apply fixture expectations.

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

## Waivers and dissent

Waivers require:

1. Written justification (≥12 chars)
2. `human_authority: true`
3. Approver **≠** accountable role
4. Explicit `expires_at`

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
python3 -m unittest discover -s tests -v
```

## Hard controls

- No production deployment from this module.
- No credentials, tokens, private health/finance/personal content in fixtures.
- No self-approval of blocking findings.
- No legal filing or binding advice.
- Synthetic fixtures only.
