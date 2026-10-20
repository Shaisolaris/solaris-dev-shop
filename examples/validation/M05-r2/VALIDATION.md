# M05 r2: G05 r2 and r3 on the current head 04b3cf2 (Grok self-validation, not independent review)

Verdict: **PASS after one repair.**
- The first run on G05 r2 3056378 found a P2. The repair was a fast-forward builder fix, G05 r3 04b3cf2. This
  recheck passes on it.
- M05 P3 (waiver-closed findings) is closed. M05 P4-1 is unchanged.
- This is Grok checking a Grok build. It is not independent review and accepts nothing.

## What is being checked
- M05 validated 8b38a72.
- Since then:
  - 3056378 G05 r2: waiver-governed closure stays current and reopen refuses (root finding: a valid waiver-closed
    finding was reported UNBOUND_CLOSURE and reopened).
  - 04b3cf2 G05 r3: the repair below.
- Binding (raw/binding-verify.txt):
  - 04b3cf2 is the current remote head.
  - The G05 r3 patch equals `git diff --binary 3056378 04b3cf2`. The manifest matches.

## Probe written for this pass (oracle/m05r2_probe.py)
In-process, with my own finding and waiver.
- **V0:** setup. A valid waiver closes the S1 finding.
- **V1:** the root finding. While the waiver is valid, the closure is current at two revisions and reopen is
  refused.
- **V2:** after the waiver's expiry (as_of later than expires_at), the closure is not current and reopen works.
- **V3:** the waiver record is now rejected, or expired by status. Same expectation as V2.
- **V4:** a different waiver record.
- **V5:** no record given.
- **V6:** a non-waiver closure is current and stale as before, and reopen works.
- **V7:** UNBOUND_CLOSURE.
- **V8:** control. A waiver for another finding cannot close it.
- **V9:** the doc states the expired case.

Results:

| Head | Probe score | Failing rows |
|---|---|---|
| G05 r3 04b3cf2 | 11/11 on 3.9.6, 3.11.16, 3.12.14, 3.13.15 | none |
| G05 r2 3056378 | 5/11 | V2, V3 x2, V4, V5, V9 |
| G05 r1 8b38a72 | 6/11 | V1 and the waiver rows |

## Finding on G05 r2, fixed in G05 r3
- **P2-1: an expired or revoked waiver kept a blocking finding closed and current forever, and it could not be
  reopened.**
  - On 3056378, `closure_is_current` returned (True, []) for any closure with a waiver_id, and `reopen_finding`
    returned WAIVER_GOVERNS. Neither function took or checked the waiver.
  - After the waiver expired (V2) or was revoked (V3), the S1 finding stayed closed, was reported current at every
    revision, and reopen refused.
  - M05's original P3 failed closed (it reopened too much). The r2 fix failed open past expiry, against the doc
    ("until it expires") and the root finding ("closure and expiry consistently in both functions").
  - Repair: G05 r3 04b3cf2 (see grok-output/G05-r3).
    - Both functions take the waiver record and run validate_waiver.
    - With no record they refuse (WAIVER_RECORD_REQUIRED). A mismatched record gives WAIVER_MISMATCH.
    - The new tests fail on 3056378. The r2 test now passes the record (disclosed).

## Earlier and builder checks on 04b3cf2
- **M05 oracle (unchanged):** 19/20 on all four Pythons. The one failure is the same C06 adjudicated in M05 (an empty
  digests map, P4-1).
  - OBS row C17c now shows the waiver closure needs its record (WAIVER_RECORD_REQUIRED) instead of UNBOUND_CLOSURE.
- **binding_oracle:** 16/16 on all four Pythons. naive scores 6/16 and no-op 3/16.
- **Full suite on fresh clones:** 158 OK on all four Pythons. Browser 0.

## Residuals
- **P4-1 (from M05, unchanged):** an empty `digests` map is rejected as malformed. The doc should say digests must be
  nonempty.
- **OBS-1:** callers on the r2 form `closure_is_current(f, rev)` now get WAIVER_RECORD_REQUIRED for waiver closures.
  This fails closed, but it is an API change that callers must know about.
- **OBS-2:** a finding record stores the waiver id only. The caller supplies the waiver record, and its truth is the
  caller's, as for every declared record in G05.

Browser launches for this pass: 0.
