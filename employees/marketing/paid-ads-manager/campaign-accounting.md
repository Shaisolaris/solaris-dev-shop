# Campaign accounting without live spend (G35)

Tool: `campaign_ledger.py` (stdlib, Python 3.9+, local files only). It never opens an ad account, never
calls a network and never publishes, schedules, boosts or spends. Every number it prints comes from the
files in one campaign package.

## Package (`solaris.campaign-ledger/1`)
| Key | Meaning |
|---|---|
| `as_of`, `window` | reporting cutoff and the conversion window (timestamps with Z or an offset) |
| `spend.contract` | a G13 `csv_reconcile.py` contract over the platform spend export; it must define a `sum` metric `spend` by `campaign_id`, `day`, `currency`, so copies, restatements and late rows are settled by G13 |
| `orders.contract` | a G13 contract over the order book with a `sum` metric `revenue` by `order_id`, `currency`; its window must equal the package window |
| `finance.g14_package` | optional: the CFO's G14 `cash_revenue_reconcile.py` package, for the tie-out to recognized revenue |
| `campaigns` | `id`, `currency`, `flight_start`/`flight_end` (dates, inclusive), `budget_total`, `budget_daily` (two-decimal strings; floats are refused), `click_window_days` (1-90), `view_window_days` (0-30, 0 = no view-through) |
| `touches` | JSON lines: `touch_id`, `campaign_id`, `user`, `kind` (`click`/`view`), `at`, `loaded_at` |
| `conversions` | JSON lines: `event_id`, `order_id`, `user`, `at`, `loaded_at`, `source`; `value`/`currency` are what the pixel said and are only compared, never used |
| `creatives` | optional: draft creatives with the claims they make (below) |

Paths are relative and must stay inside the package folder. Unknown keys are schema drift and refused.

## Rules
1. **Duplicates.** Spend and orders are deduplicated by G13 (latest restatement per campaign and day; exact
   copies collapsed; loaded after `as_of` = late and named). Touch and conversion ids: an identical re-send is
   a copy; the same id with another body is a conflict, every version is dropped and named. A pixel event and a
   server event for one order are one conversion (the earliest time is used).
2. **Attribution.** For each order in the reconciled book that has a conversion event: the latest click by the
   same user at or before the conversion and no older than the campaign's click window; if none, the latest
   view inside the view window. Exactly 7 days counts; 7 days and one second does not; a touch after the
   conversion never counts; a touch outside the campaign's flight is ignored. Two campaigns with the latest
   touch at the same instant = `ambiguous_touch`, credited to neither.
3. **Value.** Order value comes from the order book, never from the pixel; differences are listed as
   `reported_value_differs`. A conversion whose order is not in the book (test, void, late, unknown) is named
   `conversion_without_order` and valued at nothing.
4. **Identities, per currency (no FX).** order-book value = attributed + every unattributed bucket
   (`no_conversion_event`, `no_eligible_touch`, `ambiguous_touch`, `user_conflict`, `currency_mismatch`);
   spend export total = campaign spend + unassigned spend. A broken identity is a finding.
5. **Budgets.** Spend equal to a cap is fine; one cent over is `over_daily_budget` / `over_total_budget`.
   Spend outside the flight is `spend_outside_flight`; spend for an unknown campaign is unassigned and named.
   These are accounting findings; the tool cannot pause or change anything.
6. **Ratios.** CPA = spend / conversions (2 decimals), ROAS = attributed revenue / spend (4 decimals), half-even.
   No conversions or no spend gives `null`, never 0 or infinity.
7. **Finance tie-out (G14).** Order value is compared with the CFO's recognized revenue per currency; a credit
   note shows as `order_value_differs_from_recognized_revenue` with the difference. ROAS stays on order value
   and says so; read it next to that difference.

## Creative review (truthful drafts)
Each creative: `id`, `campaign_id`, `channel`, `headline`, `body`, `claims` (`text` that appears in the copy
and a `figure` such as `campaign:C-search:roas`; figures: spend, conversions, attributed_revenue, cpa, roas,
budget_total), optional `material_connection` (`none`, `paid`, `gifted`, `employee`, `affiliate`, `unknown`)
and `disclosure`. Blocked when: any publish field (`publish_at`, `scheduled_at`, `ad_id`, `post_id`, ...) or a
status other than `draft`; a number in the copy outside a declared claim; a claim whose figure, rounded
half-even to the decimals written, differs from the computed one (2.4658 supports "2.47", not "2.46"); an
unknown figure; prohibited wording (guaranteed, risk-free, #1, ...); a paid, gifted, employee or affiliate
connection without a disclosure that appears in the copy; a social creative with no or unknown connection
status. A clean creative is `ready_for_human_review`; when the report has other findings it is
`held_unverified` until they are cleared. Nothing here publishes: a human does that in the platform.

## Output and exit
`reconcile PACKAGE [--json] [--out DIR]`. `--out` writes `report.json` and `campaign-brief.md` (labelled
INTERNAL DRAFT) atomically and must be outside the package folder. Exit 0 `reconciled`, 1
`reconciled_with_findings` (every finding named), 2 invalid: nothing is written and an earlier report stays.

## Limits
Synthetic user keys only; no cross-device, modelled, incrementality or platform-reported conversions. Spend is
the export, not the platform invoice. One window and one as-of per package. Events are held in memory (tested
at 20 000 orders, 36 035 touches and 29 159 conversion events; G13's limits apply to the CSV files).
