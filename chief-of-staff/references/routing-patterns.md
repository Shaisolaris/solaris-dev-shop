# Routing patterns - worked examples of request -> route (companion to routing-table.md)
The routing DECISION is executable + tested via scripts/route.py (parses routing-table.md, self-test of 10 canonical requests). These are the worked examples the SKILL references.

| Request | Route | Mode | Why |
|---|---|---|---|
| "please review this code" | code-reviewer | direct | single-domain, clear ask |
| "is this NDA safe to sign" | legal-advisor | direct | legal/contract |
| "the site is down in prod" | site-reliability-engineer | direct | incident |
| "the login page is slow" | performance-engineer | direct | perf signal |
| "what's new in vector databases" | market-researcher | direct | external scan |
| "what have we learned about onboarding" | chief-of-staff (learnings sweep) | internal | synthesis from learnings.md, not a route |
| "build me a landing page" | cto + full-stack + ui-ux + qa | team | multi-domain build |
| "write me a launch blog post" | cmo + content-marketer | team | marketing content |
| "should we choose AWS or GCP" | cto | advisor | decision support + ADR |
| "can you charge the client's card" | STOP - confirm Shai | gate | money movement (red flag) |
| "i don't know what to do next" | clarify-one-question | clarify | ambiguous - ask one Q first |

Run `python3 scripts/route.py "<request>"` to resolve; `route.py --selftest` gates the routing logic in CI-style checks. Keep this table and routing-table.md in sync; routing-table.md is the machine source of truth.
