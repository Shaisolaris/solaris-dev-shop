# Native Mobile Language Packs

> **Absorbed 2026-06-14** from `affaan-m/everything-claude-code` (ECC, MIT) - methodology only, no code bundled.
> Source skills lifted: kotlin-patterns, kotlin-coroutines-flows, kotlin-testing, kotlin-ktor-patterns, kotlin-exposed-patterns, android-clean-architecture, compose-multiplatform-patterns, dart-flutter-patterns, flutter-dart-code-review, swiftui-patterns, swift-concurrency-6-2, swift-actor-persistence, swift-protocol-di-testing, liquid-glass-design, foundation-models-on-device.
>
> **What this adds.** This employee already carried the RN/Expo cross-platform stack, the test/release pillar (`mobile-test-and-release.md`), and the dpconde NowInAndroid skeleton (`android-architecture.md`). This pack adds **language-level depth** for the three native ecosystems - idiomatic Kotlin, modern Swift 6.2 / SwiftUI / iOS 26, and Dart/Flutter - so Claude writes native code the way a senior platform engineer would, not transliterated JS. It does not replace any existing file; load it alongside `android-architecture.md` for Kotlin work, and as the primary depth reference for Swift/iOS and Flutter.
>
> **Supported platforms / languages after this pack:** Kotlin (Android + KMP + Ktor/Exposed server), Jetpack Compose + Compose Multiplatform, Dart + Flutter (BLoC / Riverpod / Provider / GetX / MobX / Signals), Swift 6.2 + SwiftUI + UIKit + WidgetKit (iOS 26 Liquid Glass), Apple on-device LLM (FoundationModels). React Native + Expo + Flutter cross-platform coverage remains the default per SKILL.md stack-priority order; native depth is for when platform features or performance demand native.

---

## Pack A - Kotlin / Android / Compose

### A1. Idiomatic Kotlin (source: kotlin-patterns)

The seven pillars Claude should enforce in any new or reviewed Kotlin:

1. **Null safety via the type system.** Non-nullable by default. Safe-call `?.` + Elvis `?:` for fallbacks. Force-unwrap `!!` is a red flag - replace with a checked throw (`?: throw ...`) or a nullable return.
2. **Immutability by default.** `val` over `var`, immutable `List`/`Map` over mutable, `data class` + `copy()` for updates. Mutable global state and mutable data classes are anti-patterns.
3. **Expression bodies.** Single-expression functions and `when`-as-expression over block bodies with `return`.
4. **Value objects.** `data class` for data holders; `@JvmInline value class` for zero-overhead type-safe wrappers (`UserId`, `Email`) with `init { require(...) }` validation.
5. **Sealed hierarchies.** `sealed class`/`sealed interface` for restricted type sets (`Result`, `ApiError`) so `when` is exhaustive without `else`.
6. **Scope functions, used correctly.** `let` (transform nullable), `apply` (configure, returns receiver), `also` (side effect, returns receiver), `run`/`with` (block returning result). Anti-pattern: nesting scope functions - chain safe calls instead (`user?.address?.city?.let { ... }`).
7. **Extension functions** to add behavior without inheritance; scope them inside a class when they should not pollute the global namespace.

Supporting idioms: interface delegation (`class X(d: Repo) : Repo by d` then override only what you wrap), property delegation (`by lazy`, `Delegates.observable`, map-backed), type-safe DSL builders with `@DslMarker` + lambda-receiver, `Sequence` for lazy multi-step pipelines over large collections, `require`/`check`/`error` for preconditions, `Result` + `runCatching` for domain operations (do NOT use exceptions for expected control flow).

Gradle: Kotlin DSL (`build.gradle.kts`), `jvmToolchain(N)`, version-pin plugins, detekt + ktlint as static-analysis gates. (Mirrors the `android-architecture.md` rule: deps live in `gradle/libs.versions.toml`, build config in convention plugins, never inline per-module.)

### A2. Coroutines & Flow (source: kotlin-coroutines-flows)

