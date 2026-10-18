# M10 validation of G10 "Network diagnosis from inspectable evidence"

**Verdict: FAIL** (2 x P2, 4 x P3, 2 x P4, plus 1 test-strength finding).

The reworked SAN-prefix defect is fixed. Muse found it at 3ebbe73, and this run re-derived it independently: the oracle rejects 3ebbe73 on o6a and the candidate passes o6a. Everything else in the acceptance text holds on four interpreters: localization of the known faults, bounded uncertainty, reproducibility, field citation, offline operation, invalid-input handling, the original 84 tests and the fresh caller.

The verdict is FAIL because the same bug class survives in neighbouring forms. Common SAN spellings that the tool does not recognise give a confident `localized/high TLS_NAME_MISMATCH` for a certificate that does cover the host (F1). A wildcard directly over a TLD or public suffix is accepted as covering, which hides a real name mismatch behind a generic `TLS_ALERT` (F2). Both break "correct known failure localization", and F2 breaks a rule the reviewer brief asked for by name.

**Self-validation note:** this is Grok self-validation of a Grok-built candidate, not independent review. It was run adversarially with an oracle written for M10 that does not read the builder's oracle or tests. The final independent review stays pending.

## Subject (isolation)

| item | value |
|---|---|
| candidate | `6af7849eab0df33d024739023dbceb7827764c21`, branch `review/grok-g10-network-diagnosis` |
| earlier commit (Muse finding) | `3ebbe73100c565392e9da4433b5a51a6b67bd7e8` |
| base | `02ba9c5` (v0.61) |
| isolation | read-only `git fetch origin <branch>` from week-grok, then `git worktree add --detach <tmp> <sha>`. No clone, and no writes to week-grok's tree, index or branch (`raw/weekgrok-before.txt`, `raw/weekgrok-after.txt`) |
| manifest | `<D>/grok-output/G10/` manifest: 25/25 OK, and the manifest file set equals the diff file set against 02ba9c5 (`raw/manifest-verify.txt`). Diffstat: 25 files, +2254/-5 |
| contracts | `<D>/G10.md`, `<D>/M10.md`; candidate docs `employees/infrastructure/network-engineer/offline-trace-diagnosis.md` |
| interpreters | 3.9.6 (/usr/bin/python3), 3.11.16, 3.12.14 (main), 3.13.15 |
| network | every candidate run went through `oracle/inject/sitecustomize.py`, which blocks and logs socket connect, sendto, bind, getaddrinfo, gethostby* and create_connection. Zero attempts were logged. Traces use only documentation ranges and `.example` names |

## Acceptance items

| acceptance (G10/M10) | result | evidence |
|---|---|---|
| Correct known-failure localization | **FAIL** on SAN forms (F1, F2); PASS on 11 dns/route/tls/app cases | `raw/oracle-teeth.txt` (candidate o2 PASS, o6a PASS, o6b FAIL), `raw/san-probe.txt`, `raw/finding-repros.txt` |
| Incomplete trace stays bounded uncertainty | PASS | o3: missing layers give `undetermined` or `probable` with candidates and missing_evidence, contrary evidence gives `intermittent`, an empty trace is `undetermined`. The adversarial case where a handshake reset and HTTP 200 sit in one trace gives `probable/tls intermittent` |
| Reproducible from the same trace | PASS within one interpreter; P4 note across interpreters (F7) | o4 (PYTHONHASHSEED, TZ, key, observation and SAN order, batch workers 1 and 4); a01: 43 traces give identical bytes and exit codes on 4 interpreters; a02: 6 timestamp spellings are accepted on 3.11+ and refused on 3.9 |
| Diagnosis cites actual fields | PASS | o5: every address and name in the evidence lines appears in the trace; header values are never echoed (a09) |
| Missing evidence is not turned into certainty | PASS except F1 and F2, where a misread certificate field becomes a high-confidence verdict | o3, o6a, o6b |
| Clean control | PASS | o1: https, http, IP literal, mixed-case host and SNI |
| Meaningful unseen/failure case | PASS (oracle cases are new and not taken from the builder fixtures) | o2, o6a, adversarial a01 to a15 |
| Safe recovery / invalid input | PASS, except F5 (deep JSON crashes with exit 1, not 2, and aborts a batch) | o7: duplicate keys, NaN, symlinks, size limit, observation limit and malformed fields all exit 2 and write nothing; a15 checks symlinks and dotfiles in batch; a07 shows that out-of-range `--workers` values are refused |
| Offline, no live changes | PASS | o8 (0 attempts), o9 (no side writes); next_actions are read-only text and are never executed; a08 confirms a shell-metacharacter path stays one quoted token |
| Original 84 tests preserved | PASS | `raw/pyversions-matrix.txt`: G10 29 OK, original 84 OK and full 113 OK on 3.9.6, 3.11, 3.12 and 3.13 |
| Fresh caller | PASS | `raw/fresh-caller.txt`: `env -i`, new HOME, a `python3` shim, and only the 3 commands in the doc. All work, `report.json` is written, 0 network attempts, no stray files |
| Realistic scale/concurrency | PASS | a14: 10000 observations in 0.1 s; a batch of 2000 traces takes 0.3 s sequential and 0.2 s with 4 workers, with identical output |

