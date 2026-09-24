# CFO - TOP-5 verified 2026 source scan (2026-06-13)

Domain: SaaS finance / runway / unit economics / FP&A.

| # | Source | Stars | License | Last commit | Maintainer | What it adds | Gate-0 | Tag |
|---|--------|-------|---------|-------------|------------|--------------|--------|-----|
| 1 | github.com/EveryInc/charlie-cfo-skill | 210 | MIT | 2026 (5 commits) | EveryInc (notable) | BOOTSTRAPPED/profitable-company lens: profit-as-constraint, reserve structure (operating/contingency/growth), 13-week cash flow, cash conversion cycle + working-capital (AR/AP/prepay), revenue-per-employee benchmarks, hiring-as-<12mo-payback ROI | PASS - Solaris CFO was VC-SaaS oriented (ARR/burn/fundraise) and lacked the bootstrapped lens, 13-week cash flow, reserve tiers, working-capital/CCC, and rev-per-employee benchmarks. Highly relevant - Solaris is itself a bootstrapped agency | METHODOLOGY (ABSORB - MIT) |
| 2 | github.com/alirezarezvani/claude-skills (cfo-advisor pod) | 17,992 | MIT | 2026-06-12 | alirezarezvani | financial_planning, ARR bridge, three-statement, benchmarks | CONTENT-DUPLICATE (already absorbed) | (absorbed) |
| 3 | github.com/OctagonAI/skills | (mid) | (varies) | 2026 | OctagonAI | agentic financial RESEARCH (filings analysis) | OVERLAP - filings/market-data tooling already covered by references/filings-and-market-data-tooling.md (sec-edgar-mcp) | (already absorbed adjacent) |
| 4 | borghei/claude-skills (cfo-advisor) | 262 | NOASSERTION (FLAG) | 2026-05-27 | borghei | cfo-advisor frameworks | OVERLAP + NOASSERTION - duplicates alirezarezvani cfo pod; no net-new vs current | REJECT (overlap) |
| 5 | Anthropic finance team's 150 internal skills | n/a | not public | n/a | Anthropic | production FP&A workflows | NOT OSS (internal, not published) | REJECT (not available) |

## Verdict
One strong win: **EveryInc/charlie-cfo-skill (210 stars, MIT, notable maintainer)** adds the BOOTSTRAPPED-CFO lens the Solaris CFO lacked - and it is the more applicable lens for Solaris (a bootstrapped/profitable agency, not a VC-backed SaaS). Net-new: profit-as-constraint mental model, the 3-tier reserve structure, a 13-week cash-flow discipline, working-capital / cash-conversion-cycle optimization (AR/AP/prepay), revenue-per-employee benchmarks, and hiring-as-payback-ROI. Absorbed as METHODOLOGY (MIT, clean). OctagonAI financial-research overlaps the already-absorbed filings tooling; borghei cfo-advisor (NOASSERTION) duplicates the alirezarezvani pod; Anthropic's 150 internal finance skills are not public. The alirezarezvani cfo pod stays the VC-SaaS canon (content-duplicate, absorbed).