- **Structured concurrency only.** Scope chain: `viewModelScope` (or `LaunchedEffect(key)` in Compose) -> `coroutineScope { }` -> `async { }`. **`GlobalScope` is banned** - it leaks and ignores cancellation.
- **Parallel decomposition** with `coroutineScope { val a = async{}; val b = async{}; combine(a.await(), b.await()) }`. Use `supervisorScope` when one child's failure must not cancel its siblings.
- **StateFlow for UI state**: `.stateIn(scope, SharingStarted.WhileSubscribed(5_000), initial)`. The 5-second timeout keeps upstream alive across config changes without restarting collection.
- **`combine(...)`** multiple repository flows into one UI-state flow.
- **Flow operators for search**: `debounce(300).distinctUntilChanged().flatMapLatest { search(it) }.catch { emit(empty) }`.
- **`retryWhen`** with exponential backoff (`delay(1000L * (1 shl attempt))`) for transient `IOException`, capped attempts.
- **SharedFlow for one-time effects** (snackbar, navigation) - a sealed `Effect` interface emitted from the ViewModel, collected in a `LaunchedEffect`. Never model one-time events as StateFlow state (they re-fire on recomposition).
- **Dispatchers**: `Default` (CPU), `IO` (blocking I/O, JVM/Android only), `Main` (UI). In KMP, `IO` is unavailable off-JVM - use `Default` or inject the dispatcher.
- **Cooperative cancellation**: `ensureActive()` in long loops; cleanup in `try/finally`, wrapping must-run release in `withContext(NonCancellable)`. Never catch `CancellationException` and swallow it.
- Anti-patterns: collecting in `init{}` without a scope; `MutableStateFlow` holding mutable collections (always `_state.update { it.copy(...) }`); creating a `Flow` inside a `@Composable` without `remember`.

### A3. Clean Architecture for Android/KMP (source: android-clean-architecture; complements android-architecture.md)

- **Module layers & one-way dependency rule:** `app -> presentation, domain, data, core`; `presentation -> domain, design-system, core`; `data -> domain, core`; `domain -> core (or nothing)`; `core -> nothing`. **`domain` must never import a framework class** - pure Kotlin only.
- **UseCase** = one business operation, `operator fun invoke(...)` for clean call sites; Flow-returning UseCases for reactive reads. Keep business logic in UseCases, not ViewModels.
- **Repository interface in `domain`, implementation in `data`** coordinating local + remote DataSources.
- **Mappers as extension functions** near the data models (`Entity.toDomain()`, `Dto.toEntity()`). Never expose Room entities or network DTOs to the UI layer.
- **Persistence**: Room on Android (`@Entity`/`@Dao`/`@Upsert`/`Flow`-returning `observeAll`); SQLDelight for KMP (`.sq` files); Ktor `HttpClient` with `ContentNegotiation(json)` + `Logging` for the network DataSource.
- **DI**: Koin (KMP-friendly - `module { factory/single/viewModelOf }`) or Hilt (Android-only - `@Module @InstallIn`, `@Binds`, `@HiltViewModel`).
- **Error type**: `Result<T>` or a custom `sealed interface Try<T>` + `sealed interface AppError(Network/Database/Unauthorized)`, mapped to UI state in the ViewModel.
- **Convention plugins** in `build-logic/` to dedupe KMP build config across modules.

### A4. Compose / Compose Multiplatform (source: compose-multiplatform-patterns)

