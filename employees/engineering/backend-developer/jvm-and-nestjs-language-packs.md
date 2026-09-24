# JVM and NestJS Language Packs (methodology)

Language-specific idioms, testing, security, and build-fix methodology for backend stacks the generic rules.md does not cover. Load this when the job is Java (Spring Boot or Quarkus), JPA/Hibernate, or NestJS. The generic backend doctrine in rules.md (API design W1, data modeling W2, auth W3, queues/sagas W4, idempotency, testing strategy) still applies on top; this file adds only the per-language craft.

Absorbed from ECC (affaan-m/everything-the coding agent-code, MIT) skills + agents, methodology lifted, no code bundled. See plugin.json absorbed_from for source list + dates.

These are now SUPPORTED LANGUAGES for the dev shop: Java 17+ (Spring Boot 3.x, Quarkus 3.x LTS) + JPA/Hibernate, and NestJS (TypeScript). Route Java/Quarkus engagements and NestJS team-scale Node work here.

---

## 0. Framework detection (do this first, every time)
Before applying any Java rule, read the build file (`pom.xml` / `build.gradle` / `build.gradle.kts`) and decide the lane:
- build file contains `quarkus` -> apply [QUARKUS] rules
- build file contains `spring-boot` -> apply [SPRING] rules
- both (rare) -> flag it as a finding, apply both
- neither -> shared Java rules only, note the ambiguity
The idioms diverge enough (CDI vs Spring DI, Panache vs Spring Data, ExceptionMapper vs RestControllerAdvice, JBoss Logging vs SLF4J) that picking the wrong lane produces wrong-but-compiling code.

---

## 1. Java core (shared, both frameworks)

### Idioms
- Java 17+ baseline. Records for DTOs and value objects; sealed classes + pattern matching where they remove casts; `instanceof` pattern matching instead of check-then-cast.
- Immutable by default: records, `final` fields, getters-only, no setters on domain objects. Minimize shared mutable state.
- `Optional` is a return type for `find*` methods, never a field or parameter. Compose with `map`/`flatMap`/`orElseThrow`; never `.get()` without `isPresent()` (use `.orElseThrow(...)`).
- Streams for short transformation pipelines; drop back to a loop the moment a stream nests or needs side effects. `.toList()` over `collect(toList())`.
- Generics: declare type parameters, no raw types; bounded generics for reusable utilities.
- Exceptions: unchecked for domain errors, create domain-specific types (e.g. `MarketNotFoundException`), wrap technical exceptions with context, never an empty/silent `catch (Exception e) {}`.
- Null handling: `@NonNull` by default, `@Nullable` only when unavoidable, Bean Validation (`@NotNull`, `@NotBlank`, `@Email`, `@Size`) on all inputs.

### Code smells to flag
Long parameter lists (-> DTO/builder), deep nesting (-> early returns), magic numbers (-> named constants), static mutable state (-> DI), silent catch blocks, string concatenation in loops (-> StringBuilder), null returns from the service layer (-> Optional).

### Member ordering + layout
Constants, fields, constructors, public methods, protected, private. One public top-level type per file. Keep methods short, extract helpers.

---

## 2. Spring Boot [SPRING]

### Architecture
- Layered: controller (`*Controller`) -> service -> repository. Controllers stay thin (parse input, call service, map to response DTO). Business logic lives in services. Repositories stay simple.
- Constructor injection always. `@Autowired` on fields is a code smell and a review block.
- `@Transactional` on the service layer, never controller or repository. `@Transactional(readOnly = true)` on read paths.
- Centralize errors in one `@RestControllerAdvice` / `@ControllerAdvice`; map validation, access-denied, and a catch-all generic 500 (log stack traces, return a generic message, never leak `e.getMessage()` to clients).
- Never return a JPA entity from a controller; return a DTO/record projection.

### REST + validation
- `@RestController` + `@RequestMapping`, `@Valid @RequestBody` on every write DTO, records for request/response DTOs with Bean Validation constraints.
- Pagination via `Pageable` -> `Page<T>` (default size 20); unbounded `List<T>` endpoints are a finding.
- Enable RFC 7807 problem details: `spring.mvc.problemdetails.enabled=true` (Spring Boot 3+). This is the JVM equivalent of the RFC 9457 problem+json the generic W1 already mandates.

