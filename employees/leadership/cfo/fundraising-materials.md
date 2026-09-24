# Fundraising Materials - The Financial Side of the Raise

Methodology absorbed 2026-06-14 from ECC (github.com/affaan-m/ECC, MIT) skill `investor-materials`, financial slice only. Methodology lifted, no code bundled.

Scope key: `fundraising_financials`

## Why this exists (Gate-0 boundary)

The CFO canon already covers the INTERNAL operating side: bottoms-up three-statement modeling, the SaaS metrics hierarchy (Tier 1-4), AOP/MBR/rolling-forecast cadence, the bootstrapped lens (13-week cash flow, reserve tiers, CCC), valuation triangulation, IC-memos, and filings-grounded comparables. None of that is fundraising-facing.

This file is the distinct other job: building the financial artifacts an OUTSIDE investor reads and stress-tests - the model as a fundraising asset, the use-of-funds table, the cap-table and metrics narrative, and the financial slides in the deck. Same numbers as the internal model, packaged and defended for a partner meeting. The CEO owns the story and outreach (see ceo/references/investor-narrative-and-outreach.md); the CFO owns that every number in those materials is true, sums, and survives diligence.

## The Golden Rule: one source of truth

All investor materials must agree with each other. Before any fundraising financial is drafted, lock a single source of truth and write every later asset off it:

- traction metrics (ARR/MRR, growth, NDR, logo count, pipeline)
- pricing and revenue assumptions
- raise size and instrument (SAFE / priced round / note; cap, discount)
- use of funds
- team bios, titles, comp run-rate
- milestones and timelines

If two assets disagree on a number, STOP and resolve the conflict before drafting further. A deck that says $1.2M ARR and a model that says $1.05M is an instant-kill credibility problem in diligence. The CFO is the keeper of this source of truth across the deck, the model, the data room, and every email update.

## The financial model AS a fundraising asset

The internal operating model and the investor model are the same workbook with different framing. For the raise:

- **Explicit assumptions tab.** Every driver visible and labeled, never buried in a formula. Apply the standard model color convention (blue = input/assumption, black = in-sheet formula, green = cross-sheet/file link) so a partner opening the file sees in one glance what is an assumption vs a calculation.
- **Bear / base / bull cases.** Mandatory for a raise. Base is the plan you will be held to; bull is the upside that justifies the valuation; bear shows you survive a miss. Map each case to the same driver set (do not hand-tune outputs).
- **Clean layer-by-layer revenue logic.** Build revenue bottoms-up (units x price x conversion x retention), never as a top-down "1% of a big TAM." The layers must be inspectable and must sum.
- **Milestone-linked spending.** Every major spend ties to a milestone the raise funds. "We hire 4 engineers in Q3 to ship X, which unlocks Y revenue in Q1." Spending that is not milestone-linked reads as burn without a plan.
- **Sensitivity analysis where the decision hinges.** Where the investability of the round turns on one or two assumptions (CAC, conversion, churn), show the sensitivity table. This pre-empts the partner's "what if you are wrong about X" and signals you already stress-tested it.
- **Live workbook, not a screenshot.** Comps / DCF / scenario tables are delivered as a working Excel/Sheets model with live formulas and sensitivity tables. The model is the deliverable; a deck chart is a snapshot of it. Investors who ask for the model get the real thing.

Stress-test internally before it leaves the building: never show a model to investors before the internal team has tried to break it.

## Use-of-funds: the consistency spine

The use-of-funds table is where most decks contradict themselves. Discipline:

- It must **sum to the raise size**, exactly. Round-number sloppiness ("roughly") is a red flag.
- Every category ties to milestones and to the spending in the model. If the deck says "40% to engineering" the model's headcount build must reflect that allocation and that timeline.
- Express it as both allocation (%) and the runway/milestone it buys ("18 months to $3M ARR and Series A metrics"). Investors fund milestones, not line items.
- The use-of-funds, the model's spend plan, the milestone slide, and the runway claim are four views of ONE plan. Reconcile all four before delivery.

## Cap-table and metrics narrative

The CFO frames the numbers that tell the investability story:

- **Cap table:** present cleanly - current ownership, the new round's dilution, post-money, and option pool. Pre-empt the math: show pre-money, amount, post-money, and resulting investor ownership so the partner does not have to reverse-engineer it. Flag anything unusual (prior SAFEs stacking, advisor grants, founder vesting status) before they find it.
- **Metrics narrative:** lead with Tier 1 (ARR/MRR, growth rate, NDR, runway) - the same Tier-1-first discipline as internal reporting. Pair each metric with the comparable benchmark that makes it good (NDR >110% / >130%, LTV:CAC >3:1, CAC payback inside the segment band, Burn Multiple <2, Rule-of-40 path). A metric without its benchmark is a number; a metric next to "best-in-class is X, we are Y" is an argument.
- **Capital efficiency markers:** for the raise, surface burn multiple, months of runway the round buys, and revenue-per-dollar-raised. Efficiency is increasingly the differentiator; make it explicit rather than hoping the investor computes it.

## Deck financials (the CFO's slides in the deck)

Within the deck the CEO structures, the CFO owns the integrity of: traction, business model, financials/projections, the ask, and use-of-funds/milestones. For each:

- Traction slide: real, current, source-of-truth numbers; no vanity metrics dressed as revenue (keep one-time and recurring separate, never book TCV as ARR).
- Business model slide: unit economics that match the model (price, gross margin, CAC, payback).
- Projections slide: the base case from the model, shown as a clean trajectory, with the assumption drivers stated so it is defensible, not a hockey stick with no logic.
- Ask + use-of-funds: precise amount, instrument, and the milestone the money buys - reconciled to the table above.

## Red flags to kill before delivery

- Numbers that disagree across deck / model / data room / email update
- Use-of-funds that does not sum to the raise
- Fuzzy market sizing with no bottoms-up assumptions
- Revenue math that does not sum cleanly layer to layer
- Inflated certainty where the assumption is fragile (no sensitivity shown)
- TCV booked as ARR; one-time revenue inside recurring
- A single-scenario projection (no bear/base/bull) for a round
- A model shown to investors before internal stress-test
- Inconsistent team roles/titles between deck and cap table

## Quality gate (before any fundraising financial leaves the building)

- every number matches the current source of truth
- use-of-funds and revenue layers sum correctly
- assumptions are visible, not buried, and color-coded
- bear/base/bull present; sensitivity shown where the round hinges on it
- the cap-table math is pre-computed (pre/amount/post/ownership)
- the story the numbers tell is clear without hype language
- the model and every derived asset are defensible in a partner meeting

## Boundary

The CFO does NOT write the narrative arc, the cold/warm investor emails, or the investor update prose - that is the CEO (ceo/references/investor-narrative-and-outreach.md). The CFO supplies and guarantees the numbers those communications cite. When Solaris itself raises someday, this split holds: CEO tells the story and runs the process, CFO owns that the financials underneath it are true and survive diligence.
