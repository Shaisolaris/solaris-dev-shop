# Quality, Security, Compliance, and Legal Operating Standard (2026-07)

Status: active for quality-security / legal-compliance / technical-writer gates
Wave: skill-lkl / skill-wave-quality-security-20260724
Synthetic fixtures only. No production scans. Not licensed counsel.

This standard upgrades code review, QA, security, compliance, legal, and technical
writing so outputs are severity-calibrated, evidence-backed, jurisdiction-aware,
and honest about uncertainty. Planted issues must be detected; clean fixtures must
not produce material false positives.

## 1. Severity calibration (HARD)

Use a single ladder across review, QA, and security findings:

| Band | When | Default action |
|------|------|----------------|
| S0 / P0 / Blocker | Active exploit, live secret, irreversible external harm | Block release/merge |
| S1 / P1 / Important | High impact reachable defect, CVSS-class high | Block until fixed or waived by human |
| S2 / P2 | Medium impact or conditional exploit | Track with owner + due date |
| S3 / P3 / Nit | Low impact, polish, style | Optional unless policy says otherwise |
| info | Context only | No block |

Map CVSS when available: >=9.0 -> S0/P0; 7.0-8.9 -> S1/P1; 4.0-6.9 -> S2/P2; <4.0 -> S3/P3.
Live secrets and CISA KEV hits are never severity-downgraded by reachability alone.
Accessibility blockers (e.g. keyboard trap, missing name on critical control) use the
same ladder with impact on affected users stated.

## 2. Evidence required (HARD)

Every finding must include:
- `title` and `severity` (or mapped priority)
- `evidence`: file:line, trace, screenshot path, or scan artifact path
- `reproduction` or smallest-safe proof steps when security/QA class
- `remediation` that is concrete (code or exact steps)
- `confidence`: confirmed | inferred | needs-verification

No evidence => lead, not finding. Do not count leads as findings.
Do not invent CVE IDs, CVSS scores, or tool output.

## 3. False-positive discipline (HARD)

Before promoting a scanner hit or suspicion to a finding:
1. Check reachability / taint / framework mitigations (ORM params, auto-escape, CSP).
2. Suppress with a documented reason when framework-handled or unreachable.
3. Prefer one corroborated finding over duplicate tool noise.
4. Clean fixtures (no planted defect) must not yield material S0-S2 findings.

Material false positive = S0-S2 filed without evidence of exploitability or with
contradicted reachability.

## 4. Planted-issue detection

Synthetic planted fixtures exist under `fixtures/evaluation/quality-security/**`.
When a planted defect is in scope, the capability must:
- detect it
- assign correct severity band
- attach evidence path or file:line
- avoid inventing extra high-severity findings without evidence

Confusion-matrix orientation: true positives preferred; false positives on clean
fixtures are gate failures for this wave.

## 5. Accessibility (QA / review / docs UI)

- WCAG 2.2 AA is the default client bar (2.1 AA minimum when 2.2 not applicable).
- Automated axe-class tools cover only ~30%; note manual keyboard / SR pass status.
- Critical a11y defects use severity ladder with user-impact statement.
- Do not claim "accessible" without stating method and residual gaps.

## 6. Jurisdiction, uncertainty, human counsel (legal / compliance) (HARD)

Every legal or compliance deliverable states:
- `jurisdiction`: e.g. US-federal, DE, EU-GDPR, multi / unknown
- `source_date` or `retrieved` for each material source
- `uncertainty`: known gaps, conflicts, or missing primary authority
- `human_counsel_required`: true when advice would bind, file, or sign

Mandatory disclaimer language (informational only, not a lawyer, not legal advice).
Forbidden: "I am your attorney", binding representation, autonomous legal_file,
destroying evidence, or presenting research as counsel opinion.

Stale sources (default max age 365 days unless source-specific) =>
`LEGAL_SOURCE_STALE` + human review trigger. Missing sources => no Gate: passed
for legal conclusions.

## 7. Compliance evidence and mapping

- Framework claims (SOC 2, ISO 27001, HIPAA, PCI-DSS, GDPR, CCPA) are control-mapped
  with evidence artifacts, never checkbox theater.
- Gap lists mark control ID, status (met/partial/missing), evidence, owner.
- Not an audit opinion unless a licensed auditor engagement says so; label drafts
  as informational readiness.

## 8. Documentation quality (technical-writer)

- Diataxis type chosen; no mixed-quadrant ship.
- Zero-hallucination: every claim traceable to code/spec or flagged TODO(owner).
- Samples runnable; last-updated present.
- No invented endpoints, flags, or env vars.
- Client-facing docs white-label when required.

## 9. Approval, receipts, failure, rollback

External mutations (scan-against-prod, file, publish docs to prod, open customer
tickets with legal conclusions) stop at approval_preview.

```text
APPROVAL_PREVIEW
action: <scan_external|legal_file|publish|mutate_external>
target: <system>
payload_summary: <what would happen>
risk: <low|med|high> + why
authority_needed: <role>
sources_for_claims: <list or UNVERIFIED>
status: AWAITING_HUMAN_AUTHORITY
```

Receipt when human-authorized:
```text
RECEIPT
action: ...
authority_ref: ...
result: <success|partial|failed>
artifacts: ...
rollback_hint: ...
```

Failure: preserve partial findings and drafts; do not invent completion.
Rollback: prior capability version is rollback_target; fixtures synthetic only.

## 10. Prohibited

- Legal advice presented as counsel or representation
- Scanning production systems from this skill wave
- Executing untrusted candidate scanners or uploading source externally
- Deploying, rotating secrets, or changing Gas Town control plane
- Material false positives on clean fixtures
- Invented CVEs, metrics, or evidence paths

## 11. Gate line

End successful deliverables with the literal line: `Gate: passed`
only when severity, evidence, false-positive, jurisdiction/uncertainty (when
applicable), and source-pinning checks for the deliverable are satisfied or
explicitly waived by human authority.