- **One immutable state data class per screen**, exposed as `StateFlow`, collected via `collectAsStateWithLifecycle()`. Prefer this over `mutableStateOf` in ViewModels for lifecycle safety.
- **Split Screen into stateless + stateful**: `XScreen(viewModel)` reads state and delegates to a stateless `XContent(state, onEvent)` - the stateless half is previewable and testable. (Reinforces the existing `XRoute`/`XScreen` split rule.)
- **Event-sink pattern**: a `sealed interface XEvent` + single `onEvent(event)` callback instead of a long list of lambda parameters.
- **Type-safe navigation (Nav 2.8+)**: routes as `@Serializable` objects/data classes; `composable<Route>`, `toRoute<Route>()`, `dialog<Route>` for declarative dialogs. Pass lambda callbacks down, never the `NavController`.
- **Slot-based composables** (`header`/`content`/`actions` slot params) for reusable components.
- **Modifier order matters**: layout (padding/size) -> shape (clip) -> drawing (background/border) -> interaction (clickable).
- **Performance**: `@Immutable`/`@Stable` data classes for skippable recomposition; stable `key = { it.id }` in `LazyColumn`; `derivedStateOf` to defer derived reads; `remember(input)` expensive filters; `key(id) { }` to keep callbacks attached to the right row; no heavy compute or allocation inside `body`.
- **KMP platform UI** via `expect`/`actual` composables.
- **Material 3 theming** with dynamic color (`dynamicDarkColorScheme`/`dynamicLightColorScheme` on Android 12+).
- Anti-patterns: passing `NavController` deep; heavy work in `@Composable`; `LaunchedEffect(Unit)` as a stand-in for ViewModel init (re-runs on some config changes); new object instances as composable params.

### A5. Kotlin testing (source: kotlin-testing)

- **TDD RED -> GREEN -> REFACTOR**; never skip RED.
- **Kotest** is the framework of record (pick one style and keep it): `StringSpec` (simplest), `FunSpec` (JUnit-like), `BehaviorSpec` (Given/When/Then BDD), `DescribeSpec` (RSpec). Expressive matchers (`shouldBe`, `shouldContain`, `shouldThrow<T>`, `shouldBeInstanceOf<T>`, numeric/collection matchers, custom `Matcher`).
- **MockK** for mocks: `every`/`verify` (sync), `coEvery`/`coVerify` (suspend), `slot<T>()` argument capture, `relaxed = true`, `spyk` for partial. `clearMocks` in `beforeTest`. But the employee's standing rule still holds: **prefer Fakes over Mocks in new code** - use MockK at hard boundaries, not for everything.
- **Coroutine tests**: `runTest { }`, `advanceTimeBy`/`advanceUntilIdle`, `StandardTestDispatcher`; never `Thread.sleep`. Test StateFlow with **Turbine** (`viewModel.state.test { awaitItem() ... }`).
- **Property-based testing** with Kotest `forAll`/`checkAll` + `Arb` generators for pure functions and serialization roundtrips.
- **Data-driven** `withData(...)`. **Lifecycle hooks** `beforeSpec`/`afterSpec`/`beforeTest` + reusable `Extension`s.
- **Coverage with Kover**: `koverHtmlReport`/`koverVerify`; gate the build with `minBound(80)`; exclude generated/config. Targets: critical logic 100%, public API 90%+, general 80%+.
- **Ktor route tests** via `testApplication { application { configureRouting() }; client.get(...) }`.

### A6. Server-side Kotlin for the shared backend (sources: kotlin-ktor-patterns, kotlin-exposed-patterns)

Relevant when the mobile team owns a KMP shared module or a thin Kotlin BFF. Owns the **app side**; the server proper still belongs to backend/full-stack (see hand-offs).

- **Ktor**: plugin-based `Application.module()` wiring (Serialization, Authentication, StatusPages, CORS, DI, Routing as separate `configureX()` functions); routing DSL with `authenticate { }` blocks; `kotlinx.serialization` (`@Serializable` models, `ignoreUnknownKeys`); JWT auth; `StatusPages` for centralized error -> HTTP-status mapping; Koin DI; request validation; WebSockets; config via `application.yaml`.
- **Exposed ORM**: two styles - DSL (`UsersTable.selectAll().where { }`) and DAO (`UserEntity.new { }`). All ops inside `newSuspendedTransaction { }` for coroutine safety + atomicity. HikariCP pool (`isAutoCommit = false`, sized `maximumPoolSize`). Flyway versioned migrations at startup. Repository interface wraps Exposed so business logic is decoupled and tests run against in-memory H2. JSONB columns via kotlinx.serialization.

