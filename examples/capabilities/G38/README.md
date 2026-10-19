# G38: repository and legal authority consistency (synthetic)

Two local checks, read-only towards what they examine:

- `employees/quality-security/security-auditor/provenance_check.py`: license declarations against the LICENSE
  text, NOTICE coverage of upstream license files, and a sha256 manifest against the files, hashed with G05's
  `artifact_digests`.
- `employees/engineering/blockchain-developer/event_chain.py`: a synthetic hash-chained event log with append,
  verify (optionally against an anchor) and recover to a new file.

Neither gives a legal opinion or authenticates anyone; names in files stay claims. No wallet, key, transaction,
network or process is used.

## Run

```
python3 employees/quality-security/security-auditor/provenance_check.py check examples/capabilities/G38/fixtures/repo-clean --manifest examples/capabilities/G38/fixtures/repo-clean/MANIFEST.sha256   # exit 0
python3 employees/quality-security/security-auditor/provenance_check.py check . --exclude examples/capabilities/G38/fixtures   # exit 0
python3 employees/quality-security/security-auditor/provenance_check.py check .   # exit 1
python3 employees/engineering/blockchain-developer/event_chain.py verify examples/capabilities/G38/fixtures/events.jsonl --anchor 2:385371e6751915d9397db981ee2887233f845c173e058a79ea097719f90ec20b   # exit 0   # exit 0
python3 examples/capabilities/G38/authority_oracle.py   # ACCEPTED 8/8
python3 examples/capabilities/G38/authority_oracle.py --tools examples/capabilities/G38/naive   # REJECTED 1/8
python3 examples/capabilities/G38/authority_oracle.py --tools examples/capabilities/G38/noop   # REJECTED 1/8
```

Worked results:

- The clean fixture: consistent, LICENSE MIT, 4 declarations, 8 of 8 manifest files match.
- The actual repository at this revision: consistent, MIT in LICENSE, pyproject, 61 plugin.json files and the
  README badge and section (64 declarations), once the G38 fixture folder is excluded. Without the exclusion the
  fixture's own LICENSE and LICENSE-upstream are reported as upstream_license_unlisted: the check does not hide them.
- The event fixture: 6 events, head seq 5; claimed_by "Release desk (synthetic)" 3 and "Build bot (synthetic)" 3,
  reported as not authenticated.

## Oracle

`authority_oracle.py` computes its own expectations with hashlib. p1: the clean fixture and the actual repository,
with and without the fixture exclusion. p2: nine single-cause license drifts (plugin, pyproject, badge, section,
unlisted COPYING, NOTICE naming a missing file, unrecognised LICENSE text, Apache LICENSE under MIT declarations,
a plugin without a license), each giving exactly its finding. p3: changed, missing, symlinked and escaping manifest
entries; a malformed manifest refused with an earlier report kept. e1: the fixture chain against an independent
recompute, with an anchor. e2: on 4 seeded chains of 40 to 400 events, an edit, a deletion, a swap, a replay, a
torn tail, an unanchored rewrite (passes: self-consistent only), an anchored rewrite and an anchored truncation,
each named at its line with nothing after it trusted. e3: recovery to a new file, refusals, append to a broken log
refused, and an anchored rewrite recovering nothing. e4: 8 concurrent appenders of 25 events each give 200 verified
events. s1: no network, process, wallet or chain library use; fixtures byte-identical. `--seed N` changes e2.
The naive control (first line of LICENSE, JSON-and-seq only, no lock) and the no-op control fail.
