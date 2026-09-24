# financial-analysis - official finance plugin methodology (absorbed)

Source: anthropics/financial-services-plugins (https://github.com/anthropics/financial-services-plugins). Apache-2.0, official, verified live + actively expanded 2026 (Cowork PowerPoint/Excel support added). ABSORB (Apache-2.0, attribution-clean). Land the `financial-analysis` core first; investment-banking / equity-research / private-equity / wealth-management remain queued.

## Scope absorbed now: financial-analysis core
- Financial statement analysis: common-size + trend + ratio analysis (liquidity, leverage, efficiency, profitability, coverage).
- Valuation: DCF (FCFF/FCFE, WACC build, terminal value via Gordon + exit-multiple, sensitivity), comparable-company + precedent-transaction multiples, football-field summary.
- Modeling discipline: three-statement linkage, driver-based assumptions, scenario/sensitivity tables, circularity/iterative-calc handling, audit checks (balance-sheet ties, cash ties).
- Outputs: Excel models + PowerPoint board/IC decks (the plugin's Cowork doc support), with assumptions stated and sources cited.

## Methodology rule
Every model states its assumptions, separates inputs from calcs from outputs, and carries audit ties. Never present a valuation without its sensitivity range and stated discount-rate basis. Finance advice stays informational (not personalized investment advice).

## Queued (not landed this pass)
investment-banking, equity-research, private-equity, wealth-management plugins from the same official source - absorb in a later pass.
