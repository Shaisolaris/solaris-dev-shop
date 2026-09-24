# Business & creative runtime policy (Solaris)

Status: hardening shared policy for leadership / marketing / sales-outreach / creative-media  
Bead: skill-solaris-business-hardening  
Synthetic / professional only  -  no private Alfred personal data.

## Permission model

| Action | Mode | Notes |
|--------|------|-------|
| read project/workspace materials | allow | declared paths only |
| draft artifacts | allow | markdown/files in project store |
| message_send | require_human | email, SMS, LinkedIn, social DM, ESP |
| spend | require_human | ad buy, boosts, paid APIs billed to client/org |
| mutate_external | require_human | publish, CRM live write, DNS, pixel prod |
| deploy | deny | production deploy not in business skills |
| move_funds | deny | never |
| legal_file | deny or require_human | proposals draft only; no filing/signature |
| diagnose_health | deny | N/A |
| book | deny | N/A |

## Approval preview (mandatory shape)

```text
APPROVAL_PREVIEW
action: <message_send|spend|mutate_external|...>
target: <system/channel>
payload_summary: <what would happen>
risk: <low|med|high> + why
authority_needed: <role/name level>
sources_for_claims: <list or UNVERIFIED>
status: AWAITING_HUMAN_AUTHORITY
```

No execution step runs until status becomes `AUTHORIZED` by a human outside this skill.

## Claim ledger (mandatory for public or commercial claims)

| claim | type (metric/quote/competitor/pricing) | source | date | confidence | disposition |
|-------|------------------------------------------|--------|------|------------|-------------|
| ... | ... | ... | ... | high/med/low | keep / UNVERIFIED / STALE / drop |

## Financial authority ladder

| Level | May approve | Examples |
|-------|-------------|----------|
| L0 skill | none of spend/commit | drafts only |
| L1 operator | non-binding internal plans | budget *proposals* |
| L2 budget owner | spend within pre-approved envelope | ad budget change after preview |
| L3 exec | pricing floors, discounts, contracts | CEO/CFO named |

Skills operate at **L0** unless a sealed order raises authority. They never self-promote.

## Brand policy gates

- Voice matches provided brand kit; if missing, state assumptions and mark draft.
- No unsubstantiated superlatives ("#1", "guaranteed") without source.
- No competitor defamation; comparative claims need dated evidence.
- No trademark misuse; flag clearance needs instead of asserting clearance.
- Accessibility and platform policy constraints noted for creatives.

## Research provenance

- Prefer primary sources; record retrieval date.
- Distinguish fact / estimate / opinion.
- Market sizes and benchmarks always dated; undated = STALE.
- Fixtures and demos use synthetic entities only.

## Rollback / recovery

- Failed external preview → leave draft artifacts; do not retry send/spend loops.
- Revoked connector → blocked envelope, preserve partial drafts.
- Bad claim discovered post-draft → amend claim ledger; do not silent-edit customer-facing commits already approved without new preview.
- Contract rollback_target remains prior capability version; no history rewrites.

## Prohibited in git / evidence

Credentials, tokens, raw connector payloads, private health/finance/personal content, real customer secrets.

## Product-design-creative wave (2026-07-24)

Also apply `solaris/employees/design/PRODUCT-DESIGN-CREATIVE-STANDARD.md` for accessibility, licensing, critique, and tool-availability honesty.

