# Filings + Market-Data Tooling (ABSORB sec-edgar / CONNECT yahoo-finance)

Absorbed/connected 2026-06-13. The CFO's core principle - "build models from source filings, not from memory; cross-check assumptions against comparables" - was previously a discipline with no data path. This file is that path. Methodology unchanged; this is the source-of-truth acquisition layer.

## 1. SEC filings - exact-precision analysis (ABSORB: stefanoamorelli/sec-edgar-mcp)

Source: stefanoamorelli/sec-edgar-mcp (**AGPL-3.0 - self-host/connect is fine; copyleft if redistributed as a service; commercial license available from the author**). Built on edgartools, **exact numeric precision via XBRL parsing** - not LLM-estimated numbers.

### Patterns to apply
- **Numbers come from XBRL-parsed filings, never from memory or a model's recollection.** The whole point of this tool is exact figures. When a 3-statement model needs a real company's actuals (comparables, a target in diligence, a public competitor benchmark), pull them from the filing, not from training data. This directly enforces the CFO "build from source" principle.
- **Filing-section extraction:** retrieve 10-K / 10-Q / 8-K and extract specific sections (MD&A, risk factors, segment data) rather than reading the whole document. Use 8-K for event-driven reads (guidance changes, M&A, exec departures).
- **Three-statement pull:** balance sheet, income statement, cash flow are XBRL-parsed individually - populate a comps model line-by-line from the actual statement, then your assumptions cross-check against these real comparables (the principle).
- **Insider-trading signal:** Form 3/4/5 transactions are exposed - material insider buying/selling is a qualitative signal for diligence on a public comparable or acquisition target.
- **Verification is built in:** every response includes the SEC filing URL. Cite it. A figure in a CFO deliverable that traces to a filing URL is defensible; one that doesn't is an assumption.

### Use vs not-use
- Use for: public-company comparables, competitor benchmarking, diligence on public targets, grounding industry assumptions in real disclosed numbers.
- Not for: Solaris's own private books (no SEC filings) - those come from the accounting system. This is the *external comparable* data source.

## 2. Market data - quotes/history (CONNECT: yahoo-finance-mcp)

Source: yahoo-finance-mcp (**MIT**). Free market data - prices, historical series, basic fundamentals.
- Use it for: current/historical prices for public comparables, quick market-cap and ratio sanity checks, beta/returns inputs for a discount-rate assumption.
- Caveat: Yahoo data is convenience-grade (delayed, occasionally gappy). Fine for assumption sanity-checks and comps context; for anything committed/audited, the SEC filing (sec-edgar) is the authoritative source. Never quote Yahoo as a primary figure in a deliverable when a filing exists.

## CONNECT - host install (auto-deploy does NOT install external MCP servers)
- **sec-edgar-mcp** (AGPL-3.0): `docker run -i --rm -e SEC_EDGAR_USER_AGENT="Name (email)" stefanoamorelli/sec-edgar-mcp:latest` (the SEC user-agent string is required by SEC fair-access policy). No API key. Self-host only; respect AGPL if ever served to third parties.
- **yahoo-finance-mcp** (MIT): host installs per its README; no key (uses public Yahoo endpoints). Free.