### Cross-cutting
- Caching: `@EnableCaching` + `@Cacheable`/`@CacheEvict` keyed explicitly.
- Async: `@EnableAsync` + `@Async` returning `CompletableFuture`; supply a bounded custom `Executor` (default is unbounded threads, a review finding).
- Background work: `@Scheduled` or a queue (Kafka/SQS/RabbitMQ); handlers idempotent + observable; long-running `@Scheduled` blocks the scheduler thread.
- External calls: retry with exponential backoff (preserve interrupt status on `InterruptedException`); add jitter (no jitter -> thundering herd).
- Logging: SLF4J with structured key=value messages; JSON via Logback encoder for prod.
- Observability: Micrometer metrics (Prometheus/OTel) + Micrometer Tracing.
- HikariCP pool sized to workload with explicit timeouts.

### Security (Spring Security)
- Stateless JWT or opaque tokens with a revocation list; session cookies `httpOnly` + `Secure` + `SameSite=Strict`. Validate token in a `OncePerRequestFilter` or use the resource-server support.
- `@EnableMethodSecurity` + `@PreAuthorize("hasRole('ADMIN')")` or `@PreAuthorize("@authz.isOwner(#id, authentication)")` for resource-level checks. Deny by default.
- Password hashing via a `PasswordEncoder` bean (`BCryptPasswordEncoder(12)` or Argon2); never manual hashing, never plaintext.
- SQL injection: Spring Data derived queries or `:param` bindings; never string-concatenate into `@Query`/`JdbcTemplate`. Native queries that mutate need `@Modifying` + `@Transactional`.
- CSRF: keep enabled for browser/session apps; disable only for pure stateless Bearer-token APIs (and document why) alongside `SessionCreationPolicy.STATELESS`.
- CORS at the security filter level, allow-list origins, never `*` in prod.
- Security headers: CSP (`default-src 'self'`, avoid `unsafe-inline` for script-src, use nonces/hashes), `X-Frame-Options`/frameOptions sameOrigin, XSS protection, referrer-policy.
- Rate limiting: Bucket4j filter or gateway; key on `request.getRemoteAddr()`, NOT raw `X-Forwarded-For` (spoofable). Trust forwarded headers only behind a configured `ForwardedHeaderFilter` + `server.forward-headers-strategy`. Return 429 + retry hint.
- Secrets: env vars or Vault (Spring Cloud Vault); `${DB_PASSWORD}` placeholders, never literals in `application.yml`.
- File uploads: validate size + content type + extension, store outside web root.
- Logs: never log secrets/tokens/passwords/PAN; redact PII.
- Dependencies: OWASP Dependency-Check / Snyk in CI, fail the build on known CVEs.
- Pre-release security checklist: auth tokens validated + expiring, authz guard on every sensitive path, all inputs validated, no concatenated SQL, correct CSRF posture, secrets externalized, headers set, rate limiting on public/auth/payment endpoints, deps scanned, logs clean.

### TDD (JUnit 5 + Mockito + MockMvc + Testcontainers)
- Loop: write failing test -> minimal code to pass -> refactor green -> enforce coverage. Arrange-Act-Assert, AssertJ `assertThat` for value checks, `assertThatThrownBy` for exceptions, `@ParameterizedTest` for variants, test data builders for fixtures. Names describe behavior (`should_return_404_when_user_not_found`), not method names.
- Right-size the test slice (over-scoping is a finding):
  - unit: `@ExtendWith(MockitoExtension.class)` + `@Mock`/`@InjectMocks`, no Spring context.
  - controller slice: `@WebMvcTest` + `@MockBean`.
  - repository slice: `@DataJpaTest`, prefer Testcontainers Postgres over H2 (wire via `@DynamicPropertySource`) so tests mirror prod.
  - full integration: `@SpringBootTest` + `@AutoConfigureMockMvc` + `@ActiveProfiles("test")`, reserved, not for units.
- Coverage gate: JaCoCo, 80%+ lines (70%+ branches). Use Awaitility (not `Thread.sleep`) for async.

