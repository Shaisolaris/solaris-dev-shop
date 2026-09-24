# Unreal C++ Quality and Build - language-level review, standards, testing, build-fix loop (depth)

> **Depth absorption 2026-06-14 (v0.3.0).** C++ LANGUAGE methodology lifted (methodology only, no code bundled) from `affaan-m/ECC` (everything-claude-code, MIT) skills `cpp-reviewer`, `cpp-coding-standards`, `cpp-testing`, `cpp-build-resolver`. The ECC standards are grounded in the [C++ Core Guidelines](https://isocpp.github.io/CppCoreGuidelines) (isocpp.org). This file is the LANGUAGE-quality layer; the engine layer lives in `unreal-gameplay-patterns.md` (GAS / perf / networking / packaging) and `unreal-testing-pipeline.md` (PIE / UE Automation / cook). Do not duplicate engine work here - this is "is the C++ itself safe, modern, correct, and does it build", not "how do abilities or replication work".

**Gate-0 (vs existing content).** Before this file the employee had ZERO C++-language methodology: nothing on memory safety, smart pointers, RAII, Rule of Five, const-correctness, concurrency races, GoogleTest, or a C++/CMake build-error-fix loop. The engine files cover Unreal subsystems but assume the underlying C++ is already sound. This is the missing quality + build-fixing delta for Unreal gameplay C++. PASS.

**Unreal adaptation up front (so this stays a delta, not a generic C++ doc).** Unreal is not vanilla C++. Three things change how the Core Guidelines apply, and they are flagged inline throughout:
1. **The UObject GC layer.** UObjects are NOT managed by `std::unique_ptr`/`std::shared_ptr`. They are garbage-collected and kept alive by `UPROPERTY()` reflection. Use `TObjectPtr<T>` (UE5) for member references and the U-prefixed containers (`TArray`, `TMap`, `TSet`, `FString`) for engine-facing code. The smart-pointer rules below apply in full force to **plain C++** (non-UObject helpers, math, data structs, third-party-style libraries, server/tool code) and to manual native resources (file handles, sockets, OS handles) inside the engine.
2. **UE has its own coding standard** (PascalCase types, `b`-prefixed bools, no exceptions by default in engine code). Where Epic's convention and the Core Guidelines disagree on *style* (naming, `endl`), follow Epic in engine modules. Where they agree on *safety* (RAII, init-on-declare, no raw `new/delete` for native resources, no data races), the Core Guidelines win everywhere.
3. **The build system is UBT, not raw CMake.** The CMake/CTest workflow below applies to standalone C++ (tools, server-side, plugins built outside the editor, unit-test harnesses). For the in-editor build, drive UBT via `system_control` (see `unreal-testing-pipeline.md`). The *error-diagnosis discipline* (read the error, minimal surgical fix, rebuild, re-verify) is identical regardless of build system.

---

## Part 1 - The C++ review pass (memory safety, modern C++, concurrency)

Run this as a dedicated review whenever a chunk of gameplay or tool C++ is written or changed - the engine-side review (does the ability/replication design hold) is separate and lives in the gameplay-patterns file. This is "is the C++ safe and idiomatic".

### How to start a review
1. Diff the C++ that changed: `git diff -- '*.cpp' '*.h' '*.hpp' '*.cc' '*.cxx'`.
2. Run the static analyzers if the project has them: `clang-tidy` and `cppcheck`. For Unreal modules, also lean on the editor's own compile warnings and the UnrealHeaderTool (UHT) output - UHT catches reflection/UPROPERTY mistakes a generic linter cannot.
3. Triage by severity. Block on CRITICAL/HIGH, warn on MEDIUM. Do not approve C++ with a memory-safety or concurrency defect.

### CRITICAL - Memory safety (block)
- **Raw `new`/`delete` for native resources** - use `std::unique_ptr`/`std::shared_ptr` (plain C++) or `TUniquePtr`/`TSharedPtr` (Unreal non-UObject types). For UObjects, never `new`/`delete` - use `NewObject`/`SpawnActor` and let GC + `UPROPERTY`/`TObjectPtr` keep them alive.
- **Buffer overflows** - C arrays, `strcpy`, `sprintf` without bounds. Prefer `std::array`/`std::vector` (or `TArray`/`FString` in engine code).
- **Use-after-free / dangling** - invalidated iterators, pointers outliving their object. In Unreal the classic version is holding a raw `AActor*` after the actor was destroyed: store a `TWeakObjectPtr` and check validity, or a `UPROPERTY` `TObjectPtr` so GC tracks it.
- **Uninitialized variables** - reading before assignment. Always initialize at declaration (ES.20).
- **Memory leaks** - missing RAII, resources not tied to object lifetime.
- **Null dereference** - pointer access without a null/`IsValid()` check.

### CRITICAL - Security (block)
- **Command injection** - unvalidated input into `system()`/`popen()`.
- **Format-string attacks** - user input as a `printf`/`UE_LOG` format string (pass it as an argument, never as the format).
- **Integer overflow** - unchecked arithmetic on untrusted input.
- **Hardcoded secrets** - API keys, passwords in source. (Reinforces the standing rule: never ship keys in a packaged build; route LLM/GenAI keys through a backend.)
- **Unsafe casts** - `reinterpret_cast` without justification; never cast away `const` (ES.50). Prefer `Cast<T>()` for UObjects (it is checked) over C-style or `reinterpret_cast`.

### HIGH - Concurrency (block)
Unreal gameplay logic is mostly single-threaded on the Game thread, but tasks, `Async`, the task graph, render-thread interaction, and tool/server code all introduce real concurrency. Apply CP.* in full there.
- **Data races** - shared mutable state without synchronization (CP.2). Minimize shared writable data (CP.3); think in tasks not threads (CP.4).
- **Deadlocks** - multiple mutexes locked in inconsistent order. Use `std::scoped_lock` (or `FScopeLock` in engine code) to take several at once (CP.21).
- **Manual lock/unlock** - never plain `lock()`/`unlock()`; always RAII-named guards (`std::lock_guard`/`FScopeLock`) (CP.20, CP.44). An unnamed guard destroys immediately and locks nothing.
- **`volatile` for synchronization** - wrong tool; it is for hardware I/O only (CP.8). Use atomics/mutexes.
- **Detached threads** - `std::thread` without `join()`/`detach()`, or detaching at all (CP.26) - lifetime becomes unmanageable. Prefer the UE task system.
- **Calling unknown code while holding a lock** (CP.22) - deadlock risk. Never call a delegate/callback under a lock.
- **Touching UObjects / the engine off the Game thread** - Unreal-specific landmine: most `UObject`/actor/world APIs are NOT thread-safe. Marshal back to the Game thread (`AsyncTask(ENamedThreads::GameThread, ...)`) before touching them.

### HIGH - Code quality (block)
- **No RAII** - manual resource management instead of tying lifetime to an object (R.1).
- **Rule of Five violations** - if you define or `=delete` any of destructor / copy ctor / copy assign / move ctor / move assign, handle all five (C.21). If you manage no resource, define none - Rule of Zero (C.20).
- **Large functions** (over ~50 lines) and **deep nesting** (over 4 levels) - F.3, ES.5: keep functions short, scopes small.
- **C-style code** - `malloc`/`free` (R.10), C arrays, `typedef` instead of `using` (T.43).

### MEDIUM - Performance and best practice (warn)
- **Unnecessary copies** - pass big objects by `const&`, not by value (F.16); `std::move` sink parameters (F.18).
- **Missing `reserve()`** on a known-size vector/`TArray`; string concat in a loop (use a stream / `reserve`).
- **`const`-correctness** - const member functions by default (Con.2); pass pointers/refs to `const` (Con.3); make objects `const`/`constexpr` unless mutated (Con.1, ES.25).
- **`enum class` over plain `enum`** (Enum.3); `nullptr` over `0`/`NULL` (ES.47); no narrowing conversions (ES.46); no magic numbers (ES.45).
- **`explicit` single-argument constructors** (C.46); virtual functions marked exactly one of `virtual`/`override`/`final` (C.128); polymorphic base destructor public-virtual or protected-non-virtual (C.35).
- **Include hygiene** - include guards / `#pragma once`, self-contained headers, never `using namespace` at global scope in a header (SF.7, SF.8, SF.11). In Unreal, also keep includes IWYU-clean (Include-What-You-Use) to keep compile times sane.

### Approval criteria
- **Approve** - no CRITICAL or HIGH issues.
- **Warn** - MEDIUM only.
- **Block** - any CRITICAL or HIGH. A memory-safety or data-race defect is never "ship it and clean up later".

---

## Part 2 - The standard (C++ Core Guidelines, the cross-cutting six)

These six themes are the foundation; everything in Part 1 is a specialization of them. They are the bar for plain C++ and for the safety-relevant parts of engine C++ alike.
1. **RAII everywhere** (P.8, R.1, E.6, CP.20) - bind resource lifetime to object lifetime. The single highest-leverage rule.
2. **Immutability by default** (P.10, Con.1-5, ES.25) - start `const`/`constexpr`; mutability is the exception you justify.
3. **Type safety** (P.4, I.4, ES.46-49, Enum.3) - use the type system to catch errors at compile time. Strong types over bare `double`/`int`; `enum class` over magic ints.
4. **Express intent** (P.3, F.1, NL.1) - names and types communicate purpose. (Style note: in engine code follow Epic's naming; the *principle* still holds.)
5. **Minimize complexity** (F.2-3, ES.5) - one logical operation per function, short functions, small scopes.
6. **Value semantics over pointer semantics** (C.10, R.3-5, F.20) - return by value, prefer scoped objects, raw pointers are non-owning observers (R.3). (Unreal exception: UObjects are reference-semantic and GC-owned by design - "value semantics" applies to your plain data types, not to actors/components.)

### The smart-pointer ownership rules (plain C++ + native resources)
- `make_unique`/`make_shared` - never naked `new`/`delete` (R.11, R.22).
- `unique_ptr` over `shared_ptr` unless ownership is genuinely shared (R.21).
- A raw `T*` is a non-owning observer - never transfer ownership through it (R.3, I.11).
- **Unreal mapping:** plain C++ -> `std::unique_ptr`/`std::shared_ptr`; non-UObject Unreal types -> `TUniquePtr`/`TSharedPtr`/`TSharedRef`; UObjects -> `TObjectPtr`/`UPROPERTY` (GC-owned) and `TWeakObjectPtr` for non-owning references that must survive the referent being destroyed.

### Rule of Zero / Rule of Five (C.20, C.21)
Prefer Rule of Zero: hold your members in types that already manage themselves (smart pointers, containers) and let the compiler generate the special members. Only when you wrap a raw native resource (a `FILE*`, a socket) do you write all five - and then move ops are `noexcept`. This is the most common source of subtle leaks and double-frees in gameplay tool code.

### Error handling (E.*)
Custom exception types, throw by value, catch by reference (E.14, E.15); RAII guarantees cleanup on the way out (E.6); destructors never throw (E.16); do not catch everything everywhere (E.17). **Unreal caveat:** engine code largely runs with exceptions disabled - inside engine modules prefer `check()`/`ensure()`/`TOptional`/explicit return codes and reserve C++ exceptions for standalone/tool/server code where they are enabled.

### The quick checklist (run before calling C++ work done)
- [ ] No raw `new`/`delete` for native resources; UObjects via `NewObject`/`SpawnActor` + `UPROPERTY`/`TObjectPtr` (R.11)
- [ ] Everything initialized at declaration (ES.20)
- [ ] `const`/`constexpr` by default; const member functions where possible (Con.1, Con.2, ES.25)
- [ ] `enum class`, `nullptr`, no narrowing, no C-style casts, no magic numbers (Enum.3, ES.46-48)
- [ ] Single-arg ctors `explicit`; Rule of Zero or full Rule of Five (C.46, C.20, C.21)
- [ ] Virtual functions tagged once (`virtual`/`override`/`final`); base dtor public-virtual or protected-non-virtual (C.128, C.35)
- [ ] Headers self-contained with guards; no global `using namespace` in headers; IWYU-clean (SF.7, SF.8, SF.11)
- [ ] Locks are RAII and named (`scoped_lock`/`lock_guard`/`FScopeLock`) (CP.20, CP.44)
- [ ] No UObject/world access off the Game thread without marshaling back
- [ ] Templates constrained with concepts where the project is C++20 (T.10)

---

## Part 3 - C++ testing (GoogleTest/GoogleMock + CTest)

Two test surfaces, used deliberately - do not conflate them:
- **UE Automation framework** (Functional / `IMPLEMENT_SIMPLE_AUTOMATION_TEST`, Gauntlet) - for anything that needs the engine, a world, actors, PIE. This is the default for gameplay and is covered in `unreal-testing-pipeline.md`. Run it via `system_control`.
- **GoogleTest/GoogleMock + CTest** - for **plain C++** that does NOT need the engine: math, algorithms, data structures, parsers, server/tool code, standalone libraries and plugins. This is faster, runs in CI without an editor, and is where the methodology below applies. Choosing the cheaper surface is itself the skill: if a unit does not touch UObjects, test it with GoogleTest, not by booting the editor.

### TDD loop
RED (write a failing test that captures the behavior) -> GREEN (smallest change to pass) -> REFACTOR (clean up while green). Keep tests deterministic and isolated; prefer dependency injection and fakes over global state.

### The patterns
- **Plain test:** `TEST(SuiteName, DoesTheThing) { EXPECT_EQ(Add(2,3), 5); }`. `ASSERT_*` for preconditions that must hold before continuing, `EXPECT_*` for independent checks (so one failure does not mask the rest).
- **Fixture:** subclass `::testing::Test`, build shared state in `SetUp()`, tear down in `TearDown()`; use `TEST_F`. Hold members in smart pointers so the fixture self-cleans.
- **Mock vs fake:** `MOCK_METHOD(...)` + `EXPECT_CALL(...).Times(n)` to assert **interactions**; a hand-written **fake** for **stateful** behavior. Do not over-mock simple value objects - prefer a fake when you need real behavior.
- **Layout:** `tests/unit`, `tests/integration`, `tests/testdata`; label or directory-separate unit vs integration in CTest.

### CMake/CTest wiring (standalone C++ targets)
Use `FetchContent` to pull GoogleTest at a **pinned version** (project policy; do not float to a moving tag), `enable_testing()`, and `gtest_discover_tests()` for stable discovery. Run with `ctest --test-dir build --output-on-failure`; filter a single test with `-R Name` or `--gtest_filter=`. (Full CMake/CTest snippets live in the ECC `cpp-testing` skill; the methodology - pin the dep, discover tests, run subset-then-full - is the part to carry.)

### Sanitizers and coverage (the high-value CI additions)
- **Sanitizer builds in CI** - AddressSanitizer (ASan, use-after-free/overflow), UndefinedBehaviorSanitizer (UBSan), ThreadSanitizer (TSan, data races). Gate them as opt-in CMake options on dedicated build dirs. A green test suite under ASan/TSan is worth far more than the same suite without. (Note: TSan and Unreal's editor do not mix well - run sanitizers on the standalone C++ targets, not the full editor.)
- **Coverage** - `--coverage`/gcov+lcov (GCC) or `-fprofile-instr-generate -fcoverage-mapping`+llvm-cov (Clang), as target-level options not global flags.

### Flaky-test guardrails (the discipline that keeps CI trustworthy)
- Never `sleep()` for synchronization - use condition variables / latches / bounded waits.
- Unique temp directory per test; always clean it. No fixed temp paths.
- No real time / network / filesystem in unit tests - inject a clock, fake the I/O.
- Deterministic seeds for randomized inputs.
- Reset or remove global state in fixtures.

### Optional, only if the project already has it
libFuzzer (pure functions, minimal I/O) or property testing (RapidCheck) for invariants. Catch2 / doctest are lighter GoogleTest alternatives if the project standardizes on them.

---

## Part 4 - The C++/CMake build-error-fix loop

When C++ fails to compile or link, do NOT thrash. Run a tight, surgical loop. This applies to standalone CMake C++; for the in-editor build the same diagnosis discipline applies but the command is a UBT build via `system_control` and you also read UHT/editor compile output (and recall the standing rule: first-open "plugin failed to load" is expected - close + reopen, do not chase it as a real failure).

### The loop
1. **Build, read the FIRST error** - `cmake --build build 2>&1 | head -100` (or the UBT build via `system_control`). Compilers cascade; fix the first error, the rest often vanish. Read the message; never guess.
2. **Read the affected file** - understand the context before editing.
3. **Apply the minimal, surgical fix** - only what the error needs. Do not refactor while fixing a build.
4. **Rebuild to verify** the fix.
5. **Run the tests** - `ctest --test-dir build --output-on-failure` (or UE Automation via `system_control`) so a build fix did not silently break behavior.

### Common errors -> cause -> fix
| Error | Cause | Fix |
|-------|-------|-----|
| `undefined reference to X` / unresolved external | Missing implementation or unlinked library/module | Add the .cpp, link the lib; in UE add the module to `Build.cs` `PublicDependencyModuleNames` |
| `no matching function for call` | Wrong argument types | Fix types or add an overload |
| `use of undeclared identifier` | Missing include or typo | Add `#include` / fix the name; in UE check the generated `.generated.h` is included last |
| `multiple definition of` | Duplicate symbol | `inline`, move to .cpp, or add include guard |
| `incomplete type` | Forward declaration used where the full type is needed | Add the `#include` |
| `template argument deduction failed` | Wrong template args | Fix the template parameters |
| `no member named X in Y` | Typo or wrong class | Fix the member name |
| `CMake Error ...` | Configuration issue | Fix `CMakeLists.txt`; for UE, fix `.Build.cs`/`.Target.cs`/`.uproject` modules |

UE-specific build failures cluster around reflection: a `UPROPERTY`/`UFUNCTION` macro mistake, a missing `GENERATED_BODY()`, an out-of-order `.generated.h` include, or a module not declared in `Build.cs`. Read the UHT error, not just the C++ compiler error.

### CMake troubleshooting escalation
`-DCMAKE_VERBOSE_MAKEFILE=ON`, `--verbose`, `--clean-first` when the build is stale or caching a bad state.

### Hard discipline
- Surgical fixes only - fix the error, do not refactor.
- Never suppress a warning with `#pragma` without explicit approval - fix the root cause.
- Never change a function signature unless the error genuinely requires it.
- One fix at a time, verify after each.

### Stop conditions (do not loop forever)
Stop and report if: the same error survives 3 fix attempts; a fix creates more errors than it removes; or the fix needs architectural changes beyond the immediate scope (escalate the design instead of forcing a local patch).

### Report format
`[FIXED] path:line | Error: <message> | Fix: <what changed> | Remaining errors: N`, ending with `Build Status: SUCCESS/FAILED | Errors Fixed: N | Files Modified: <list>`.

---

## Cross-references
- `unreal-gameplay-patterns.md` - the ENGINE layer (GAS, performance profiling, networking, packaging). This file is the LANGUAGE layer underneath it; load both when writing a real gameplay system in C++.
- `unreal-testing-pipeline.md` - UE Automation tests + PIE + cook/package. Part 3 here is the GoogleTest counterpart for plain C++ that does not need the engine; that file owns the engine-test surface.
- `unreal-mcp-operator.md` - drive the in-editor UBT build via `system_control`; the build-fix discipline in Part 4 wraps it.
- `learnings.md` / `CLAUDE.md` - record recurring build/quality fixes; promote repeat lessons.

## Re-check schedule
- Quarterly with the rest of the stack: re-skim ECC (`affaan-m/ECC`, MIT) cpp-* skills for new patterns; re-check the C++ Core Guidelines for new rules as C++23/26 land and as Unreal's own coding standard evolves (TObjectPtr adoption, IWYU defaults, C++20 in UE5).
