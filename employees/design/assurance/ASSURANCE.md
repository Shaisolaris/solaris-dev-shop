# Design assurance contract

Domain: `design`  
Parent: `quality-security/assurance/ASSURANCE.md`  
Engine: `solaris/employees/quality-security/assurance/quality_os.py`

## Accountable outputs

| Artifact | Defect kinds owned | Risk floor |
|----------|-------------------|------------|
| UX flows / critique | ux, design | elevated when user-facing |
| Design system tokens | design | standard |
| Accessibility design | accessibility, design | elevated |
| Technical writing for release | release | elevated |

## UI/UX gates

1. Critical user journeys have happy + failure path designs.
2. Touch targets ≥44×44 CSS px; contrast 4.5:1 body / 3:1 large (WCAG 2.1 AA min).
3. Keyboard and screen-reader affordances designed (not bolted on later).
4. UX copy states empty/error/success; no dead-end states without recovery.
5. Accessibility defects route to **qa-engineer** (accountable gate) with
   **ui-ux-designer** as independent verifier for design-root fixes; pure visual
   UX defects route to **ui-ux-designer** with **qa-engineer** verifier.

## Blocking thresholds

- Contrast or keyboard trap on primary flow → accessibility S1/S2; cannot be
  self-closed by qa-engineer.
- Missing error-state design on money/PII flows → ux S2.

## Evidence to attach

```json
{
  "ux": {
    "summary": "Checkout critique; 2 S3 polish only",
    "artifacts": ["design/checkout-critique.md"]
  },
  "accessibility": {
    "summary": "axe + keyboard pass on /checkout",
    "artifacts": ["a11y/checkout-axe.json"]
  }
}
```