### Verification loop (before PR / pre-deploy)
Build (`mvn -T 4 clean verify -DskipTests`) -> static analysis (spotbugs + pmd + checkstyle) -> tests + JaCoCo coverage -> security scan (OWASP Dependency-Check + grep for hardcoded secrets / `System.out.print` / raw `e.getMessage()` in responses / wildcard CORS) -> optional Spotless format -> diff review. Emit a VERIFICATION REPORT (Build/Static/Tests/Security/Diff -> READY or NOT READY with the issue list). Treat warnings as defects.

---

## 3. Quarkus 3.x LTS [QUARKUS]

Quarkus diverges from Spring on most idioms; do not transplant Spring habits.

### Architecture + CDI
- Layered: resource (`*Resource`, JAX-RS, NOT `*Controller`) -> service -> repository. Same thin-resource discipline.
- CDI scopes: `@ApplicationScoped` is the default for services. `@Singleton` is non-proxyable and breaks interception + lazy init (a review finding; switch to `@ApplicationScoped` unless explicitly justified). Constructor injection preferred; package-private field `@Inject` is acceptable in Quarkus (avoids proxy issues).
- `@Transactional` on mutating service methods; active-record `persist()`/`delete()`/`update()` outside a transactional context fails. Keep transactions short; do not call async ops inside them.
- Centralize errors via `ExceptionMapper<T>` (`@Provider`) or `@ServerExceptionMapper` (RESTEasy Reactive); map `ConstraintViolationException` to 400 and a generic catch-all to 500.
- Never return a Panache entity from a resource; use a DTO/record.

### Data access (Panache)
- Pick ONE per bounded context: active-record (`PanacheEntity`, public fields, build-time accessors) OR repository (`PanacheRepository`). Mixing them is a finding. Same rule for MongoDB (`PanacheMongoEntity` vs `PanacheMongoRepository`).
- Parameterized queries by position (`?1`) or name (`Parameters.with(...)`); native queries use `:param`, never concatenation.
- Paginate with `.page(Page.of(index, size))`; unbounded `listAll()`/`findAll()` is a finding.
- MongoDB extras: register codecs/BSON annotations for custom types, index queried fields, decide `ObjectId` vs custom `@BsonId`, multi-document transactions need an explicit `ClientSession` (Panache MongoDB does NOT auto-manage them), add TTL indexes for sessions/tokens/caches, use GridFS for large blobs (16 MB BSON limit).

### Reactive
- Return `Uni`/`Multi` from reactive endpoints; compose with `.chain(...)`, signal absence with `.onItem().ifNull().failWith(...)`.
- NEVER block inside a `Uni`/`Multi` pipeline or a `@NonBlocking` endpoint (JDBC, file I/O, `Thread.sleep`). Use `@Blocking`, `.runSubscriptionOn(executor)`, or a reactive client. Blocking on the Vert.x event loop is `BlockingNotAllowedOnIOThread`.
- Do not subscribe to a shared `Uni` more than once; use `Uni.memoize()`.

### Config + ops
- YAML or properties; profile-aware (`%dev`/`%test`/`%prod`). `hibernate-orm.database.generation`: `drop-and-create` dev/test, `validate` prod (never auto-DDL in prod).
- Type-safe config: `@ConfigMapping` (build-time validated) for grouped config, `@ConfigProperty` for single values. Externalize secrets to env/Vault (`quarkus-vault`).
- Logging: JBoss Logging (default, zero-cost build-time) via `Logger.getLogger(...)` or `@Inject Logger`; `logback` + Logstash encoder when structured JSON is needed; propagate a LogContext through service calls (and into `CompletableFuture` work) for request tracing.
- Async: `CompletableFuture.supplyAsync(... executor)` on a managed executor (`ManagedExecutor`), not unbounded threads; pass LogContext into the async scope.
- Health checks: `@Liveness` / `@Readiness` `HealthCheck` beans (DB connection, Camel context, etc.).
- Favor build-time over runtime processing; avoid runtime reflection (add `@RegisterForReflection` only when native image needs it). Stay on the latest 3.x LTS; use dev mode for hot reload; test native compilation periodically.