---

## Pack B - Dart / Flutter

### B1. Idiomatic Dart + Flutter patterns (source: dart-flutter-patterns)

- **Null safety**: avoid `!`; prefer `?.`/`??`, Dart 3 pattern matching (`switch (user) { User(:final name) => ... null => ... }`), and early-return guards (which promote to non-null). **Avoid `late` overuse** - it defers null errors to runtime; only use when init is guaranteed before first access (e.g. an `AnimationController` set in `initState`).
- **Immutable state**: `sealed class` hierarchies for exhaustive `switch`; **Freezed** (`@freezed`, `copyWith`, `fromJson`/`toJson`) to kill boilerplate.
- **Async composition**: structured concurrency with Dart 3 records + `.wait` (`final (a, b) = await (f1, f2).wait;`); `StreamBuilder` with `switch` on `AsyncSnapshot`. **CRITICAL: after any `await` in a `StatefulWidget`, check `if (!mounted) return;` before touching `context`** - stale context after an async gap crashes.
- **Widget architecture**: **extract to widget classes, not `_build*()` methods** (enables `const`, element reuse, framework optimization); aggressive `const` propagation to stop rebuilds; scoped rebuilds (isolate the changing subtree in its own `ConsumerWidget`, keep siblings `const`).
- **State management** (the pack ships BLoC/Cubit and Riverpod idioms): Cubit `emit(...)` state transitions with `BlocBuilder` + `switch`; Riverpod `@riverpod` async providers, `Notifier`s with immutable list mutations, and derived/selector providers (`cartCount`, `cartTotal` using `firstWhereOrNull` to avoid `StateError`).
- **Navigation**: GoRouter with `refreshListenable: GoRouterRefreshStream(authCubit.stream)` and a centralized `redirect` for auth guards; `ShellRoute` for persistent shells; typed `pathParameters`.
- **Networking**: Dio with an auth interceptor and a **one-time retry guard** on 401 refresh (`extra['_isRetry']`) to prevent infinite refresh loops.
- **Error handling**: global `FlutterError.onError` + `PlatformDispatcher.instance.onError` -> Crashlytics; custom `ErrorWidget.builder` for release.
- **Testing**: `test` for use cases, `blocTest` for Cubits/BLoCs, `testWidgets` with `ProviderScope(overrides: [...])`; Fakes over mocks.

### B2. Flutter/Dart code-review checklist (source: flutter-dart-code-review)

A library-agnostic review gate (15 sections). Run it on any Flutter PR. Highest-signal items:

