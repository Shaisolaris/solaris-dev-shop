# G34 - Content discovery and conversion diagnostics (offline, saved snapshots)

`employees/marketing/seo-aso-specialist/page_diagnostics.py` reads a folder of saved HTML pages and a small JSON
config and reports metadata, sitemap, link and redirect, accessibility-basics and conversion-path findings.
Each finding has a severity, evidence and a concrete fix. With `--baseline` it diffs against an earlier report.
Method and limits: `employees/marketing/seo-aso-specialist/content-diagnostics.md`.

**Not run anywhere here:** fetching live pages or external links, redirects a real server sends, browser
rendering, CSS and contrast, Core Web Vitals, JavaScript-inserted content, screen-reader output, indexing and
rankings. Every site is synthetic and fictional (`*.example` hosts). This is not an ASO, website-publishing,
directory-submission or campaign tool.

## Commands (from the repository root, Python 3.9+)
```
T=employees/marketing/seo-aso-specialist/page_diagnostics.py; F=examples/capabilities/G34/fixtures
python3 $T $F/before/site --config $F/before/config.json --out /tmp/before.json      # exit 1: 29 findings
python3 $T $F/after/site --config $F/after/config.json --baseline /tmp/before.json   # exit 0: fixed 29, new 0
python3 $T $F/unseen/site --config $F/unseen/config.json --fail-on medium            # exit 1: 14 findings
python3 examples/capabilities/G34/diag_oracle.py                                     # exit 0: 14/14
python3 examples/capabilities/G34/diag_oracle.py --tool examples/capabilities/G34/noop_diagnostics.py   # exit 1
python3 examples/capabilities/G34/diag_oracle.py --tool examples/capabilities/G34/naive_diagnostics.py  # exit 1
python3 -m unittest tests.test_g34_capability                                        # 10 tests
python3 examples/capabilities/G34/make_fixtures.py /tmp/g34-fixtures                 # regenerates the fixtures
```

## Fixtures (`make_fixtures.py`, deterministic)
| Folder | What it is | Declared findings |
|---|---|---|
| `clean/` | small library site, every check satisfied (clean control) | none |
| `before/` | product site with seeded defects; each injection declares its finding key | 29 (high 11, medium 12, low 6) |
| `after/` | the same site with every defect corrected | none; versus before: fixed 29, new 0 |
| `unseen/` | a different site of traps: correct-but-unusual markup that must not be flagged, plus defects `before/` lacks (case-only link mismatch, redirect chain and loop, non-UTF-8 bytes, malformed markup, foreign canonical, two canonicals, FAQPage in `@graph`, missing conversion page) | 14 |

The expectations come from the generator, not from the tool's output. The traps include empty alt, image-only
links named by alt, aria-labelledby buttons, wrapped labels, hidden inputs, `#top`, `/docs` without a slash,
mailto/tel/javascript links, unquoted upper-case tags, `<a name>` anchors, entity-encoded titles and
percent-encoded file names.

## Oracle (`diag_oracle.py`, works on temporary copies)
| Id | Check |
|---|---|
| o1 | clean control: no findings, complete, exit 0 |
| o2 | before: exactly the 29 declared keys |
| o3 | after: none, and the baseline diff says all 29 fixed, none new |
| o4 | unseen: exactly the 14 declared keys, no trap flagged |
| o5 | every finding has severity, area, evidence and a fix |
| o6 | repeated runs give byte-identical JSON and text |
| o7 | the snapshot folders are unchanged after every run |
| o8 | a symlink out of the snapshot and a symlinked folder are skipped and named, the rest scanned, exit 3 |
| o9 | a page over `--max-bytes` is skipped and named, exit 3 |
| o10 | a failed run keeps the earlier `--out` byte-identical, a good run replaces it, no temp file left |
| o11 | usage errors exit 2 and write nothing (out inside snapshot, bad config, missing site, missing out folder) |
| o12 | `--fail-on` thresholds follow the severities found |
| o13 | scale: 2,000 generated pages in 20 folders, exactly the generated defects |
| s1 | static: the tool imports no network module |

The mid-write path (a failing `os.replace`) is fault-injected in `tests/test_g34_capability.py`, together with
exit-code precedence, config and baseline validation, URL resolution and redirect rules, and one test that fires
each check id the fixtures do not reach. Every one of the 43 check ids is covered.

## Results (macOS, Python 3.9.6; raw logs in the handback)
- Tool 14/14. No-op control 3/14: it passes only o6, o7 and s1, which a do-nothing tool satisfies. Naive
  control 9/14: it ignores redirects (o2 to o4), follows a symlink out of the snapshot (o8) and has no size cap
  (o9).
- Scale: 2,000 pages, 469 findings, about 0.2 s for the scan in a single run. This only shows the tool is cheap
  on a snapshot of that size; it says nothing about crawl or page speed.