### Event-driven (Apache Camel + RabbitMQ), when the architecture is event-driven
- `RouteBuilder` routes: `direct:` for in-memory routing, `spring-rabbitmq` component for RabbitMQ; `ProducerTemplate` (sync or `asyncSendBody`) to publish; `onException(...).handled(true)` for route error handling; `.choice().when(...).otherwise()` for conditional flow.
- Track every operation with an EventService (explicit success + error events persisted with type/status/payload/timestamp).
- SmallRye Reactive Messaging `@Incoming`: implement a dead-letter or `nack` strategy; no DLQ handling is a finding.
- MicroProfile Fault Tolerance `@Retry`: add jitter.

### Security (Quarkus Security)
- Auth: MicroProfile/SmallRye JWT (`mp.jwt.verify.*`) or OIDC (`quarkus.oidc.*`); `@Authenticated` on protected resources; read identity via injected `JsonWebToken` / `SecurityIdentity`. Custom `ContainerRequestFilter` at `@Priority(Priorities.AUTHENTICATION)` rejects missing/malformed `Bearer` immediately.
- Authz: `@RolesAllowed("ADMIN")` declarative; programmatic ownership checks via `SecurityIdentity` (`isAnonymous`, `hasRole`, principal name). Deny by default.
- Passwords: `BcryptUtil.bcryptHash` / `BcryptUtil.matches`; never plaintext.
- SQL injection: Panache parameterized queries; parameterized native queries via `EntityManager`.
- Input validation: `@Valid` on `@BeanParam`/`@RestForm`/request body; custom `ConstraintValidator` for domain formats.
- CORS via `quarkus.http.cors.*` (allow-list origins). Security-headers `ContainerResponseFilter` (`X-Frame-Options: DENY`, `nosniff`, HSTS, CSP without script `unsafe-inline`).
- Rate limiting: `ContainerRequestFilter`; identify clients by `getRemoteAddr()` (+ `quarkus.http.proxy.proxy-address-forwarding=true` behind a trusted proxy), NOT raw `X-Forwarded-For`; 429 on breach.
- Audit sensitive ops via `SecurityIdentity`. CVE scan: `mvn org.owasp:dependency-check-maven:check` + `mvn quarkus:audit`.

### TDD (JUnit 5 + Mockito + REST Assured + Camel + JaCoCo)
- Structure unit tests with `@Nested` (group by method) + `@DisplayName` + `givenX_whenY_thenZ` naming + explicit `// ARRANGE / ACT / ASSERT`. Cover happy paths, null inputs, edge cases (empty collections, boundaries, blank strings), and exceptions. `verify(...)` interactions; `verify(... never())` in error paths.
- Panache `persist()` is void: stub with `doNothing().when(repo).persist(any())` + verify.
- Slices (over-scoping `@QuarkusTest` for units is a finding):
  - unit: plain JUnit 5 + Mockito (`@ExtendWith(MockitoExtension.class)`), no `@QuarkusTest`.
  - CDI integration: `@QuarkusTest` + `@InjectMock` (Quarkus-specific, not `@MockBean`).
  - API: REST Assured `given()...when()...then().statusCode(...)`.
  - Camel routes: `camel-quarkus-junit5` + `MockEndpoint` + `AdviceWith` to swap real endpoints for mocks.
  - DB integration: Dev Services (preferred, auto Postgres/Kafka/Redis) or `@QuarkusTestResource`/Testcontainers; `@TestProfile` for scenario config.
- AssertJ for value checks; `assertThrows` to capture then AssertJ on the message; Awaitility for async. Coverage: JaCoCo 80%+ lines / 70%+ branches.

### Verification loop (adds native + container phases over Spring)
Build -> static analysis (checkstyle/pmd/spotbugs, optional SonarQube) -> tests + JaCoCo `jacoco:check` -> security (OWASP Dependency-Check, `quarkus:audit`, optional OWASP ZAP against `/q/openapi`) -> native compilation (`mvn package -Dnative -Dquarkus.native.container-build=true`, smoke-test the runner + `/q/health`) -> optional K6 load test (p50/p95/p99, throughput, error rate) -> health checks (`/q/health/live`, `/q/health/ready`) -> container build + image scan (Trivy/Grype) -> config validation per env -> OpenAPI/docs review. Native targets: startup < 100ms, acceptable memory.

---

## 4. JPA / Hibernate (Spring Boot data layer)

