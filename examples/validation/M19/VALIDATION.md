# M19: validation of G19 "Duplicate-safe API and tenant boundaries"

**Kind:** Grok self-validation (same bot as the G19 builder). Not independent review. It was done adversarially:
- with an M19 oracle written for this pass from `duplicate-safe-api.md` only (`oracle/m19_oracle.py`), with its own principals and four unseen tenants, not derived from the builder's oracle, tests, probe or stubs;
- with 36 single-site mutants of `ledger_api.py` and 6 stubs (4 written for M19, 2 from the builder).

An independent reviewer is still required by the QA2 contract.

**Verdict: PASS** against candidate commit `5606672b464f5daaf08e28cbfa5a8d307f730c27` (branch `review/grok-g19-duplicate-safe-api`, parent and base `02ba9c571b10ad1dba792d2ac5534bcad3171e67`, subject "G19: duplicate-safe API and tenant boundaries (review only)"). The candidate manifest verified 18/18, and its file set equals the diff file set (`raw/manifest-verify.txt`).

What holds:
- The M19 core checks pass 12/12 on 3.9.6, 3.11.16, 3.12.14 and 3.13.15: duplicates, concurrent retries, overspend races, crash and recovery, tenant reads, writes and enumeration, key scope, auth, check command and seeded load.
- The suite passes (16 G19, 84 other, 100 total) on all four interpreters.
- A fresh caller using only the documented commands succeeds on 3.9.6 and 3.12.14.
- The M19 oracle kills 36/36 mutants.

There is no P1 or P2 finding, so no proposed-fix patch is included. The findings are:
- 2 at P3: the `check` command misses three kinds of unrecorded effect; duplicated Authorization and Idempotency-Key headers are resolved silently.
- 6 at P4: unhandled odd inputs, HTML error pages, no read timeout, a burst over the listen backlog, `--host ::1`, and the builder oracle hanging on one mutant.
- An evidence-strength note: the builder's oracle and tests are weaker than the handback says.

Runs were on host macOS (arm64) on 2026-10-18 between 14:11 and 15:30 PT. Python 3.12.14 was used unless stated.

## Isolation
- The candidate was fetched with `git fetch origin review/grok-g19-duplicate-safe-api` (FETCH_HEAD `5606672b...`, `raw/fetch.txt`). It was checked out as a detached worktree at `/tmp/m19-eval` (`raw/worktree-add.txt`).
- All runs used `/tmp` copies: mutants are APFS clones in `/tmp/m19-mutants`, and oracle databases live in per-run temp directories. The candidate worktree had 0 status lines after every interpreter run (`raw/pyversions-matrix.txt`).
- Nothing was written to the week-grok working tree. Its branch, HEAD, index hash and status hash were recorded before (`raw/weekgrok-before.txt`, `raw/weekgrok-status-before.txt`) and after (`raw/weekgrok-after.txt`, `raw/weekgrok-status-after.txt`).
- No candidate file was modified. Defects are reported, not fixed.

## Acceptance items (M19 oracle core checks, `raw/oracle-candidate-<version>.txt`)
| Check | What it proves | 3.9.6 | 3.11.16 | 3.12.14 | 3.13.15 |
|---|---|---|---|---|---|
| k1 clean control | create, replay, get, list, pay, pay rest and void exact; 409s; Location and Idempotent-Replayed | PASS | PASS | PASS | PASS |
| k2 concurrent replays | 48-way create replay (first attempts, all 201): 1 invoice; 32-way payment replay paid once; same key with 2 bodies gives 1 effect, losers 422 | PASS | PASS | PASS | PASS |
| k3 overspend race | 20-way 300-on-1000: exactly 3 accepted, paid 900; stored 409 stays 409 | PASS | PASS | PASS | PASS |
| k4 cross-tenant reads | other tenants' reads byte-identical to a missing id; lists never leak; foreign cursor equals a made-up cursor | PASS | PASS | PASS | PASS |
| k5 cross-tenant writes | cross-tenant pay and void equal a missing id; tenant fields refused; tenant headers and `?tenant` ignored | PASS | PASS | PASS | PASS |
| k6 key scope | keys scoped per tenant; reuse with another body, endpoint or invoice gives 422 | PASS | PASS | PASS | PASS |
| k7 auth | 7 bad credentials 401, viewer writes 403, nothing changed | PASS | PASS | PASS | PASS |
| k8 crash and recovery | fault plans before and after commit; exit 70; kill -9 mid-burst of 64, then retries give exactly 64 | PASS | PASS | PASS | PASS |
| k9 check command | clean is consistent and read-only; paid tamper and duplicated audit row exit 1; garbage exit 2 | PASS | PASS | PASS | PASS |
| k10 invalid input | non-loopback hosts and bad principals exit 2; 28 invalid requests exact | PASS | PASS | PASS | PASS |
| k11 enumeration | ids random; other tenants' ids answer byte-identical to random ids | PASS | PASS | PASS | PASS |
| k12 seeded load | duplicate-laden load over 4 tenants and 16 threads matches the model (seeds 7, 2026, 31337) | PASS | PASS | PASS | PASS |