## Findings

All repros are in `oracle/m10_finding_repros.sh` and their observed output is in `raw/finding-repros.txt`. Each repro runs `diagnose` on a synthetic trace with a TLS `bad_certificate` alert.

**F1 (P2): SAN spellings outside `DNS:`/`IP:`/`IP Address:` are read as bare names and give a confident false `TLS_NAME_MISMATCH`.** This is the same class as the reworked defect. Affected spellings:
- keytool `DNSName: x` and `IPAddress: x`
- Windows `DNS Name=x` and `IP Address=x`
- the one-line openssl list `DNS:a, DNS:b`

The candidate's own TLS_NAME_MISMATCH next_action (`openssl x509 -noout -ext subjectAltName`) prints exactly that one-line form, so recapturing the evidence the way the tool advises and pasting it in reproduces the false blame. Observed: `localized at tls (confidence high)`, `TLS_NAME_MISMATCH: certificate names ['dnsname: api.shop.example'] do not cover api.shop.example`. The `DNS:` control gives `TLS_ALERT`, which is correct. Suggested fix: accept these prefixes, or refuse any typed entry the tool does not recognise (exit 2, or `probable` with a note) rather than treating it as a bare name.

**F2 (P2): a wildcard directly over a TLD or public suffix is accepted as covering.** `DNS:*.example` covers `shop.example`, and `DNS:*.co.uk` covers `shop.co.uk` (also `*.com`). Real clients reject these, so the real cause (a name mismatch) is reported only as a generic `TLS_ALERT`, and the name-mismatch next_actions are lost. Rule in the brief: one label only, with no partial-label or public-suffix wildcards. Suggested minimal fix: require at least two labels after `*.` (`"." in name[2:]`); a full public-suffix list would be stricter. Positive control: `oracle/proposed-fix.patch` passes the M10 oracle 10/10 and the builder's tests 29/29.

**F3 (P3): non-ASCII SAN text is case-folded into ASCII.** `str.lower()` turns U+212A KELVIN SIGN into `k`, so `DNS:\u212aelvin.example` covers `kelvin.example`. Observed: `TLS_ALERT`, with no mismatch. Suggested fix: refuse or ignore non-ASCII SAN entries before lowercasing (A-labels only, as already happens for targets; see a10).

**F4 (P3): an SNI that differs from the target is not flagged.** Here the trace's client SNI is `www.other.example`, the target is `api.shop.example`, and the certificate covers only the SNI. The name check runs against `sni or host`, so the result is `TLS_ALERT` with no finding and no note that the client asked for a different name. That is a real misconfiguration class and it goes unreported.

**F5 (P3): a deeply nested JSON trace crashes.** A trace nested 100000 levels deep raises an uncaught `RecursionError` traceback and exits 1, which is the "fault or undetermined" exit code and not 2 for invalid input. One such file in `batch` aborts the whole batch (exit 1, empty stdout), so the good traces get no output. Suggested fix: catch `RecursionError` with the other parse errors.

**F6 (P4): a SAN with a double trailing dot (`api.shop.example..`) counts as covering.** The same string as a target is refused (exit 2), so the two paths disagree.

**F7 (P4): timestamp parsing differs by interpreter.** `+0000`, `+00`, one-digit or 7-digit fractions, the basic form `20261018T160000Z` and the week date are accepted on 3.11+ and refused (exit 2) on 3.9.6. Results on 3.9.6 and 3.11+ therefore differ for these traces. The doc says "Stdlib Python 3.12", but REWORK.md added a 3.9 `Z` shim, so 3.9 is partly supported. Either refuse the non-RFC 3339 forms everywhere or document 3.11+.

