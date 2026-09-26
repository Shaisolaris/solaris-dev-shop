# The Org Chart

How the 61 Solaris employees (12 departments) work together, under the chief-of-staff orchestration layer. Counts regenerated from disk on 2026-09-26; the live source of truth is `control-plane/roster.json`.

## Command structure

```
                           You (the owner)
                                │
                                ▼
                     ┌─────────────────────┐
                     │   Chief of Staff    │  Every request enters here
                     │    (dispatcher)     │  Parses intent, assembles team
                     └──────────┬──────────┘
                                │
           ┌────────────┬───────┼────────┬─────────────┐
           ▼            ▼       ▼        ▼             ▼
          CEO          CTO     CMO      CFO           COO
           │            │       │        │             │
      (strategy)  [Engineering][Marketing][Finance] [Operations]
                  [Infra     ][Creative ][Legal   ] [Sales    ]
                  [QualSec   ][Media    ][Compl.  ] [Product  ]
                  [Data      ]
                  [Design    ]

                    Background (no dispatch authority)
                  ┌──────────────────────────────────────┐
                  │ Learnings sweep  (internal)          │
                  │ Market watch     (external)          │
                  └──────────────────────────────────────┘
```

## How a request flows

**Example: "Build a landing page for the Unity game with ASO in mind."**

1. **Chief of Staff** parses intent → routes to CMO + CTO (cross-functional)
2. **CMO** assembles a marketing team: cro-landing-designer + seo-aso-specialist + content-marketer
3. **CTO** assembles a build team: full-stack-developer + ui-ux-designer
4. **Learnings sweep** (session end) captures cross-learnings into the relevant `learnings.md` files
5. **Market watch** gets a gap note if the team hits a missing capability - e.g. "we need an ASO-specific keyword tool we don't have"
6. Deliverable: landing page + ASO keyword research + implementation + lessons captured

## Department heads and their teams

### Engineering (under CTO)
ai-automation-engineer, ai-ml-engineer, backend-developer, blockchain-developer, devops-engineer, frontend-developer, full-stack-developer, iot-engineer, llm-agent-designer, mobile-developer, unity-developer, unreal-developer

### Infrastructure (under CTO)
cloud-architect, database-administrator, fleet-dispatcher, fleet-provisioner, kubernetes-specialist, network-engineer, site-reliability-engineer

### Quality, Security & Reliability (under CTO)
code-reviewer, performance-engineer, qa-engineer, security-auditor

### Data (under CTO)
data-analyst, data-engineer, data-scientist

### Design (under CTO for tech, CMO for brand)
technical-writer, ui-ux-designer

### Creative Media (under CMO)
3d-artist, image-generator, video-editor, voice-audio-producer

### Marketing (under CMO)
content-marketer, cro-landing-designer, email-specialist, market-researcher, paid-ads-manager, seo-aso-specialist, social-media-manager

### Product & Project (under COO)
business-analyst, delivery-lead, product-manager, project-manager, project-onboarding

### Sales & Outreach (under COO)
customer-success, outreach-specialist, proposal-writer, sales-engineer

### Legal & Compliance (under CFO)
compliance-auditor, legal-advisor

### Leadership / Strategy (under CEO)
ceo, cfo, cmo, coo, cto

### Specialized Domains (called ad-hoc, no standing head)
ar-vr-developer, ecommerce-specialist, engineering-design, game-designer, payments-specialist, wordpress-master (ships 38 diagnostic sub-skills under `diagnostics/`)

## Escalation triggers (event-driven model)

The canonical event names for the Flows-mode escalation used by `chief-of-staff/rules.md`:

| Event name | Trigger condition | Listener(s) | Resolution |
|---|---|---|---|
| `clickup-github-divergence` | ClickUp task/board state disagrees with the GitHub repo on what shipped or what's done | project-manager (reconciles ClickUp) | **GitHub is truth.** PM reconciles ClickUp to match the repo; never the reverse |
| `financial-risk-spike` | CFO sees burn multiple > 2 | ceo | Spending freeze review before next milestone |
| `security-block` | security-auditor finds CVSS ≥ 9.0 | cto, chief-of-staff | Stop ship vs patch-and-ship vs document-and-track |
| `capability-gap` | Team hits a missing capability mid-assignment | chief-of-staff | `[GAP]` note to the owner; queued for market watch |

Unresolved conflicts escalate per the table above; when all else fails → the owner. The owner is the only "above."

## Doctrine carve-out + canon

**Delivery-lead carve-out - ALLOWED vs still-BANNED:**

- **ALLOWED:** delivery-lead orchestrates *human contractors* (TL / PM / dev) and *client delivery* - scoping, spec-lock, milestone QA gates, white-label client comms, project takeover. It manages people *outside* the AI fleet and the client relationship.
- **STILL BANNED:** the AI-fleet-coordinator / VP-of-Engineering pattern - any employee inserted *between* the strategy layer and the flat AI execution layer to manage or route other AI employees. delivery-lead never manages AI employees; Chief of Staff still routes the fleet.

**Canon row:**

| Discipline | Canon owner | What they decide |
|---|---|---|
| **Client delivery / engagement management** | delivery-lead | Scoping, spec-lock, milestone QA gates, white-label client comms, human-contractor (TL/PM/dev) management |

## The three invariants

Regardless of who's working on what, these always apply:

1. **Chief of Staff runs first** for any multi-domain request. Direct-to-employee is allowed only for single-domain questions.
2. **Learnings sweep runs at session end** to collect new `learnings.md` entries; promotion to `rules.md` needs owner review.
3. **Market watch runs on a weekly schedule** and receives ad-hoc gap-requests throughout.

## Org-wide rules (promoted from employee lessons)

When the same lesson surfaces across 3+ employees, it graduates here. Seed rules:

- **Design before you code.** Every screen, feature, or campaign has its "player mood / primary action / previous-next" defined before execution. Originated in Unity Developer; generalizes everywhere.
- **Methodology updates beat logs.** When a pattern stabilizes, rewrite the rules - don't just log it. The point is compounding wisdom, not an ever-growing log file.
- **Verify your outcome, not just the tool call.** "No error thrown" ≠ "task done." Read the result back. Originated in CTO's pre-commit verification protocol.