Adversarial checks x1 to x19 are findings only and never change the core score. The candidate rejected the attack in 6/19 (3.9.6 and 3.11.16) or 7/19 (3.12.14 and 3.13.15). The difference is x3, below.

## Findings
All findings come from the candidate run on each interpreter. Repro one check on a fresh candidate tree `T` with interpreter `PY` (from `/tmp`):

```
PY oracle/m19_oracle.py --only x10,x11,x12 --probe T/employees/quality-security/security-auditor/boundary_probe.py -- PY T/employees/engineering/backend-developer/ledger_api.py
```

Replace the `--only` list with the check names given for each finding.

No finding is P1 or P2: no duplicate effect, cross-tenant read or write, overspend or lost write was found under any burst, crash or interpreter.

### C1 (P3): `check` reports "consistent" for three kinds of unrecorded effect (x10, x11, x12)
The doc offers `check` as the way to confirm stored state has no duplicate or missing effects. It exits 0 "consistent" for:
- **x10:** an invoice row with no idempotency record and no audit row (what an unrecorded second create leaves behind).
- **x11:** a created invoice deleted while its idempotency record and audit row remain.
- **x12:** a duplicated payment row with `paid_cents` raised to match (a double charge without its own key).

`check` does catch `paid_cents` tampering and duplicated audit rows (k9). These rows were written straight into the database. The API itself never produced them in any M19 run. So this is a detection gap, not a live defect. The likely fix is to cross-check that every invoice and payment row has exactly one idempotency record and one audit row, and the reverse.

### C2 (P3): duplicated Authorization and Idempotency-Key headers are resolved silently (x6, x7)
- **x6:** with two Authorization headers (marlow first, kestrel second), the first wins. A create landed in the marlow tenant. A proxy that authorises on the last header would disagree with the API about the tenant.
- **x7:** two different Idempotency-Key headers are accepted using the first. A later request with only the second key created a second invoice, so one logical request can produce two effects when a client or proxy duplicates the header.

Rejecting a repeated Authorization or Idempotency-Key header with a 400 JSON error would remove both.

### C3 (P4): odd inputs drop the connection without an answer (x1, x2, x3)
- **x1:** `limit=` with a superscript two (`%C2%B2`) drops the connection with no response (an unhandled ValueError). Arabic-Indic and fullwidth digits are accepted as numbers, which is harmless.
- **x2:** `Content-Length` with a superscript two gets no response. Arabic-Indic three gets a stdlib 411.
- **x3:** an 8000-deep JSON array and a 2500-deep object (under the 16 KiB body limit) drop the connection on 3.9.6 and 3.11.16, where RecursionError is unhandled. On 3.12.14 and 3.13.15 they get 400 and 422 JSON errors.

In all three the server stays up and nothing is written.

### C4 (P4): some errors are stdlib HTML pages, not `{"error": ...}` (x4, x5)
The doc says "Errors always use {error:{code,message}}". HEAD, OPTIONS, TRACE and unknown methods return the stdlib 501 HTML page (HEAD with an empty body). A malformed request line and a too-long URI return stdlib HTML 400 and 414 pages.

### C5 (P4): no read timeout on client sockets (x13)
40 clients that sent 1 of 200 body bytes were all still held open after 20 s. A normal create was still served in about 0.00 s, because the server is threaded, so this is resource use, not an outage, on a loopback-only service.

### C6 (P4): a 256-connection burst exceeds the listen backlog (x14)
256 simultaneous replays of one create gave 26 to 38 resets or refusals (3.9.6: 26, 3.11.16: 33, 3.12.14: 29, 3.13.15: 38). Exactly 1 invoice was made, so retry safety holds. The client sees connection errors and must retry.

