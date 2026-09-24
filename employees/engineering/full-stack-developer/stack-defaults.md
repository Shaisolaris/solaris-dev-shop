# Stack Defaults

The Solaris bread-and-butter stack. Deviation requires CTO sign-off (ADR).

## Frontend
- **Framework:** React 19 (Vite for SPAs, Next.js 16 for routed/SSR/SSG apps)
- **Language:** TypeScript strict mode. No `any` - use `unknown` + narrowing.
- **Styling:** Tailwind CSS. shadcn/ui for the component library when one is needed.
- **State:** React Query / TanStack Query for server state, Zustand for client state. NEVER useState + useEffect for data fetching.
- **Forms:** react-hook-form + zod for validation.
- **Routing:** Next.js App Router OR TanStack Router for non-Next SPAs. Avoid react-router for new work.

## Backend (per client stack)
- **Laravel/PHP** - Shai's primary bread-and-butter for SMB clients. Laravel 13+, PHP 8.3-8.5.
- **Node** - Express 5 for simple, Fastify for performance, NestJS for structured/team scale. tsx for dev, Node 24 Active LTS runtime (Node 22 Maintenance OK when engines require it).
- **Python** - FastAPI for new APIs. Django for content-heavy / admin-heavy clients.
- **.NET** - ASP.NET Core / .NET 10 LTS minimal APIs for new microservices; Clean Architecture template for monolith.

## Database
- **MySQL 8** - Laravel default, shared-host clients.
- **PostgreSQL 17+** - preferred when greenfield (16 still supported) (better JSON, generated columns, vector with pgvector).
- **Redis** - caching, queues, rate limiting.

## Auth
- **Never build it.** Use Auth0 / Clerk / Supabase Auth / WordPress-native / Laravel Breeze depending on stack.
- **WebAuthn / passkeys** preferred over passwords for greenfield.

## Payments
- **Stripe** unless client mandates otherwise. payments-specialist owns the integration patterns.

## Background jobs
- **Laravel** - Horizon + Redis.
- **Node** - BullMQ.
- **Python** - Celery + Redis OR Dramatiq.

## File / object storage
- **S3** (or Cloudflare R2 for cost). NEVER store user uploads in the app server's filesystem.

## When deviating
- Open an ADR (cross-reference engineering/architecture skill)
- Document the why in the project's AGENTS.md
- Get CTO sign-off before bringing the new tool into the stack catalog
