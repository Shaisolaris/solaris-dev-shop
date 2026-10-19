# G33: product choice from conflicting evidence (product manager, market researcher, CMO)

Tool: `employees/product-project/product-manager/evidence_decision.py` (stdlib, Python 3.9+, local files
only). Rules and package format: `employees/product-project/product-manager/evidence-product-decision.md`.
All data here is synthetic. Nothing is sent; reports are drafts for the owner.

## Demo (from the repository root)

```bash
python3 employees/product-project/product-manager/evidence_decision.py decide examples/capabilities/G33/fixtures/choice.json
python3 employees/product-project/product-manager/evidence_decision.py decide examples/capabilities/G33/fixtures/choice.json --json
python3 examples/capabilities/G33/evidence_oracle.py   # ACCEPTED 9/9
python3 examples/capabilities/G33/evidence_oracle.py --tool examples/capabilities/G33/naive_decision.py   # REJECTED 1/9
python3 examples/capabilities/G33/evidence_oracle.py --tool examples/capabilities/G33/noop_decision.py   # REJECTED 1/9
```

## The clinic options fixture, worked by hand

Options: **portal**, **ai-schedule**, **reports**. Dimensions: pain 0.45, fit 0.30, proof 0.25 (proof has
metric_scale thresholds 1, 5, 10, 50, 100). Claims C1-C13 over interview snapshots (`sources/*.txt`), one
external market note (`S-mkt`, mutable, max_age_days 30, retrieved 2026-06-01 so 127 days old as of
2026-10-06) and a G13 reconciliation (`S-g13` → `g13/`, clean fixture; `g13-gaps/` for the low-confidence
path).

Clean result: **PREFERRED portal** with totals low 3.5000 / high 3.9500 / point 3.8214. Pain cell for portal
is mean 4.7143 (low 4, high 5, no conflict). Excluded: C9 (segment outside ICP mid-size clinics) and C10
(stale S-mkt). ai-schedule totals 0.9500 across the board; reports has unknown proof (1.0500-2.3000, point
null). C8 from G13 stays high confidence on the clean contract.

Changing interview scores so portal no longer dominates, or leaving an option with an empty dimension,
yields `no_robust_choice` with `deciding_evidence`. Editing a snapshot, inventing a quote, mismatching a
G13 value or stating a score that disagrees with the metric scale blocks those claims.

## Oracle

`evidence_oracle.py` copies the fixtures to a temporary folder and checks: the clean preference and
exclusions (o1); snapshot, quote, value and G13 mismatches (o2); preference flips and overlapping ranges
(o3); crash-style recovery around `--out` (o4); unknown dimensions, fresh mutable sources, G13-with-gaps
and top-level TAM refusal (o5); invalid packages write nothing (o6); `--out` / `verify` / tamper / keep
earlier result (o7); 40 seeded unseen packages whose totals and preference match an independent reference
(o8); no network, mail or process use and fixtures byte-identical (s1). `--seed N` changes the unseen
packages. The naive control (point mean, no source checks) and the no-op control both fail.