- **Project health**: feature/layer-first structure; no business logic in widgets; strict `analysis_options.yaml` (`strict-casts`/`strict-inference`/`strict-raw-types` + a lint set like very_good_analysis or flutter_lints); no `print()` in prod (use `dart:developer log()`); generated files current.
- **Dart pitfalls**: excessive `!`; broad `catch (e)` without `on`; catching `Error` subtypes (they signal bugs); unused `async`; `late` overuse; `StringBuffer` over `+` in loops; ignored `Future`s (use `await` or `unawaited()`); `final`/`const` over `var`; `package:` imports over relative; unmodifiable views over raw mutable collections; Dart 3 records over throwaway DTOs.
- **Widgets**: build method <~80-100 lines; split by rebuild boundary; `_build*()` helpers extracted to classes; correct `Key` choice (`ValueKey` in lists, `GlobalKey` sparingly, never `UniqueKey` in `build`); theme-driven colors/text (`Theme.of(context).colorScheme`/`textTheme`, no hardcoded hex); no I/O or `.listen()` in `build`.
- **State management (library-agnostic)**: logic outside widgets; DI not internal construction; repository layer between state and data; single-responsibility managers; **model mutually-exclusive states with sealed/union/`AsyncValue`, never boolean-flag soup** (`isLoading` + `hasError` allows impossible combos); every async op has loading/success/error; exhaustive UI handling; narrow consumer scopes + selectors; cancel all `.listen()`/timers/controllers in `dispose`; `context.mounted` guard after await; never store `BuildContext` in singletons.
- **Performance**: no `setState` at root; `RepaintBoundary` around independent subtrees; no sort/filter/regex in `build`; `MediaQuery.sizeOf` over `.of`; image caching + `cacheWidth`/`cacheHeight` + placeholders; `ListView.builder` for large lists; `AnimatedOpacity`/`FadeTransition` over `Opacity` in animations.
- **Accessibility**: `Semantics`/`ExcludeSemantics`/`MergeSemantics`; image `semanticLabel`; contrast >= 4.5:1; tap targets >= 48x48; color not the sole state indicator; text scales with system font size.
- **Security**: secrets in Keychain/EncryptedSharedPreferences, never plaintext; API keys via `--dart-define`/excluded `.env`, never hardcoded; backend proxy for true secrets; validate + sanitize deep-link URLs before navigation; HTTPS enforced; certificate pinning for high-security apps.
- **Plus**: dependency review (pub points 130+/160, verified publisher, fresh publish date, caret constraints, `flutter pub outdated`); typed route args + centralized guards; framework error handling wired to Crashlytics/Sentry with user-friendly messages (never raw exception strings to users); i18n (no hardcoded strings, ICU plurals, RTL); DI on abstractions; static analysis enforced in CI.
- A **state-management mapping table** translates each universal principle to its concrete form in BLoC / Riverpod / Provider / GetX / MobX / Signals / built-in (container, consumer, selector, side-effect, disposal, testing).

---

## Pack C - Swift / SwiftUI / iOS

### C1. SwiftUI patterns with the Observation framework (source: swiftui-patterns)

- **Use `@Observable` (NOT `ObservableObject`/`@Published`/`@StateObject`/`@EnvironmentObject`)** for new code - it tracks property-level changes so only views reading a changed property re-render.
- **Property-wrapper selection table**: `@State` (view-local value types), `@Binding` (two-way to parent state), `@Observable class + @State` (owned model), `@Observable class` no-wrapper (read-only passed in), `@Bindable` (two-way to an `@Observable` property), `@Environment` (injected shared deps).
- **ViewModel**: `@Observable final class` with `private(set)` outputs; `init(repository: any Repo = Default())` for DI; `func load() async { isLoading = true; defer { isLoading = false }; ... }`. View consumes via `@State private var viewModel`, kicks work off in `.task { await viewModel.load() }`.
- **Environment injection** replaces `@EnvironmentObject`: `.environment(authManager)` to inject, `@Environment(AuthManager.self)` to consume.
- **View composition**: extract small subviews so a state change invalidates only the subview reading it; `ViewModifier` + a `View` extension for reusable styling.
- **Type-safe navigation**: an `@Observable Router { var path = NavigationPath() }` + a `Hashable` `Destination` enum + `NavigationStack(path:)` with `.navigationDestination(for:)`.
- **Performance**: `LazyVStack`/`LazyHStack` for large collections; stable `id` in `ForEach` (never array index); no I/O or heavy compute in `body` (use `.task {}`); minimize `.shadow`/`.blur`/`.mask` in lists (offscreen render); conform expensive views to `Equatable` to skip re-renders.
- **Previews**: `#Preview("state") { View(viewModel: ...(repository: MockRepo())) }`.
- Anti-patterns: legacy Observation wrappers in new code; async in `body`/`init`; child-owned `@State` view models for data it doesn't own; `AnyView` erasure (use `@ViewBuilder`/`Group`); ignoring `Sendable` across actor boundaries.

### C2. Swift 6.2 Approachable Concurrency (source: swift-concurrency-6-2)

