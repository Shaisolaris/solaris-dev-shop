# Specialized department runtime policy (Solaris)

Status: growth-revenue + product-design-creative + specialist-engineering alignment for ecommerce, CAD, game design, AR/VR, WordPress, and adjacent specialized skills  
Beads: skill-7fw, skill-5sg, skill-je0  
Synthetic / professional only - no private client files, no unlicensed assets.

## Permission model

| Action | Mode | Notes |
|--------|------|-------|
| read project/workspace materials | allow | declared paths only |
| draft artifacts | allow | markdown, design tokens, briefs, plans, store drafts in project store |
| message_send | require_human | customer email/SMS, client share of assets |
| spend | require_human | paid apps, stock, font licenses, billed plans, paid model APIs |
| mutate_external | require_human | live store, pixel prod, theme publish, Figma publish, asset CDN |
| deploy | deny | production deploy not autonomous |
| move_funds | deny | never silent charges |
| legal_file | require_human | license agreements, IP transfer drafts only |
| diagnose_health | deny | N/A |
| book | deny | N/A |

## Approval preview (mandatory shape)

```text
APPROVAL_PREVIEW
action: <message_send|spend|mutate_external|...>
target: <system/channel/tool>
payload_summary: <what would happen>
risk: <low|med|high> + why
authority_needed: <role/name level>
sources_for_claims: <list or UNVERIFIED>
license_check: <cleared|pending|blocked|n-a>
status: AWAITING_HUMAN_AUTHORITY
```

No execution step runs until status becomes `AUTHORIZED` by a human outside this skill.

## Growth-revenue standard

Obey `solaris/employees/marketing/GROWTH-REVENUE-STANDARD.md` for consent,
suppression, tracking consent mode, platform/store policy, attribution honesty,
receipts, failure, and rollback. Wave: skill-wave-growth-revenue-20260724.

## Product-design-creative standard

Also apply `solaris/employees/design/PRODUCT-DESIGN-CREATIVE-STANDARD.md` for
engineering-design, game-designer, and adjacent creative/CAD work:
accessibility, licensing, critique, and tool-availability honesty.
Wave: skill-wave-product-design-creative-20260724.

### Accessibility gate (when UI in scope)

- Target: WCAG 2.2 Level AA unless project specifies otherwise.
- Cover keyboard operability, name/role/value, contrast, focus visible, reduced motion.
- Game/UI shells document platform a11y notes (Unity UI Toolkit / Unreal UMG).
- Missing a11y when UI is in scope => fail rubric (no Gate: passed).

### Licensing and provenance gate

| Asset class | Required fields |
|-------------|-----------------|
| font | family, license, source URL, embed rights |
| stock image/video/audio | provider, license type, asset id, commercial use |
| 3D model/texture | license, redistribution, attribution |
| design system / Figma file | ownership, share permissions |
| code samples / templates | SPDX or license notice |

Unclear license => treat as **BLOCKED for publish/export**; draft plans may proceed as PARTIAL.

### Unavailable licensed software

If Figma MCP, Blender MCP, FreeCAD MCP, Resolve, Unity, Unreal, or paid generative APIs are missing:
1. State tool/MCP as UNAVAILABLE.
2. Emit PARTIAL plan or BLOCKED execution (never invent rendered frames, STEP files, or Figma node IDs).
3. Offer alternative path (manual steps, open-source substitute, host connect instructions).

### Artifact evidence

Successful turns include:
- brief restatement (when product/design/creative work)
- provenance_ledger (sources + licenses)
- partial_or_blocked_note (or explicit NONE)
- critique or review notes when finalizing design/creative artifacts
- Gate: passed only when controls hold

## Specialist-engineering standard

Obey `solaris/employees/specialized/SPECIALIST-ENGINEERING-STANDARD.md` for AR/VR,
WordPress, and other specialized platform skills in wave skill-wave-specialist-engineering-20260724 (skill-je0).
Fail closed on missing engines/SDKs/licenses; no store submission, hosting production
mutation, or untrusted plugin execution without human authority.