### C7 (P4): `--host ::1` is refused (x15)
The doc allows loopback hosts, but `--host ::1` exits 2: `cannot listen on ::1:0 (nodename nor servname provided, or not known)`. The server binds only IPv4. Either support IPv6 loopback or document 127.0.0.1 only.

### C8 (P4, tooling): the builder oracle has no timeout
On mutant `replay_ignored` the builder oracle gave no answer after 10 minutes. I killed it (oracle pid 57019 and its server pid 57052) and recorded this in `raw/builder-oracle-vs-teeth.txt`. That mutant is counted as not accepted. A grader that can hang turns a broken candidate into a stalled pipeline instead of a REJECT.

### E1 (evidence strength): the builder oracle and tests are weaker than the handback says
The handback says the G19 tests kill 14/14 and the builder oracle kills 12/14 of its own 14 mutants. Against the 36 M19 mutants on 3.12.14:
- the builder tests kill 33/36;
- the builder oracle kills 26/36.

The survivors are listed under "Oracle teeth". The candidate's own behaviour is not affected. The M19 oracle covers every survivor.

### Checks where the attack was rejected (OK)
- **x8:** auth scheme case. `bearer` and `BEARER` give 401. This is an observation only: RFC 7235 says the scheme is case-insensitive, but the doc says `Bearer`.
- **x9:** path confusion. Ten path, case, encoding and absolute-form variants for another tenant's id all give 404.
- **x16:** probe URL guard. All 10 non-loopback or odd base URLs exit 2 before sending.
- **x17:** probe teeth. `boundary_probe` exits 0 on the candidate, 1 on the vulnerable, racy and naive stubs, and 3 on the noop stub.
- **x18:** pay and void race. In 5 rounds of 10 payments racing 10 voids, no round was inconsistent.
- **x19:** two server processes on one database, with 32 concurrent duplicates split across them, made 1 invoice and `check` stayed consistent.

## Oracle teeth (`raw/oracle-teeth.txt`, `raw/builder-oracle-vs-teeth.txt`, `raw/builder-tests-vs-mutants.txt`, 3.12.14)
`oracle/make_mutants.py` makes 36 mutants. Each is one exact, single-occurrence edit of `ledger_api.py`, and the script stops if an anchor is missing or not unique. The mutants cover:
- idempotency: replay, BEGIN mode, fingerprint parts, stored conflicts and errors, key scope and the replay status and header;
- tenancy: find, list and cursor scope, other-tenant 403 and trusted tenant headers;
- auth: any bearer, viewer writes, optional key;
- money: overspend, paying closed invoices, voiding paid ones, status stays open, bool amounts;
- the check command: audit and paid checks skipped;
- shape: duplicate JSON keys, extra fields, body limit, Location, next_after, smuggling error code;
- binding and ids: non-loopback bind, sequential ids;
- recovery: the fault point swapped around the commit.

| Subject | M19 oracle (12 core) | Builder oracle (10) | Builder tests (16) |
|---|---|---|---|
| candidate | 12/12 ACCEPT | 10/10 accept | OK |
| M19 stub noop / naive / vulnerable / racy | REJECT (1, 4, 2, 6 pass) | reject (2, 4, 2, 5 pass) | n/a |
| builder noop_stub / vulnerable_stub | REJECT (0, 0 pass) | reject (0, 1 pass) | n/a |
| **36 mutants killed** | **36/36** | **26/36** | **33/36** |

Mutants the builder oracle accepts (10/10 checks pass):
- check_audit_skipped
- check_paid_skipped
- errors_stored
- fingerprint_no_iid
- key_optional
- pay_audit_dropped
- pay_closed_allowed
- sequential_ids
- smuggle_code_lost
- void_paid_allowed

It hung on replay_ignored (C8), which is counted as killed only because it gave no ACCEPT.

The builder tests accept (pass) three mutants: check_audit_skipped, fingerprint_no_iid and sequential_ids.

The handback claims the tests kill 14/14 and the oracle 12/14 of the builder's own 14 mutants. Its mutant set was not rerun here.