### Entity design
- `@Entity` + `@Table` with explicit `indexes`; `@Id @GeneratedValue`; `@Enumerated(EnumType.STRING)` (never ORDINAL); `@EntityListeners(AuditingEntityListener.class)` + `@CreatedDate`/`@LastModifiedDate` with `@EnableJpaAuditing`.
- Keep entities lean; map only what you persist.

### N+1 prevention (the default ORM mistake, generic W2 calls it out; this is the JPA mechanics)
- Default to LAZY; `EAGER` on collections is a finding. Fetch deliberately with `JOIN FETCH` or `@EntityGraph`/`@NamedEntityGraph` per read path.
- Read paths: DTO projections (interface or class) instead of loading full entities; `select` only needed columns, never `select *`.
- Verify SQL counts by enabling `logging.level.org.hibernate.SQL=DEBUG` (+ `org.hibernate.orm.jdbc.bind=TRACE` for params).

### Repositories + transactions
- `JpaRepository`; derived queries (auto-parameterized) or `@Query` JPQL with `:param`. Mutating `@Query` needs `@Modifying` + `@Transactional`.
- `@Transactional` on service methods, `readOnly = true` for reads, choose propagation deliberately, keep transactions short (no long-running ones). 1st-level cache is per EntityManager; do not hold entities across transactions; treat 2nd-level cache cautiously and validate eviction.

### Performance
- Index common filters (`status`, `slug`, FKs) and composites matching query patterns (`status, created_at`). Batch writes with `saveAll` + `hibernate.jdbc.batch_size`.
- HikariCP: `maximum-pool-size` (start ~20), `minimum-idle`, `connection-timeout`, `validation-timeout`; for Postgres LOB add `hibernate.jdbc.lob.non_contextual_creation=true`.
- Pagination: `PageRequest.of(n, size, Sort.by(...))`; cursor-like via `id > :lastId` + ordering for large/fast-moving sets.

### Migrations + testing
- Flyway or Liquibase; never Hibernate auto-DDL in prod. Migrations idempotent + additive; no column drops without a plan (ties to generic W2 expand-and-contract).
- Test data access with `@DataJpaTest` + Testcontainers (mirror prod engine); assert SQL efficiency from the logs.

---

## 5. NestJS (TypeScript)

This deepens the bare "NestJS team-scale Node" stack mention. The generic Node/TS maxims (branded types, make impossible states impossible, event-loop discipline) still apply.

### Structure
- Feature modules own their domain code (controller, service, module, dto/, entities/, guards/, strategies/). Cross-cutting filters/guards/interceptors/pipes/decorators live in `common/`. Config in `config/`. DTOs sit next to the module that owns them.
- Controllers stay thin (parse HTTP, call a provider, return a response DTO). Business logic goes in `@Injectable` services. Export only the providers other modules genuinely need.

### Bootstrap + validation (do this once, globally)
- One global `ValidationPipe` with `whitelist: true`, `forbidNonWhitelisted: true`, `transform: true`, `transformOptions.enableImplicitConversion: true`. `whitelist` + `forbidNonWhitelisted` are mandatory on public APIs.
- Global `ClassSerializerInterceptor` (strip internal fields) + a global exception filter. Reuse the exact same global pipes/filters in tests.
- Validate every request DTO with `class-validator` (`@IsEmail`, `@IsString`, `@Length`, `@IsOptional`, `@IsEnum`). Return dedicated response DTOs/serializers; never return ORM entities directly (no leaking password hashes, tokens, audit columns). Route params via `ParseUUIDPipe`/`ParseIntPipe`.

### Auth + error shape
- `@UseGuards(JwtAuthGuard, RolesGuard)` + `@Roles(...)`: coarse access in guards, resource-specific authorization in services. Keep strategies/guards module-local unless truly shared; use an explicit authenticated-request type.
- One consistent error envelope across the API via a single `@Catch()` `ExceptionFilter`: pass through `HttpException` status + body for expected client errors, log + wrap unknown failures as a generic 500.

### Config + persistence + production
- `ConfigModule.forRoot({ isGlobal: true, load: [configuration], validate: validateEnv })`: validate env AT BOOT, not lazily; terminate on invalid config rather than booting partially. Access config behind typed helpers; split dev/staging/prod in config factories, not scattered branches.
- Keep ORM/repository code behind providers that speak domain language; isolate transactional/multi-step writes in services that own the unit of work (Prisma/TypeORM). Controllers never coordinate multi-step writes.
- Production defaults: structured logging + request correlation IDs; async provider init for DB/cache clients with explicit health checks; background jobs + event consumers in their own modules (not HTTP controllers); explicit rate limiting + auth + audit logging on public endpoints.