- **Mental model**: in 6.2, code is **single-threaded by default and async stays on the calling actor** - this eliminates the implicit background offloading that caused spurious data-race errors in 6.0/6.1. Concurrency is now opt-in.
- **Write on MainActor first, optimize later.** Enable **MainActor default-inference mode** for app/executable targets so most types are implicitly `@MainActor` with no annotations.
- **Isolated conformances**: a MainActor type can conform to a non-isolated protocol via `extension T: @MainActor SomeProtocol` - the compiler ensures it's only used on the main actor. Use this instead of `nonisolated`/`@Sendable` workarounds.
- **Globals/statics**: protect shared mutable static state with `@MainActor` (or default inference).
- **`@concurrent` for real parallelism**: only for CPU-intensive work (image processing, compression, heavy compute). Recipe: mark the type `nonisolated`, add `@concurrent` + `async` to the function, `await` at call sites. **Profile with Instruments before offloading** - most async functions do NOT need it.
- **Migration**: enable Approachable Concurrency in Xcode 26 build settings (or SPM `SwiftSettings`), use the swift.org migration tooling, turn features on incrementally; data-race issues surface as compile-time errors.
- Anti-patterns: `@concurrent` on every async function; `nonisolated` to silence the compiler without understanding isolation; keeping legacy `DispatchQueue` where actors give the same safety; fighting the compiler (a reported data race is a real one).

### C3. Actor-based persistence (source: swift-actor-persistence)

