# Product / design / creative runtime policy (Solaris)

Status: hardening for product-project / design / creative-media / specialized design tools  
Wave: skill-wave-product-design-creative-20260724  
Synthetic / professional only - no private client files, no unlicensed assets.

## Permission model

| Action | Mode | Notes |
|--------|------|-------|
| read project/workspace materials | allow | declared paths only |
| draft artifacts | allow | markdown, design tokens, briefs, plans in project store |
| message_send | require_human | client share, Slack, email of assets |
| spend | require_human | stock purchase, paid model APIs, font licenses |
| mutate_external | require_human | Figma publish, store upload, CMS, asset CDN |
| deploy | deny | production deploy not in these skills |
| move_funds | deny | never |
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
license_check: <cleared|pending|blocked>
status: AWAITING_HUMAN_AUTHORITY
```

No execution step runs until status becomes `AUTHORIZED` by a human outside this skill.

## Accessibility gate (UI/UX and product surfaces)

- Target: WCAG 2.2 Level AA unless project specifies otherwise.
- Cover keyboard operability, name/role/value, contrast, focus visible, reduced motion, error identification.
- Game/UI shells document platform a11y notes (Unity UI Toolkit / Unreal UMG).
- Missing a11y when UI is in scope => fail rubric (no Gate: passed).

## Licensing and provenance gate

| Asset class | Required fields |
|-------------|-----------------|
| font | family, license, source URL, embed rights |
| stock image/video/audio | provider, license type, asset id, commercial use |
| 3D model/texture | license, redistribution, attribution |
| design system / Figma file | ownership, share permissions |
| code samples / templates | SPDX or license notice |

Unclear license => treat as **BLOCKED for publish/export**; draft plans may proceed as PARTIAL.

## Unavailable licensed software

If Figma MCP, Blender MCP, FreeCAD MCP, Resolve, Unity, Unreal, or paid generative APIs are missing:
1. State tool/MCP as UNAVAILABLE.
2. Emit PARTIAL plan or BLOCKED execution (never invent rendered frames, STEP files, or Figma node IDs).
3. Offer alternative path (manual steps, open-source substitute, host connect instructions).

## Artifact evidence

Successful turns include:
- brief restatement
- provenance_ledger (sources + licenses)
- partial_or_blocked_note (or explicit NONE)
- critique or review notes when finalizing
- Gate: passed only when controls hold

See also: `solaris/employees/design/PRODUCT-DESIGN-CREATIVE-STANDARD.md`.
