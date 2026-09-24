# Auth Patterns

**Hard rule: never build auth from scratch.** Use a managed provider, OR self-host a maintained auth library. Both satisfy the rule; rolling your own session/token/password logic does not.

## Managed vs self-hosted (which bucket)

| Bucket | Use when | Options |
|---|---|---|
| Managed SaaS | Fastest path, fine to put the user table behind a third party | Auth0, Clerk, Supabase Auth |
| Self-hosted library | Data residency / cost / "user table must stay in our DB" | **Better Auth** (TS, framework-agnostic), Lucia, framework-native (Laravel Breeze, WP-native) |
| Framework-native | The framework already ships auth | Laravel Breeze/Sanctum, WordPress-native, Django auth |

### Better Auth (self-hosted TS auth), when the user table must stay in your DB
Better Auth (github.com/better-auth/better-auth, MIT, 28.7K stars, verified 2026-06-13) is the self-host answer for the all-TypeScript stack. It is framework-agnostic, owns its OWN tables in your database (not a third-party store), and ships 2FA, organization/multi-tenant support, and a plugin ecosystem out of the box.
- **Reach for it when** a client can't put auth behind Clerk/Auth0 (data residency, compliance, cost), but you still must NOT hand-roll auth. This is the middle path the old matrix lacked.
- **It still obeys the hard rule**, you are using a maintained, audited library, not writing session/token logic yourself.
- On a tRPC stack, the Better Auth session lands in the tRPC context; `protectedProcedure` reads it (see type-safe-api-layer.md).
- Self-host note: you run and patch it; keep it updated like any dependency, and the auth tables are yours to back up and secure.


## Decision matrix

| Stack | Recommended | Why |
|---|---|---|
| Laravel | Laravel Breeze (sessions) OR Sanctum (SPA + API) OR Passport (full OAuth2) | Native, well-supported |
| Next.js | Clerk OR Auth.js (NextAuth v5) OR Supabase Auth | Clerk for fast/managed; Auth.js for self-hosted |
| Node API | Auth0 OR Supabase Auth | Battle-tested |
| WordPress | WordPress-native + JWT plugin if API needed | Don't fight WP's auth |
| Mobile | Auth0 / Clerk / Firebase Auth (mobile SDK) | Native SDKs handle token refresh |

## Cross-stack auth framework (VoltAgent)

1. **Identify resource trust boundary** - what's protected?
2. **Pick authn primitive** - sessions (cookie + server) OR JWT (stateless) OR OAuth2 (third party).
3. **Decide token lifetime** - short access token (15min) + long refresh token (30d) is the safe default for stateless APIs.
4. **Define authz model** - RBAC (roles) for simple, ABAC (attributes) when access depends on resource ownership or context.
5. **Add row-level security** for multi-tenant data (Postgres RLS, Laravel global scopes).
6. **MFA on admin accounts** always. WebAuthn/passkeys preferred over TOTP/SMS.
7. **Audit logging** for auth events: login, logout, password change, MFA toggle, permission change.

## JWT specifics (when you use them)

- **Asymmetric signing (RS256)** for tokens issued to clients you don't fully control. HS256 only when issuer and verifier are the same trusted server.
- **Refuse `alg: none`** - explicit allowlist of algorithms in verification.
- **Short-lived access (5-15 min)** + refresh token rotation.
- **Don't store JWTs in localStorage.** httpOnly + Secure + SameSite cookies, or in-memory.
- **Include `iss`, `aud`, `exp`, `iat`, `nbf`** claims.

## Session specifics

- **httpOnly + Secure + SameSite=Lax (or Strict for auth flows)** cookies always.
- **Rotate session ID on privilege escalation** (login, MFA, role change).
- **Idle timeout (30min) + absolute timeout (8h)** for sensitive apps.

## Password (when unavoidable)

- **Argon2id** hash. bcrypt acceptable. Never SHA/MD5.
- **NIST 800-63B compliance**: 8+ chars, no composition rules, breach-list check (Pwned Passwords API).
- **Rate limit** login attempts: 5 fails per 15 min then captcha or lockout.

## Anti-patterns to refuse

- Building auth from scratch on a client project. Always escalate to managed provider.
- "Just use the API key in localStorage." No.
- Long-lived JWTs (>1h) without refresh.
- Storing passwords in plain text or reversible encryption.
- Using `Math.random()` for token generation. Use crypto-random.

Cross-reference: security-auditor for any pen-test or auth-flow security review.