**F8 (test strength, P3): the builder's oracle lets 11 of 15 mutants through, and the builder's tests let 5 of 15 through.**
- Survive both the builder oracle and the tests: `answers_unsorted`, `chain_ignored`, `host_not_lowercased`, `ip_compared_as_text`, `refused_not_app`.
- The builder oracle's new `o12_san_forms` does not catch `ip_entry_covers_names` or `dns_entry_covers_ip`, the exact rework rule; only the builder tests catch them.
- `expiry_ignored` passes the builder oracle 12/12.

`raw/builder-oracle-vs-teeth.txt`, `raw/builder-tests-vs-mutants.txt`.

Behaviours checked and confirmed correct (not findings):
- The CN is never consulted. A CN-only certificate gives `TLS_ALERT` and not a mismatch, and a matching CN with a non-matching SAN still gives a mismatch, so there is no CN fallback.
- A typed `IP:` entry never covers a name, and a typed `DNS:` entry never covers an IP.
- IPv6 is compared as an address (the long form covers), and an IPv4-mapped IPv6 entry does not cover the IPv4 target.
- Punycode A-labels and wildcards over A-labels are handled.
- A U-label target is refused (a10).
- Partial-label wildcards (`w*.`, `*eb.`, `xn--*.`), `*.*`, wildcard depth two and the apex are refused (o6a: 15 covering and 11 non-covering cases; o6b: 3 strict cases).

## Oracle teeth (`oracle/m10_oracle.py` v2, checks o1 to o9 with o6 split into o6a and o6b)

| subject | M10 oracle | builder oracle | builder tests |
|---|---|---|---|
| candidate 6af7849 | 9/10 (o6b FAIL = F2, F3) | 12/12 | 29 OK |
| earlier 3ebbe73 | 8/10 (o6a FAIL: the Muse bug; o6b) | n/a | n/a |
| positive control (proposed-fix.patch) | **10/10** | 12/12 | 29 OK |
| stub no-op (fake healthy) | 1/10 REJECT | 4/12 REJECT | n/a |
| stub naive first-failure | 0/10 REJECT | 5/12 REJECT | n/a |
| builder noop_stub | 1/10 REJECT | 0/12 REJECT | n/a |
| builder naive_stub | 0/10 REJECT | 3/12 REJECT | n/a |
| 15 mutants | **15/15 caught**, each by a check the candidate passes | 4/15 caught | 10/15 caught |

Per-mutant check that catches it in the M10 oracle:

| check | mutants caught |
|---|---|
| o1 | host_not_lowercased |
| o2 | chain_ignored, expiry_ignored, refused_not_app |
| o3 | expiry_ignored, no_dns_ambiguity_on_mismatch, no_middlebox_ambiguity, probable_promoted, unknown_counts_healthy, wall_clock_dates |
| o4 | answers_unsorted |
| o6a | prefix_strip3 (the Muse bug), ip_entry_covers_names, dns_entry_covers_ip, wildcard_any_depth, ip_compared_as_text |

The M10 oracle gives the same result under 3.9.6, 3.11, 3.12 and 3.13 (`raw/oracle-cross-interpreter.txt`).

## Rejected and superseded runs (kept)

- `raw/oracle-candidate-run1-o2-overreach.txt`: o2 originally demanded more than the doc promises for "tcp refused"; it was relaxed to require dns and route ok and tls not_reached or unknown.
- `raw/oracle-teeth-v1-superseded.txt`: in v1, o6 mixed documented and strict rules, so 7 mutants were caught only by a check the candidate also fails. v2 splits o6, checks each finding's `layer` in o2, and uses mixed-case SNI and qname in o1.
- `raw/adversarial-candidate-run1-a08-harness-bug.txt`: a08 flagged a prose next_action because `shlex` cannot parse `owner's`. The harness bug was fixed: a08 now inspects only command lines that carry the path.

## Limitations

- The traces are synthetic. No real certificates, resolvers or captures were used, by design. Real-world capture formats beyond the ones probed (keytool, Windows, openssl) were not exhaustively enumerated.
- The public-suffix check uses a few well-known suffixes and not the full PSL.
- The scale check is a single run on one Mac; it is not a benchmark.
- Muse's own M10 run logs were not re-executed here; its finding was re-derived from source and from the 3ebbe73 behaviour.

## Layout

`oracle/` holds m10_oracle.py, m10_adversarial.py, m10_san_probe.py, make_mutants.py, run_teeth.sh, m10_finding_repros.{py,sh}, proposed-fix.patch, stubs/ and inject/sitecustomize.py. `raw/` holds every log, including the rejected runs. `MANIFEST.sha256` covers every file. Private paths appear as `<D>` and `<W>`.
