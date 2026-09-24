# Backend Developer - Top-5 Source Candidates (verified 2026-06-13)

Scope: best current sources to strengthen this employee on backend API/services
(framework patterns, performance, testing, security, queues). Each entry verified
live against the GitHub API on 2026-06-13. Gate-0 = grep of the employee's ACTUAL
current content (SKILL.md / rules.md / postgres-performance.md) to check for
duplication before recommending absorption.

---

## 1. goldbergyoni/nodejs-testing-best-practices  - TAG: ABSORB (methodology only)
- URL: https://github.com/goldbergyoni/nodejs-testing-best-practices
- Stars: 4,363  |  License: NONE / NOASSERTION (FLAG - methodology-only, do not vendor text wholesale)
- Last push: 2026-02-10  |  Created 2020; "April 2025" edition
- Maintainer cred: Yoni Goldberg - author of the 100k★ javascript-testing-best-practices
  and a co-author lineage with nodebestpractices; recognized authority on JS/Node testing.
- What it adds: a backend-specific *integration-first* testing strategy - component tests
  over a real DB in-process, the "five backend exit doors" outcome model, message-queue
  test checklist (nack, batch, poisoned message, idempotency, connection failure),
  HTTP-interceptor isolation + network-chaos simulation, data-isolation + cleanup strategy.
- Gate-0: PARTIAL-NEW. Employee W6 has framework-detection, coverage bars, TDD, and
  "inject failure at every saga step index" - but it has NO integration-first ordering,
  NO five-exit-doors outcome model, and NO MQ-test or external-integration-test checklist.
  Net-new methodology. ABSORB into a new testing-strategy reference; flag NOASSERTION,
  paraphrase only, no verbatim bundling.

## 2. shieldfy/API-Security-Checklist  - TAG: METHODOLOGY (corroborate + small delta)
- URL: https://github.com/shieldfy/API-Security-Checklist
- Stars: 23,261  |  License: MIT (permissive)
- Last push: 2026-02-10  |  not archived
- Maintainer cred: shieldfy org; one of the most-starred API-security references on GitHub.
- What it adds: a tight pre-release API-security countermeasure checklist
  (auth/JWT-alg-pinning, input, processing, output, CI/CD) usable as a handoff gate.
- Gate-0: MOSTLY-DUPLICATE. Employee W8 + Red flags + BaaS already cover OWASP Top 10,
  JWT validation, rate limits, SQLi/SSRF/path-traversal, secrets, CORS/CSRF, webhook
  idempotency. Small deltas worth a one-line each: pin the JWT alg server-side (reject
  `alg:none`/algo-confusion), no auto-increment IDs exposed (use UUID/ULID - partly
  present), force content-type + response content-type, generic 5xx errors (no stack
  traces to client). METHODOLOGY: fold 3-4 delta lines into rules.md security gate;
  do not duplicate the bulk.

## 3. zalando/restful-api-guidelines  - TAG: METHODOLOGY
- URL: https://github.com/zalando/restful-api-guidelines
- Stars: 3,207  |  License: CC-BY-4.0 (attribution - safe to paraphrase with credit)
- Last push: 2026-06-10  |  actively maintained
- Maintainer cred: Zalando engineering; the de-facto public reference RESTful + Event
  API guideline, cited across the industry (dret API-guidelines-in-the-wild).
- What it adds: MUST/SHOULD/MAY rule taxonomy; problem+json (RFC 9457) error format;
  compatibility/deprecation discipline; pagination + idempotency-key conventions;
  API-as-contract review checklist.
- Gate-0: MOSTLY-DUPLICATE. Employee W1 + API Design Reviewer already cover plural-noun
  resources, status-code map, pagination shapes, versioning, error envelope, breaking-
  change detection. Deltas: RFC 9457 problem+json as the standard error media type
  (employee uses a custom `{error:{code,message,details}}` - worth noting RFC 9457 as
  the interop default), explicit MUST/SHOULD/MAY severity on review findings, and a
  formal deprecation-sunset header. METHODOLOGY: cite as the external authority behind
  W1 + note RFC 9457; no bulk import needed.

## 4. OWASP/CheatSheetSeries  - TAG: CONNECT (authority reference)
- URL: https://github.com/OWASP/CheatSheetSeries
- Stars: 32,260  |  License: CC-BY-SA-4.0 (ShareAlike - FLAG: do not relicense; link/paraphrase + attribute)
- Last push: 2026-06-12  |  very actively maintained
- Maintainer cred: OWASP Foundation - the canonical application-security reference.
- What it adds: deep, per-topic cheat sheets the security pass can point to
  (REST Security, Authentication, Authorization, JWT, SQLi prevention, SSRF, Mass
  Assignment, Secrets Management, Input Validation, Logging).
- Gate-0: DUPLICATE-AS-CONTENT, VALUABLE-AS-POINTER. The employee already encodes the
  practices; what it lacks is a single authoritative pointer so the security pass can
  cite chapter-and-verse. CONNECT: add as the named external authority for W8's OWASP
  Top 10 scope; ShareAlike means link/attribute, never copy the text into our MIT skill.

## 5. OWASP/API-Security (API Security Top 10)  - TAG: METHODOLOGY
- URL: https://github.com/OWASP/API-Security
- Stars: 2,295  |  License: NOASSERTION (FLAG - methodology/taxonomy only)
- Last push: 2026-01-01  |  not archived
- Maintainer cred: OWASP Foundation API Security Project; the 2023 list is the industry
  standard taxonomy for API-specific risk.
- What it adds: the API-specific Top-10 taxonomy (BOLA / object-level authz, broken
  function-level authz, broken object-property-level authz / mass assignment,
  unrestricted resource consumption, SSRF, improper inventory management). This is
  sharper than the generic web Top-10 for an API-first employee.
- Gate-0: PARTIAL-NEW. Employee W8 references "OWASP Top 10" generically (web list).
  BOLA / object-level authorization and broken-object-property-level authz are the #1
  and #3 API risks and are only implicitly covered ("authn vs authz", RLS). METHODOLOGY:
  add the API Security Top-10 taxonomy as an explicit checklist line in the security
  gate, with BOLA called out by name. Taxonomy is facts, not copyrightable text.

---

## Summary table
| # | Repo | Stars | License | Pushed | Tag | Gate-0 |
|---|------|-------|---------|--------|-----|--------|
| 1 | goldbergyoni/nodejs-testing-best-practices | 4.4k | NOASSERTION (flag) | 2026-02-10 | ABSORB | partial-new |
| 2 | shieldfy/API-Security-Checklist | 23.3k | MIT | 2026-02-10 | METHODOLOGY | mostly-dup |
| 3 | zalando/restful-api-guidelines | 3.2k | CC-BY-4.0 | 2026-06-10 | METHODOLOGY | mostly-dup |
| 4 | OWASP/CheatSheetSeries | 32.3k | CC-BY-SA-4.0 (flag) | 2026-06-12 | CONNECT | dup-as-content |
| 5 | OWASP/API-Security (Top 10) | 2.3k | NOASSERTION (flag) | 2026-01-01 | METHODOLOGY | partial-new |

License flags: #1 and #5 are NOASSERTION (no clear OSS grant) - methodology/taxonomy
only, paraphrased, never bundle source. #4 is CC-BY-SA-4.0 (ShareAlike) - link and
attribute, never copy text into this MIT-licensed skill. #2 (MIT) and #3 (CC-BY-4.0)
are safe to paraphrase with credit.
