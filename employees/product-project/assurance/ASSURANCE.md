# Product / project assurance contract

Domain: `product-project`  
Parent: `quality-security/assurance/ASSURANCE.md`  
Engine: `solaris/employees/quality-security/assurance/quality_os.py`

## Accountable outputs

| Artifact | Defect kinds owned | Risk floor |
|----------|-------------------|------------|
| PRD / requirements | requirements | standard |
| Opportunity assessment | requirements | standard |
| Launch / rollback plan | release, functional | elevated |
| Operator-lens scope | requirements, privacy | elevated when PII |

## Product Manager / Business Analyst gates

1. Every requirement maps to testable Given/When/Then acceptance (or explicit
   non-goal).
2. Success metrics have baseline + target + window.
3. Operator lens (9 back-office surfaces) scoped in or deferred with reason.
4. Launch plans include phase gates **and** rollback thresholds before GA.
5. Privacy / legal / security dimensions declared when data_sensitivity ≠ none.

## Blocking thresholds

- Missing acceptance criteria on a committed story → functional/requirements S2.
- Launch without rollback thresholds at risk ≥ high → release S2.
- Self-close of a requirements finding by product-manager → forbidden; verifier
  is business-analyst (or human-owner).

## Evidence to attach

```json
{
  "requirements": {
    "summary": "PRD v0.3 locked; 12 stories with GWT",
    "artifacts": ["Delivery/prd-v0.3.md"],
    "blocking_open": 0
  }
}
```

## Finding → order

Unresolved product findings convert to orders owned by `product-manager` with
closure criteria requiring independent BA or human verification for S0-S2.