- **`public actor LocalRepository<T: Codable & Identifiable>`** - the actor model serializes access, so the compiler guarantees no data races with zero manual locks/`DispatchQueue`.
- **In-memory cache (`[String: T]`) + file-backed storage**: O(1) reads from cache, durable atomic writes (`data.write(to:options:.atomic)` to survive mid-write crashes).
- **Load synchronously in `init`** (actor isolation isn't active yet) to avoid async-init complexity for local files.
- All method calls are `await` from callers. Combine with an `@Observable` ViewModel: `func load() async { questions = await repository.loadAll() }`.
- Keep the public API minimal (domain ops only, never expose the internal cache). Use `Sendable` types across the actor boundary. Don't `nonisolated` your way around isolation.
- Use for local user data/settings/cached content and offline-first stores that sync later - the Swift-native counterpart to the Android Room "local DB is source of truth" rule.

### C4. Protocol-based DI + Swift Testing (source: swift-protocol-di-testing)

- **Abstract each external concern behind a small, focused, `Sendable` protocol** (`FileSystemProviding`, `FileAccessorProviding`, `BookmarkStorageProviding`) - one responsibility each, no god-protocols.
- Ship a `Default*` production implementation and a `Mock*` test implementation with configurable error properties (`readError`, `writeError`) to exercise failure paths deterministically without real I/O.
- **Inject via default parameters**: `init(fileSystem: FileSystemProviding = DefaultFileSystemProvider(), ...)` - production uses real impls, tests pass mocks. Works for actors too.
- **Test with the Swift Testing framework**: `@Test("...") func ... async`, `#expect(...)`, `await #expect(throws: SomeError.self) { try await ... }`.
- Only mock boundaries (file system, network, external APIs). Don't mock internal types with no external deps; don't use `#if DEBUG` instead of DI.

### C5. Liquid Glass design system, iOS 26 (source: liquid-glass-design)

A dynamic material that blurs content behind it, reflects surrounding light/color, and reacts to touch/pointer. Covers SwiftUI, UIKit, WidgetKit.

- **SwiftUI**: `.glassEffect()` (default regular/capsule); customize `.glassEffect(.regular.tint(.orange).interactive(), in: .rect(cornerRadius: 16))`; shapes `.capsule`/`.rect(cornerRadius:)`/`.circle`. Button styles `.glass` and `.glassProminent`.
- **Always wrap multiple glass views in a `GlassEffectContainer(spacing:)`** - it enables morphing and improves render performance; `spacing` controls how close elements must be to merge their shapes. Apply `.glassEffect()` AFTER frame/font/padding.
- **Unite** shapes with `.glassEffectUnion(id:namespace:)`; **morph** appear/disappear transitions with `@Namespace` + `.glassEffectID(id, in:)` inside `withAnimation`.
- **UIKit**: `UIGlassEffect` (`tintColor`, `isInteractive`) in a `UIVisualEffectView` (`clipsToBounds = true` with corner radius); `UIGlassContainerEffect(spacing:)` for groups; scroll-edge effects (`scrollView.topEdgeEffect.style`); `hidesSharedBackground` to opt a toolbar item out of the shared glass.
- **WidgetKit**: detect `@Environment(\.widgetRenderingMode)` (`.accented` vs full color); group with `.widgetAccentable()`; `.widgetAccentedRenderingMode(.monochrome)` for images; `.containerBackground(for: .widget)`.
- Best practice: reserve glass for interactive elements / toolbars / cards; test light + dark + accented/tinted; keep text contrast readable. Anti-patterns: standalone glass views without a container; over-nesting; glass on every view; opaque backgrounds behind glass; forgetting `clipsToBounds` in UIKit.

### C6. On-device foundation models (source: foundation-models-on-device)

Apple's `FoundationModels` on-device LLM (iOS 26+) - private, offline-capable AI.

- **Always check `SystemLanguageModel.default.availability` first** and handle every case (`.available`, `.unavailable(.deviceNotEligible / .appleIntelligenceNotEnabled / .modelNotReady / other)`). Never assume availability.
- **Sessions**: `LanguageModelSession()` single-turn; reuse a session with `instructions:` for multi-turn context. Instructions take priority over prompts - define role, task, style, safety. One request per session at a time (check `isResponding`); spin up multiple sessions for concurrency.
- **Guided generation** with `@Generable` structs + `@Guide(description:, .range(...)/.count(...))` constraints: `try await session.respond(to:, generating: CatProfile.self)`, then read typed fields off `response.content`. Stronger than parsing raw strings.
- **Tool calling**: a `struct X: Tool` with `name`, `description`, a `@Generable struct Arguments`, and `func call(arguments:) async throws -> ToolOutput`; pass `tools:` to the session; handle `LanguageModelSession.ToolCallError`.
- **Snapshot streaming**: `session.streamResponse(to:, generating:)` yields `T.PartiallyGenerated` (all-Optional) snapshots - bind to SwiftUI `@State` for progressive UI; each snapshot is a complete partial state, not a delta.
- **Constraints**: ~4,096-token window covers instructions + prompt + output combined - chunk large inputs. Access results via **`.content`, not `.output`**. Tune with `GenerationOptions(temperature:)`. Profile with Instruments.
- This is the on-device, privacy-preserving option; for cloud/larger models hand off to the AI/ML Engineer (model selection, conversion to Core ML / TFLite already in SKILL.md).

---

## How this pack maps onto existing files

| Topic | This pack | Existing file |
|-------|-----------|---------------|
| Kotlin language idioms | Pack A1-A2, A5-A6 | (new depth) |
| Android module/layer skeleton | Pack A3-A4 (language depth) | `android-architecture.md` (NowInAndroid skeleton - load both) |
| Compose UI patterns | Pack A4 | `android-architecture.md` (Route/Screen split) |
| Flutter/Dart | Pack B1-B2 | SKILL.md listed Flutter; this is the depth |
| Swift / SwiftUI / iOS 26 | Pack C1-C6 | SKILL.md listed native iOS; this is the depth |
| Testing | Pack A5 (Kotlin), B (Flutter review), C4 (Swift Testing) | `mobile-test-and-release.md` (E2E/visual/release layers - committed suite) |
| Release / store | (unchanged) | `mobile-test-and-release.md` |
| Device automation | (unchanged) | `mobile-mcp-operator.md` |

**Default stack reminder:** React Native + Expo remains the Solaris default for cross-platform client work (SKILL.md stack-priority order). Reach for these native packs when iOS/Android-specific features, fidelity, or performance demand native, or when the project is natively Kotlin/Swift/Flutter from the start.
