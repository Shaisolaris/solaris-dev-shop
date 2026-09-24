# API Design (wshobson canon + Solaris standing rules)

## REST defaults

- **Resource-noun URLs.** `/users`, `/users/:id`, `/users/:id/posts`. Never `/getUser` or `/createPost`.
- **HTTP verbs match intent.** GET safe + idempotent, PUT idempotent, POST creates, PATCH partial, DELETE removes.
- **Status codes:** 200 success, 201 created (with `Location` header), 204 no content, 400 bad input, 401 unauth, 403 forbidden, 404 missing, 409 conflict, 422 validation, 429 rate limit, 5xx server. Don't return 200 with `{"error": ...}` in the body.
- **Cursor pagination** for any list endpoint that could grow past 1000 items. Offset pagination only for small, fixed datasets.
- **Filtering / sorting / sparse fields:** `?filter[status]=active&sort=-created_at&fields=id,name`. Stay consistent.

## Request / response

- **Envelope or no envelope - pick one, stick with it.** `{ data: ... meta: ... }` is fine; raw arrays at top level is fine. Don't mix.
- **All datetimes ISO 8601 UTC.** Never client-local in the wire format.
- **All money as integers in minor units** (cents, paise). Currency code separate field. Never float.
- **Errors structured.** `{ error: { code: "string_machine_readable", message: "human readable", details: { ... } } }`. Stable error codes the frontend can branch on.

## Versioning

- **URL versioning** (`/v1/`, `/v2/`) for public APIs.
- **Header versioning** (`Accept: application/vnd.app+json;version=1`) for internal microservices.
- **Don't break v1.** Add v2 alongside. Sunset v1 with 6+ months notice and explicit deprecation headers.

## GraphQL

- **Use when** the frontend genuinely needs a different shape per view, OR there are 4+ clients consuming the same backend.
- **Don't use when** the team is small + REST works + you don't have a dedicated GraphQL champion.
- **Pagination:** Relay-style cursor connections (`edges`/`node`/`pageInfo`).
- **N+1:** mandatory DataLoader; without it, GraphQL is an N+1 generator.

## Security

- **Always rate-limit.** Auth + heavy endpoints both. Token bucket per user + per IP.
- **Idempotency-Key** header on POSTs that could be retried (payments especially).
- **CORS** explicit allowlist. Never `*` on credentialed endpoints.
- **CSRF** double-submit cookie or SameSite=Strict on cookie auth.

## Documentation

- **OpenAPI/Swagger** auto-generated from code (FastAPI, NestJS, Laravel Scribe). Hand-written API docs rot.
- **Postman / Bruno collection** alongside, kept in repo.

## Checklist before exposing an endpoint

1. Auth required? Documented?
2. Rate-limited?
3. Pagination if list?
4. Idempotent if write?
5. Error codes stable?
6. OpenAPI spec generated?
7. At least one test (happy + one error)?

Cross-reference: api-design-reviewer skill for client-API review work.
