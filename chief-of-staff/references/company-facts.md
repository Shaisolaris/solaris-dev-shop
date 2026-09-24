# Company Facts - standing knowledge (bundled; update via the brain, not by hand-editing installs)

## Who
- Owner/operator: the Solaris Dev Shop maintainer. Supply your own contact. Do not commit a personal email.
- SOLARIS = the business: white-label software agency (Solaris Tek) + Solaris Studio games. ALFRED = personal life (book, PhD, health, travel, finance). Never mix the two.

## White-label doctrine (hard)
- Client-facing voice is ALWAYS "I", never "we"/"our team". No mention of team members, rates, or internal tooling in anything a client sees.
- Delivery/ is the ONLY client-facing folder. Scope defines, Development builds, Delivery ships, Assets holds raw inputs.

## Where things live
- Clients: <project-root>/<ClientName>/ (Scope/Development/Delivery/Assets + STATUS.md). Gigs: Solaris/gigs/<platform>/<order>/.
- STATUS.md is the sync bus: read before reporting, update before stopping. One chat per project by default, two max.
- Standing memory lives in the project repository you choose. Files are memory, git is truth: not committed = didn't happen. Do not point public skills at a private org repo.

## Documents + money (hard rules)
- Client docs come from templates/client-docs/ bundle (project.js auto-fill, badge must be green, drop-rules per FIELD-MAP). Interview protocol: one pre-filled checklist, one answer round.
- EVERY issued doc gets a registry row (Solaris/_accounting/registry/registry.csv) BEFORE sending: global REG-YYYY-NNNN + per-project ref. Append-only; voids keep rows. Invoices copy to _accounting; never auto-deleted; kept ~6 years.
- Money guardrails: deterministic math only, advise-never-execute, large spends need Shai's explicit yes.

## Preferred stack
- Web: React/Next.js/TypeScript/Tailwind (+ shadcn), Vite. Backend: Laravel/PHP 8.x, Node, Python. DB: MySQL/Postgres. WordPress for WP clients (FSE-first). Games: Unity (Solaris Studio titles). Deploy: Vercel/Railway/Bluehost/FTP-gig.
- E-comm: Shopify. Payments: Stripe. PM: ClickUp. Design: Figma + Canva. Docs: the branded 10-doc series.

## Communication rules (Shai's preferences)
- Executive summaries, always. Plain talk, no walls of text, no bullet spam. Execute, don't over-ask - one batched question round max.
- Never steal screen focus mid-task. Fresh chat after any install/update (capabilities load at chat start).

## Client intake flow (short form)
Upwork/LinkedIn lead → proposal (upwork-proposals gig / delivery-lead) → won → "new client X" scaffold → Doc 3 Recap (if consult) → Doc 1 SOW (+2 NDA, +4 Milestone Plan if fixed) → build → Doc 7 Report + Doc 5 Invoice per milestone → Doc 9 Closeout (+10 Maintenance if sold) → archive after ~90 days (invoices preserved).

## Comms rule - questions (added 2026-07-11, standing)
NEVER use multiple-choice question widgets (AskUserQuestion/MCQ) with Shai. Ever. Ask questions in plain chat prose, or better: pick the sensible default, state it, and proceed. This has been repeated many times; treat a violation as a gate failure.


## Public standing rules

- Do not mix the Solaris namespace with Alfred or any personal-life namespace.
- Do not commit passwords, API keys, tokens, or real account details. Use a user-supplied placeholder.
- Do not require a personal Desktop path, a private org repository, or a specific machine name.
- Client-facing voice is first person singular. Do not invent a team.
- Money actions are advise-only unless the owner explicitly confirms the spend.
- The employee is Solaris Dev Shop. Do not name a model vendor as the employee or the product.
- Mechanically checkable deliverables need an independent review before they ship. No self-certification.
- Git author on client work is the owner's chosen name and email, never a bot or vendor name.
