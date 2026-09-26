# QA Engineer - Learnings (Pending)

```
Format: - **<YYYY-MM-DD> - <project/context>**: <what> *Proposed rule: <takeaway>* Tags: [#e2e], [#a11y], [#flaky], [#load], [#visual], [#mobile], [#promoted?]
```

---

## Pending observations

- **2026-04-24 - QA clean rebuild (6 repos only)**: Clean rebuild from 6 repos produces strong test-strategy + accessibility-audit + flaky-triage + load-testing coverage. Shai's playwright-pro (5 workflows + Golden Rules + Cypress/Selenium migration patterns + MCP test servers) layers in at v0.3.0.
  *Proposed rule: Test employees benefit from role-based locator discipline as a universal rule. Shared across Playwright, Cypress, Detox, Maestro - stable abstractions over implementation selectors.*
  Tags: [#role-based-locators]

- **2026-04-24 - QA clean rebuild**: wshobson has the richest a11y content (WCAG + screen reader + mobile + ARIA patterns across multiple plugins). Consolidated into a single accessibility-audit reference.
  *Proposed rule: For cross-cutting concerns (a11y, security, perf), consolidate into a single reference per employee rather than splitting per platform.*
  Tags: [#cross-cutting-consolidation]

- **2026-04-24 - QA clean rebuild**: Severity taxonomy (P0/P1/P2/P3) shared with Code Reviewer. Consistency across quality-security employees reduces cognitive load when composite reports are produced.
  *Proposed rule: Severity vocabulary is department-shared in Solaris. Code Reviewer + QA Engineer + Security Auditor + Performance Engineer all use P0/P1/P2/P3.*
  Tags: [#shared-severity]

---

## Promotion log

| Date | Observation → Rule | Location |
|------|-------------------|----------|
| | | |

## 2026-05-01 - M5 absorption: MetaGPT QA SOP (v0.4.0)
- 3-case minimum per method (happy/edge/error)
- Independence rule: QA writes tests, NOT the Engineer (prevents matching-bug syndrome)
- 7 quality gates, all hard-block
- CI-only execution, no local-only testing
- Source: github.com/FoundationAgents/MetaGPT
## Sources

- Upstream: Schemathesis (license not stated: 3,318); Stryker-JS (license not stated: ~2,900); Testcontainers (license not stated: 2,500 (node); 4.8k Go, 4.3k .NET); Vitest (license not stated: ~16,600); faker-js (license not stated: 15,363)
- What was used: methodology absorbed: Schemathesis, Stryker-JS, Testcontainers; methodology only: Vitest, faker-js
- License notes: licenses not recorded in scan for: Schemathesis, Stryker-JS, Testcontainers, Vitest, faker-js - verify before reuse; no code vendored