### Testing
- Unit test providers in isolation with mocked deps. Add request-level tests for guards, validation pipes, and exception filters using `Test.createTestingModule` + `createNestApplication`, applying the same global `ValidationPipe` you run in prod.

---

## 6. Java review gate (java-reviewer agent methodology)
When reviewing Java changes: detect framework first, then `git diff -- '*.java'`, run the build check (`./mvnw verify -q` / `./gradlew check`), report findings only (do not refactor). Severity ladder:
- CRITICAL (block): SQL/command/code injection, path traversal, hardcoded secrets, PII/token logging, missing input validation, unjustified CSRF disable; swallowed exceptions, `.get()` on Optional, no centralized exception handling, wrong HTTP status. Escalate CRITICAL security to security review.
- HIGH (block): field injection / wrong DI style, `@Singleton` where `@ApplicationScoped` belongs [QUARKUS], business logic in controllers, `@Transactional` on the wrong layer, entity exposed in response, blocking call on a reactive thread [QUARKUS], N+1 / `EAGER` collections, unbounded list endpoints, missing `@Modifying`, dangerous cascade, Panache active-record/repository mixing [QUARKUS].
- MEDIUM (warn): NoSQL schema-evolution/blob/nesting/TTL issues, mutable singleton fields, unbounded async, blocking `@Scheduled`, reactive stream misuse, Java idiom/perf misses, null returns, over-scoped test annotations, weak test names, `Thread.sleep` in tests; workflow/state-machine issues (idempotency key checked after mutation, illegal state transitions, non-atomic compensation, no jitter, no dead-letter).
Verdict: Approve (no CRITICAL/HIGH), Warning (MEDIUM only), Block (any CRITICAL/HIGH).

## 7. Java build-fix gate (java-build-resolver agent methodology)
Surgical fixes only, never refactor. Detect framework -> `compile`/`build` -> read the affected file -> minimal fix -> rebuild to verify -> run tests. Lean on the error->cause->fix tables:
- General Java: `cannot find symbol` (missing import/dep), `incompatible types` (cast/type), `package X does not exist` (missing dependency), `Source option no longer supported` (compiler release mismatch), annotation-processor exceptions (Lombok/MapStruct config).
- [SPRING]: `No qualifying bean` (missing stereotype/scan), circular dependency (break cycle or `@Lazy` one leg), `Failed to configure a DataSource` (driver/props), BOM version mismatch.
- [QUARKUS]: `UnsatisfiedResolutionException` (missing CDI annotation/extension), `AmbiguousResolutionException` (`@Priority`/`@Alternative`/qualifier), non-proxyable bean (`@Singleton`+interceptor or `final` -> `@ApplicationScoped`), `BlockingNotAllowedOnIOThread` (`@Blocking`/reactive client), `SRCFG*` config errors, "Panache entity not enhanced" (package scan + extension), RESTEasy classic-vs-reactive mixing. Prefer `quarkus ext add` over hand-editing the POM; add `@RegisterForReflection` only when native needs it.
Maven debug: `dependency:tree -Dverbose`, `clean install -U`, `dependency:analyze`, `help:effective-pom`. Gradle: `dependencies --configuration runtimeClasspath`, `build --refresh-dependencies`, `dependencyInsight`. Stop after 3 failed attempts, if the fix introduces more errors than it solves, if it needs architectural change, or if it needs a user decision (private repos, GraalVM not installed). Output: `Framework | Build Status | Errors Fixed | Files Modified`.

---

## CI note (fleet doctrine)
ECC's Quarkus verification skill ships a GitHub Actions sample using floating `actions/checkout@v3`, `actions/setup-java@v3`, `actions/cache@v3`, `codecov/codecov-action@v3` tags. When standing up CI for these stacks, SHA-pin every third-party action to a full commit SHA (`uses: actions/checkout@<40-char-sha> # v4`), never a floating major tag. The verification phase ordering and the JaCoCo/OWASP/native gates are the value to lift; the unpinned tags are not.
