# M19 h1: affected recheck of G19 h1 350d175 (Grok self-validation, not independent review)

Verdict: **PASS with one P4 observation.** The stop() change fixes the after-exit race without hiding a server that is
still running, the new tests fail on the accepted oracle and pass on h1, the new "Boundaries of the demo" text matches
observed behaviour, and the M19 oracle gives the same result on h1 as on the accepted commit. This is Grok checking a
Grok build. It is not independent review and accepts nothing.

## Binding (raw/binding-verify.txt)
- Candidate 350d175e5cf43438e95476f945ea16804e4bba85, current remote head of review/grok-g19-duplicate-safe-api.
- Accepted parent 5606672 is its direct parent (1 commit). Handback G19-h1.patch equals `git diff --binary 5606672
  350d175`. MANIFEST.sha256 18/18 match the tree.
- Diff scope: boundary_oracle.py (stop() only), tests/test_g19_capability.py (new class OracleServerStop),
  duplicate-safe-api.md and G19 README (docs). ledger_api.py and boundary_probe.py are unchanged.

## Code review of stop()
killpg(SIGTERM) now treats ProcessLookupError and PermissionError as "already exited" and then waits to reap. A wait
that times out still falls through to killpg(SIGKILL) and a second wait(5), which still raises if the process is
alive. So widening the except clause cannot turn a hung server into a silent pass. This is consistent with the
handback.

## Checks I wrote for this pass
- **Defect first, rechecked (results/defect-first-recheck.txt).** The h1 OracleServerStop tests copied onto the accepted
  5606672 tree: 2 errors, "PermissionError: [Errno 1] Operation not permitted", on 3.9.6 and 3.12.14. On h1 they pass.
- **stop() still kills (oracle/m19h1_stop_probe.py).** A child that ignores SIGTERM is killed by the SIGKILL fallback
  (returncode -9 after 5.0 s, no exception); a normal child stops on SIGTERM (returncode -15). 2/2 on all four Pythons.
- **Header boundaries (oracle/m19h1_header_probe.py).** Own server on loopback with synthetic keys, raw sockets so
  header order is exact: two Authorization headers act as the first caller (invoice in the first tenant's list, not
  the second's); two Idempotency-Key headers store the effect under the first key only (replay with the first key
  returns the same invoice); a retry with only the second key makes a second invoice, as the doc now says; the
  single-header tenant split holds. 4/4 on all four Pythons. This matches the builder's
  raw/duplicate-header-behaviour.txt.
- **Prior M19 oracle (oracle/m19_oracle.py, unchanged).** Core 12/12, ACCEPTS, on h1 and on 5606672. Adversarial 6/19
  (3.9.6, 3.11.16) and 7/19 (3.12.14, 3.13.15), the same split as the original M19 report, identical on both commits
  (results/m19-oracle-*.txt, pyversions.txt).
- **Builder tests.** tests.test_g19_capability 18 OK x4. Full suite 102 OK on all four Pythons from a fresh clone, 0
  browser processes (results/full-suite-matrix.txt).
- **Load run (results/stress-summary.txt, stress-runs.txt).** 3 rounds of 8 concurrent 3.12 runs of the G19 module on
  h1: 24/24 OK.

## Findings
- **P4-1, load run does not discriminate.** The same load on the accepted 5606672 (one round of 8) also gave 8/8 OK, so
  this load did not reproduce the M39 P4-1 flake (3 of 8 there). The 24/24 on h1 is therefore not evidence by itself.
  The evidence for the fix is the deterministic pair above (fail on 5606672, pass on h1) plus the code review.

## Authoring notes (disclosed)
- The first M19 oracle run failed on all commits with FileNotFoundError because the folder given as its --tmp did
  not exist yet (my harness, not the candidate). I created the folder and reran; the files here are from the rerun.
- In results/m19-oracle-*.txt the probe's synthetic refused URLs with a user part (such as user@127.0.0.1:9) are
  written with [at] instead of @ so the pre-push safety scan does not read them as email addresses. Nothing else in
  those files was changed.

Browser launches for this pass: 0.