## Fresh caller (`oracle/m19_fresh_caller.sh`; `raw/fresh-caller.txt` on 3.12.14, `raw/fresh-caller-py39.txt` on 3.9.6)
The fresh caller uses `env -i` and bash, only the documented commands, and two unseen tenants (`brackwater`, `fenmoor`). It ran four steps:
1. The doc's "Run it" block with placeholders filled. The same invoice was returned twice; the other tenant's list was empty; `boundary_probe` exited 0 with 0 findings; `check` exited 0.
2. The "Restart and retry drill" (crash after commit). The server exited 70; after a restart the retry answered `201` with `Idempotent-Replayed: true`.
3. The crash-before-commit drill. The server exited 70; after a restart the retry answered `201` with `Idempotent-Replayed: false`. Each drill invoice exists once.
4. `check --json` gave `ok True`, `violations []`, and per-tenant counts.

Both interpreters gave the same output apart from ports and random ids.

## Interpreter matrix (`raw/pyversions-matrix.txt`)
| Python | M19 core | Adversarial findings | G19 tests | Other tests | All tests | Candidate tree clean |
|---|---|---|---|---|---|---|
| 3.9.6 (/usr/bin/python3) | 12/12 | 13 | 16 OK | 84 OK | 100 OK | yes |
| 3.11.16 | 12/12 | 13 | 16 OK | 84 OK | 100 OK | yes |
| 3.12.14 | 12/12 | 12 | 16 OK | 84 OK | 100 OK | yes |
| 3.13.15 | 12/12 | 12 | 16 OK | 84 OK | 100 OK | yes |

The only difference is x3 (C3): deep JSON is handled on 3.12 and later and drops the connection on 3.9 and 3.11.

## Rejected and superseded runs (kept)
- `raw/oracle-candidate-run1-harness.txt` (REJECTED). The x3 object case was over the 16 KiB body limit, so it tested 413, not nesting. The depth was lowered to 2500 and the criterion became "any 4xx JSON error". The x1 criterion was narrowed to "a finding only if a request gets no answer". An x18 criterion bug (10 x 100 on 1000 correctly makes the invoice `paid`) was fixed.
- `raw/oracle-teeth-v1-superseded.txt` (SUPERSEDED). The v1 oracle killed 34/36: `deferred_begin` and `fingerprint_no_iid` survived. v2 added first-attempt burst checks (k2, k3) and a payment-key-on-another-invoice check (k6), and kills both. The candidate passes v1 and v2.

## Limitations
- Mutant teeth were run on 3.12.14 only. The candidate itself was run on all four interpreters.
- The builder's own 14 mutants were not rerun, so its 14/14 and 12/14 claim is neither confirmed nor refuted.
- Probe URL-guard cases used `.invalid` hosts and closed port 9. Nothing left loopback.
- Concurrency is real threads and processes on one machine. These checks are probabilistic: k2, k3, k12, x18 and x19 passed every time they were run, which is evidence, not proof.
- The direct-database tampering in x10 to x12 shows what `check` misses; it does not show the API can produce those states.

## Files
- `VALIDATION.md`: this report.
- `MANIFEST.sha256`: SHA-256 of every other file in this folder.
- `oracle/m19_oracle.py`: the M19 oracle v2 (core k1 to k12, adversarial x1 to x19).
- `oracle/make_mutants.py`, `oracle/run_teeth.sh`: the mutants and teeth runner.
- `oracle/run_pyversions.sh`: the interpreter matrix.
- `oracle/m19_fresh_caller.sh`: the fresh caller.
- `oracle/stubs/`: `m19_stub.py` (modes noop, naive, vulnerable, racy) and its wrappers.
- `raw/`: every run output named above, plus the fetch, worktree, manifest and week-grok before and after records.

## Publication notes
- The publish copy replaces local paths with placeholders (`<D>`, `<PY312>`, `<UV>`, `<TMPDIR>` and so on) and drops the week-grok status listings. The before and after hashes stay in `raw/weekgrok-before.txt` and `raw/weekgrok-after.txt`.
- One x16 test vector, the URL whose userinfo is `127.0.0.1` and whose host is `example.invalid`, has the shape of an e-mail address and trips the publish scan.
  - In `oracle/m19_oracle.py`, after the runs, that literal was rewritten as a string concatenation. The value at runtime is identical.
  - In the published `raw/` logs it is shown as `127.0.0.1[at]example.invalid`.
  - No other text was changed.
