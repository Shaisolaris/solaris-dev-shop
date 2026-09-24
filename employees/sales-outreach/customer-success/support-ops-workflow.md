# Inbound Support Ops Workflow (ticket -> escalation -> KB)

**Source:** anthropics/knowledge-work-plugins (official Anthropic, Apache-2.0) - `customer-support` plugin, skills: `ticket-triage`, `draft-response`, `customer-escalation`, `kb-article`, `customer-research`. Methodology lift permitted with attribution.

## Gate-0 net-new justification
The existing CSM files own the post-sale RELATIONSHIP lane (health scoring, save plays, onboarding phases, renewal, QBR/EBR). They contain NO inbound support-operations workflow - no ticket prioritization, no escalation-packaging format, no KB-authoring template, no situational draft-response patterns. Net-new reactive support muscle that complements the proactive retention muscle when ticket volume bleeds into CSM accounts before a dedicated support hire exists.

## Methodology absorbed
1. **Ticket triage (P1-P4):** categorize -> priority -> route -> dedupe vs known issues first. P1 prod-down/data-loss/security; P2 major broken + workaround; P3 minor/cosmetic; P4 question/request. Map priority->SLA->owning team.
2. **Draft-response by situation:** product question, escalation/outage, bad-news (delay/won't-fix), feature decline, billing. Acknowledge -> state what's true -> next concrete step -> set expectation.
3. **Escalation packaging:** repro steps + business impact (accounts + ARR + churn risk) + history + right target. Trigger on beyond-normal bug, multi-customer issue, churn threat, SLA breach.
4. **KB-article authoring:** resolved ticket / recurring question -> searchable article (problem -> symptoms -> cause -> step-by-step fix -> related).
5. **Customer-research (multi-source):** look up account/question with attribution + confidence before drafting; check what was previously told.

## Standing orders
White-label voice (respond as "I"). Model-first: ClickUp + a health log until ticket volume justifies a real support platform.
