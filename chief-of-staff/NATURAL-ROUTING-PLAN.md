# Chief of Staff - natural-talk routing upgrade (2026-07-11, from Nido forensics)
Target: meta/chief-of-staff/SKILL.md (description + Move 1) and the project STATUS.md template.

## Problem
Shai should never need trigger phrases or the operator PDF. In the Nido session, zero employees fired on scope docs, screen lists, pricing, and competitor research because nothing routed. Descriptions trigger on jargon ("PRD", "RICE", "SOW") - Shai talks in transcribed voice: "so she sent this message", "the doc looks amateur", "what do we say back".

## Fix A - description rewrite (chief-of-staff SKILL.md frontmatter)
Rewrite the trigger description to match natural/voice speech. Must include phrases like:
"she sent this", "she responded with", "what should I say back", "draft the reply", "make the doc", "build the scope", "the client said", "what do you think", "how should we play this", "give me the message", any pasted client message, any Upwork/Fiverr job or client conversation, any request that produces a client-facing document or message. Rule of thumb IN the description: "If Shai pastes a client message or asks for any deliverable, this skill fires FIRST - no exceptions."

## Fix B - Move 1 amendment (read the room → route from intent, not keywords)
Add to Move 1: map Shai's intent to employees by DELIVERABLE TYPE, not vocabulary:
- client message in → delivery-lead (voice/framing) + relevant specialist
- proposal/bid/pricing → upwork-proposals or proposal-writer + delivery-lead
- any client document → delivery-lead gate (house style lookup, templates/client-docs bundle) + owning specialist
- screens/design/UX anything → ui-ux-designer
- app build questions → mobile-developer / full-stack-developer
- competitor/market anything → market-researcher
Then EXECUTE the routing per Move 2.5 (invoke Skill tool same turn).

## Fix C - STATUS.md standing order (template + all active projects)
Insert at the very top of every project STATUS.md:
"STANDING ORDER: Any substantive request in this project - invoke ai-org-core:chief-of-staff FIRST (Skill tool, this turn), execute its routing, and name only employees actually invoked. Client documents: house style is cream/green #006039/gold (Shai Client Document Suite); never invent a palette; use templates/client-docs."
Apply to: Nido, Moviepie, Kelbell, Proforce Pest, Gobs of Games STATUS.md files + the template in meta/.

## Acceptance test
Paste a fake client message with no keywords ("she sent this = ...") in a fresh project chat → chief-of-staff must fire and invoke at least delivery-lead via the Skill tool before drafting the reply.
