# Provenance and integrity check (provenance_check.py)

Local, read-only consistency of what a repository says about its license and its files.

```
python3 provenance_check.py check ROOT [--manifest FILE] [--exclude DIR ...] [--json] [--out FILE]
# 0 consistent, 1 findings, 2 invalid input (nothing written)
```

## What it checks

| code | when |
|---|---|
| license_missing | no readable root LICENSE |
| license_unrecognized | the LICENSE text matches neither the MIT nor the Apache-2.0 fingerprint; nothing is guessed and no declaration is compared |
| license_mismatch | pyproject `license`, a `plugin.json` `license`, the README badge or the README `## License` line names another license than the LICENSE text |
| license_undeclared | a pyproject or `plugin.json` has no license value |
| upstream_license_unlisted | a LICENSE*, LICENCE* or COPYING file below the root is not named in NOTICE.md |
| notice_path_missing | NOTICE.md names a license file that does not exist |
| artifact_missing / digest_mismatch | a manifest entry is absent, or its bytes differ |
| artifact_refused | a manifest entry is a symlink, a folder, or a path outside ROOT |

Manifest lines are `<sha256>  <relative path>` (the `shasum -a 256` format). Files are hashed by G05's
`artifact_digests` (`../assurance/quality_os.py`, loaded by path), and the matching digests are returned as
`integrity.subject`, a G05 subject binding that receipts can be checked against.

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
