# Content, link and conversion-path diagnostics on saved snapshots (G34)

`page_diagnostics.py` audits a folder of saved HTML pages plus a small JSON config and reports one row per
finding: `severity | check | page | evidence | fix`. It is the baseline-capture step of an audit, run before and
after a change so the delta is measured instead of asserted. Standard library only, Python 3.9 or newer.

## What it checks (43 check ids, see `CHECKS` in the script)
- **Metadata:** title present, single, 50-60 characters, not shared; meta description present, 150-160
  characters, not shared; one absolute canonical on this host that resolves; `lang`; viewport; JSON-LD parses,
  deprecated types (HowTo, SpecialAnnouncement) and restricted types (FAQPage) flagged; non-UTF-8 bytes.
  The length ranges are this role's HARD NUMBERS, so they are reported as Low, never as errors.
- **Sitemap:** missing or unparsable, entries that do not resolve, other hosts, noindex pages listed, indexable
  pages left out. Noindex pages need no canonical and may stay out of the sitemap.
- **Links:** broken internal links (with a "differs only in case" hint, because servers are case-sensitive even
  when a laptop is not), configured redirects (one hop Low, a chain Medium, a loop High), missing `#fragment`
  targets (`#top` is allowed), orphan pages, vague link text.
- **Accessibility basics:** one h1, no skipped heading levels, image alt (empty alt counts as decorative), link
  and button names (text, image alt, aria-label, aria-labelledby), form-control labels, duplicate ids.
- **Conversion path:** for each configured page, the goal page exists and a *named* link or form reaches it
  (through redirects if need be); form actions resolve.

## How to run
```
python3 page_diagnostics.py SITE_DIR --config config.json [--baseline old.json] [--out report.json]
        [--json] [--fail-on high|medium|low|none] [--max-bytes N]
```
`config.json`: `base_url` (required), `redirects` (`{"/old": "/new"}`), `conversion`
(`{"/pricing.html": {"goal": "/signup.html"}}`), `entry_pages` (default `["/index.html"]`, exempt from orphan).
Exit 0 clean at the threshold, 1 findings at or above `--fail-on` (default high), 2 usage or input error (nothing
written), 3 incomplete: a page was over `--max-bytes`, unreadable, or a symlink out of the snapshot (it is named
under `skipped`, the rest is still scanned). 2 wins over 3, 3 over 1. With `--baseline` the report adds
`fixed`, `new` and `persisting` finding keys.

## Safety
- No network module is imported; external links are counted, not fetched.
- Never writes inside the snapshot (`--out` there is refused). `--out` is written to a temporary file in the same
  folder and renamed, so a failed run leaves the previous report as it was.
- Symlinked files leading out of the snapshot and symlinked folders are not followed.
- Output is deterministic (sorted, no timestamps), so two reports can be diffed.

## Limits (say these in the deliverable)
Not checked: live pages, redirects the server really sends (only the configured map), external links,
rendering, CSS, contrast, Core Web Vitals, JavaScript-inserted content, screen-reader output, indexing and
rankings. A clean report is not an accessibility conformance claim. Inputs are the owner's own saved pages or
synthetic fixtures; this is not a crawler and must not be pointed at third-party sites.

The proof set is `examples/capabilities/G34` (clean control, before/after, unseen traps, failure variants,
scale run, no-op and naive controls).
