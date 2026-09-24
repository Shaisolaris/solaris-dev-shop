# Legal and compliance assurance contract

Domain: `legal-compliance`  
Parent: `quality-security/assurance/ASSURANCE.md`  
Engine: `solaris/employees/quality-security/assurance/quality_os.py`

## Authority boundaries (hard)

| Allowed | Forbidden without human + licensed counsel |
|---------|--------------------------------------------|
| Informational research | Binding legal advice |
| Draft clause options labeled non-binding | Filing lawsuits, trademarks, regulatory submissions |
| Risk flags + review triggers | Claiming attorney-client relationship |
| Source-cited comparisons | Destroying or concealing evidence |

Skills in this domain **must** state they are not a lawyer / not legal advice.

## Gates

| Defect kind | Accountable | Verifier |
|-------------|-------------|----------|
| legal_risk | legal-advisor | compliance-auditor |
| compliance | compliance-auditor | legal-advisor |
| privacy | compliance-auditor | security-auditor |

## Source freshness

- Every legal/compliance claim cites sources with `retrieved_at` or `published_at`.
- Default max age: **365 days** (override per source via `max_age_days`).
- Stale source → `LEGAL_SOURCE_STALE` + trigger `refresh_sources_then_human_review`.

## Human / legal review triggers

Fire explicit human review when any of:

1. Binding-language or filing patterns detected
2. `legal_file` or other high-stakes action requested
3. Regulatory + external blast radius on a release packet
4. Stale or missing sources on a legal conclusion
5. Waiver requested on a legal_risk or compliance S0–S2 finding

## Engine checks

`check_legal_boundaries()` enforces:

- `LEGAL_BINDING_PROHIBITED`
- `LEGAL_FILING_FORBIDDEN`
- `LEGAL_DISCLAIMER_MISSING`
- `LEGAL_SOURCE_REQUIRED` / `LEGAL_SOURCE_STALE` / date errors
- `HIGH_STAKES_REQUIRES_HUMAN`

## Evidence to attach

```json
{
  "legal_risk": {
    "summary": "MSA LoL review - informational; counsel required before signature",
    "artifacts": ["legal/msa-review-informational.md"],
    "sources": [
      {"id": "restatement-contracts", "retrieved_at": "2026-06-01", "max_age_days": 365}
    ]
  },
  "compliance": {
    "summary": "SOC2 CC6 mapping draft - not an audit opinion",
    "artifacts": ["compliance/soc2-cc6-draft.md"]
  }
}
```
