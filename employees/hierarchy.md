# The Org Chart

How the Solaris work employees (52 across 12 departments) work together, under the meta orchestration layer. Counts are regenerated from disk in meta/roster-manager/references/roster.md.

## Command structure

```
                           You (Shai)
                                │
                                ▼
                     ┌─────────────────────┐
                     │   Chief of Staff    │  Every request enters here
                     │    (dispatcher)     │  Parses intent, assembles team
                     └──────────┬──────────┘
                                │
           ┌────────────┬───────┼────────┬─────────────┬────────┐
           ▼            ▼       ▼        ▼             ▼        ▼
          CEO          CTO     CMO      CFO          CHRO      COO
           │            │       │        │             │        │
      (strategy)  [Engineering][Marketing][Finance] [People] [Operations]
                  [Infra     ][Content  ][Legal  ] [Support][Product]
                  [QualSec   ][SEO/ASO  ][Compl. ]
                  [Data      ][Social   ]
                  [Design    ][Sales    ]

                         Meta Layer (runs in background)
                  ┌──────────────────────────────────────┐
                  │ Knowledge Synthesizer  (internal)    │
                  │ Talent Scout & R&D Chief (external)  │
                  │ Context Manager (token efficiency)   │
                  └──────────────────────────────────────┘
```

## How a request flows

**Example: "Build a landing page for the Unity game with ASO in mind."**

1. **Chief of Staff** parses intent → routes to CMO + CTO (cross-functional)
2. **CMO** assembles a marketing team: CRO/Landing Page Designer + SEO+ASO Specialist + Content Marketer
3. **CTO** assembles a build team: Full-Stack Developer + UI/UX Designer
4. **Knowledge Synthesizer** watches execution for cross-learnings worth capturing
5. **Talent Scout** gets notified if the team hits a gap - e.g. "we need an ASO-specific keyword tool we don't have" → scheduled for next external scan
6. Deliverable: landing page + ASO keyword research + implementation + lessons captured

## Department heads and their teams

### Engineering (under CTO)
Full-Stack Developer, Mobile Developer, Unity/Game Developer, Blockchain/Web3 Developer, IoT Engineer, AI/ML Engineer, LLM/Agent Designer, AI Automation Engineer, DevOps Engineer

### Infrastructure (under CTO)
Cloud Architect, Kubernetes Specialist, Database Administrator, Site Reliability Engineer

### Quality, Security & Reliability (under CTO)
Code Reviewer, Security Auditor, QA Engineer, Performance Engineer

### Data (under CTO)
Data Analyst, Data Engineer, Data Scientist

### Design (under CTO for tech, CMO for brand)
UI/UX Designer, Technical Writer

### Product & Project (under CEO)
Product Manager, Project Manager, Business Analyst, Delivery Lead (client delivery / engagement management)

### Marketing (under CMO)
Content Marketer, SEO+ASO Specialist, CRO+Landing Page Designer, Paid Ads Manager, Email Specialist, Social Media Manager, Market Researcher

### Sales & Outreach (under COO)
Sales Engineer, Customer Success Manager, Proposal Writer, Outreach Specialist

### Legal & Compliance (under CEO)
Legal Advisor, Compliance Auditor

### Specialized Domains (called ad-hoc)
Game Designer, WordPress Master, E-commerce Specialist, Payments Specialist, AR/VR Developer

### Support & Personal (under CHRO/COO)
Virtual Assistant, Book Writer, Health Manager, Research Paper Writer, Video Editor

### Meta / Orchestration (serves everyone)
Chief of Staff, Knowledge Synthesizer, Talent Scout & R&D Chief, Context Manager

## Doctrine carve-out + canon (added 2026-06-04, by Shai's direction)

The prior "never fold Shai personal skills into employees" rule is **retired** (see `meta/roster-manager/references/roster.md` hard rule #1). Shai's personal/work skills are now folded into the matching employees and gigs.

**Delivery-lead carve-out - ALLOWED vs still-BANNED:**

- **ALLOWED:** delivery-lead orchestrates *human contractors* (TL / PM / dev) and *client delivery* - scoping, spec-lock, milestone QA gates, white-label client comms, project takeover. It manages people *outside* the AI fleet and the client relationship. It *orchestrates* (never performs) the takeover chain: codebase-onboarding → code-review → migration-architect.
- **STILL BANNED:** the AI-fleet-coordinator / VP-of-Engineering pattern - any employee inserted *between* the strategy layer and the flat AI execution layer to manage or route other AI employees. delivery-lead never manages AI employees; Chief of Staff still routes the fleet.

**Canon row:**

| Discipline | Canon owner | What they decide |
|---|---|---|
| **Client delivery / engagement management** | delivery-lead | Scoping, spec-lock, milestone QA gates, white-label client comms, human-contractor (TL/PM/dev) management |

**Named escalation event:**

| Event name | Trigger condition | Listener(s) | Resolution |
|---|---|---|---|
| `clickup-github-divergence` | ClickUp task/board state disagrees with the GitHub repo on what shipped or what's done | project-manager (reconciles ClickUp) | **GitHub is truth.** PM reconciles ClickUp to match the repo; never the reverse |

---

## The three invariants

Regardless of who's working on what, these always apply:

1. **Chief of Staff runs first** for any multi-domain request. Direct-to-employee is allowed only for single-domain questions.
2. **Knowledge Synthesizer runs at session end** to sweep new `learnings.md` entries and promote stable ones.
3. **Talent Scout runs on weekly schedule** and receives ad-hoc gap-requests throughout.

## Org-wide rules (promoted from employee lessons)

When the same lesson surfaces across 3+ employees, it graduates here. Seed rules:

- **Design before you code.** Every screen, feature, or campaign has its "player mood / primary action / previous-next" defined before execution. Originated in Unity Developer; generalizes everywhere.
- **Methodology updates beat logs.** When a pattern stabilizes, rewrite the rules - don't just log it. The point is compounding wisdom, not an ever-growing log file.
- **Verify your outcome, not just the tool call.** "No error thrown" ≠ "task done." Read the result back. Originated in CTO's pre-commit verification protocol.
- **Load only what you need.** Progressive disclosure for tokens - never load a giant reference file when a small rules.md is enough.

*(These seed rules will be revised as lessons actually accumulate. This section is the graduation target for employee-level learnings that stabilize across the org.)*
