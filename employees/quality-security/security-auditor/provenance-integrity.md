# Provenance and integrity check (provenance_check.py)

Local, read-only consistency of what a repository says about its license and its files.

```
python3 provenance_check.py check ROOT [--manifest FILE] [--exclude DIR ...] [--json] [--out FILE]
# 0 consistent, 1 findings, 2 invalid input (nothing written; includes a missing --out folder or an --out that is a folder)
```

## What it checks

| code | when |
|---|---|
| license_missing | no readable root LICENSE |
| license_unrecognized | the LICENSE text is not the whole MIT or Apache-2.0 text (whitespace, case and quote style aside; MIT may carry its title and copyright lines, Apache its standard appendix word for word in either published bracket spelling, `{}` or `[]`); a copyright line, in MIT or in the appendix, must read `copyright [(c)] YEAR[S] HOLDER[.] [all rights reserved.]`, with no sentence inside the holder and none of the words that grant, limit or condition use (may, must, shall, not, no, only, unless, except, prohibit, forbid, permit, commercial, restrict, license, terms, conditions, software, use, without); a header, a fragment or added terms are unrecognised, nothing is guessed and no declaration is compared |
| license_mismatch | pyproject `license` (`license = "X"` or `'X'`, `license = { text = .. }`, `license = { file = .. }` or a `[project.license]` table; a file form is the license of the file it names), any `plugin.json` `license` under ROOT (chief-of-staff and employees/), the README badge or the README `## License` line (name may end at a comma or period) names another license than the LICENSE text |
| license_undeclared | a pyproject or `plugin.json` has no license value, or a pyproject license `file` is not a file inside ROOT |
| upstream_license_unlisted | a LICENSE*, LICENCE* or COPYING file below the root is not named in NOTICE.md |
| notice_path_missing | NOTICE.md names a license file that does not exist |
| artifact_missing / digest_mismatch | a manifest entry is absent, or its bytes differ |
| artifact_refused | a manifest entry is a symlink, a folder, or a path outside ROOT |

Manifest lines are `<sha256>  <relative path>` (the `shasum -a 256` format). Files are hashed by G05's
`artifact_digests` (`../assurance/quality_os.py`, loaded by path), and only the matching digests are returned as
`integrity.subject`, a G05 subject binding that receipts can be checked against. Digests of mismatched or refused files are left out of the subject.

`--exclude DIR` leaves a folder out of the license walk, for example a test fixture that is its own synthetic
repository. The report lists each excluded folder and the license files under it.

## What a clean result does not mean

- It is not a legal opinion. Whether licenses are compatible, what they require, or who owns the code is for
  legal-advisor (informational) and qualified counsel.
- It authenticates no one. Commit authors, `owner` fields and names in files are claims in plain text.
- It does not verify signatures or attestations. in-toto, SLSA and cosign checks need those tools; when they are
  not installed, report UNAVAILABLE.
- A manifest proves that the listed bytes are on disk. It says nothing about files it does not list, and it is
  only as trustworthy as the place the manifest itself came from.

## Revision note

The whole-text license match and the matching-only integrity subject come from generalizing the M38 proposed fix
(https://github.com/Shaisolaris/solaris-dev-shop/commit/994cb3d4a9a3aef41b1fd3ff872b846e5fb8f717),
plus small follow-ups for root-level plugin.json, comma-form README sections, and a clean error on a missing --out folder.

Revision r3 closes M38 r2 P2-1 (https://github.com/Shaisolaris/solaris-dev-shop/commit/87f964593a5a603d20b6af94c56afc8819037656):
added terms placed in a copyright line or in the Apache appendix were still accepted. The fix is generalized from
the M38 r2 proposed patch (Grok self-validation): the appendix is now compared as readable text in both bracket
spellings instead of one fixed-length hash, and copyright holders also may not use operative words. That word list
is a guard, not a parser: a restriction written without those words in a holder name still passes, so read any
unusual copyright line yourself. r3 also gives exit 2 for an --out that is a folder and reads the pyproject
`file =`, single-quoted and `[project.license]` forms (M38 r2 P4-1 and P4-2). The README bold-section form
(M38 r2 P4-3) and the OBS items are not changed. pyproject is read by pattern, not by a full TOML parser.

Revision r4 closes M38 r3 P2-1 (https://github.com/Shaisolaris/solaris-dev-shop/commit/11310a82709d6aa002f95e37a0ac7920f1bd125e):
plain restrictive wording that avoided the r3 words ("noncommercial purposes", "which cannot be resold", "personal
usage") still read as MIT, consistent. Now a holder is a name: after its first comma only a company suffix (Inc, LLC,
Ltd, GmbH, Corp, Co, PLC, AG, SA, BV), "and contributors" or "et al" may follow, and the word list also catches
words inside longer words and common restriction words (cannot, never, usage, purposes, resale, sold, exclusively,
redistribution and similar). It is still a guard, not a parser: a restriction with no comma and none of those words
can pass. So the report now lists every LICENSE copyright line it set aside before comparing
(`license_copyright_lines` in JSON, one "copyright line set aside" row in text); read those lines yourself before you
rely on a consistent result. The comma rule comes from the M38 r3 proposed patch (Grok self-validation).
