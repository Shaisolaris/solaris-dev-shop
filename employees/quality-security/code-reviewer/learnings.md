# Code Reviewer - Learnings (Pending)

```
Format: - **<YYYY-MM-DD> - <project/context>**: <what> *Proposed rule: <takeaway>* Tags: [#pr], [#audit], [#security], [#perf], [#deps], [#lang-X], [#promoted?]
```

---

## Pending observations

- **2026-04-24 - Code Reviewer clean rebuild**: First build absorbed Shai's code-review skill wholesale (scanner.py + 20 angles + 7 phases + 4 modes + vuln pattern DB). Clean rebuild from 6 repos produces a strong mode-based review employee (PR + Full Audit + Security + Dependency + Karpathy + Adversarial + Debug). Shai's skill layers in later as v0.3.0 with its scanner + pattern DB.
  *Proposed rule: Mode-based reviewers (distinct review patterns per context) are a better design than a monolithic review skill. Shai's skill had the mode-architecture; the 6-repo absorption preserved it independently.*
  Tags: [#mode-architecture], [#promoted?]

- **2026-04-24 - Code Reviewer clean rebuild**: sickn33 had 10+ code-review-specific skills - by far the most fine-grained of the 6 repos. Includes requesting-review, receiving-review, AI-on-AI review, vibers peer-style - all useful facets. Rolled into a single employee with mode-switching.
  *Proposed rule: When a single source repo has fine-grained specialization (sickn33's code-review-*), absorb as modes or procedures rather than collapsing. Preserves the nuance.*
  Tags: [#preserve-fine-grain]

- **2026-04-24 - Code Reviewer clean rebuild**: Severity taxonomy (Blocker / Important / Nit / Praise) is universal across all the reviewed sources. Standardized explicitly.
  *Proposed rule: Severity tags are a universal pattern across review sources; keep them consistent across Solaris (also used by Security Auditor, QA Engineer, Performance Engineer). Shared vocabulary reduces cognitive load.*
  Tags: [#shared-vocabulary]

---

- **2026-06-13 - v0.5.0 deep quality pass**: Both reference tables (SKILL.md + rules.md) listed 8 phantom checklist files (`code-review-checklist.md`, `full-audit-20-angles.md`, etc.) that were never created - the mode methodologies actually live inline. SKILL's References table also omitted the two refs that DO exist (code-context-operator.md, trivy). Net-new layered scanning stack added: semgrep (AST taint), osv-scanner (2nd CVE DB + reachability), gitleaks (history secrets), danger-js (PR automation). CI SHA-pin doctrine added - this employee gates main so it must enforce it.
  *Proposed rule: when an employee references checklist files, verify they exist before shipping - a reference table pointing at non-existent files is itself a P2 documentation-drift finding (the employee should catch this in its own reviews). Also: scanners are layered, not redundant - Trivy (tree SCA/secrets) + semgrep (taint) + osv (2nd DB) + gitleaks (history) each catch what the others miss.*
  Tags: [#audit], [#deps], [#security], [#self-application]

- **2026-08-13 - named-heading protocol**: measured D5 gap was job-two omitting contract-required artifact headings; closed by named-heading protocol in `job-two-improvement.md`.
  *Proposed rule: a revision that follows SKILL.md but misses the contract heading tokens has not improved.*
  Tags: [#job-two], [#required-artifacts]

## Promotion log

| Date | Observation → Rule | Location |
|------|-------------------|----------|
| | | |
