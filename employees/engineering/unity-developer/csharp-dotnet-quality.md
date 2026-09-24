# C#/.NET Code Quality, Idioms, and Testing (language-level)

Load this file for: **C# language-level code quality** - nullable reference types, async/await idioms, immutability, the Result pattern, guard clauses, .NET anti-patterns, and C# unit/integration testing (xUnit + FluentAssertions + NSubstitute + Testcontainers). This is the **language-and-tooling delta**, distinct from the engine work in the other references. It applies to gameplay C#, Editor tooling, build scripts, and any standalone .NET service (companion backends, asset pipelines, CLI tools) Shai writes around a Unity project.

> **Scope line (Gate-0).** Engine/Editor automation, scene flow, MonoBehaviour lifecycle, and the MCP verify loop live in the other references (`unity-scene-architecture.md`, `unity-mcp-operator.md`, `coplaydev-unity-mcp.md`, `unity-testing-pipeline.md`). This file is **only** about C#-as-a-language and .NET-as-a-platform quality. It does not re-teach Unity. Where a pattern collides with Unity reality, the Unity caveat is called out inline (see "Unity caveats" boxes) so you do not blindly apply server-side idioms inside `MonoBehaviour`s.

Source: methodology absorbed from ECC (github.com/affaan-m/everything-claude-code, MIT) skills `dotnet-patterns` + `csharp-testing`. Knowledge only; no third-party code bundled.

---

## When to apply this file

- Writing or reviewing **plain C#** (non-MonoBehaviour) - services, validators, data models, save/load, networking glue, Editor tools, build/CI scripts.
- Writing or reviewing **gameplay C#** where the logic is testable in isolation (pure functions, state machines, scoring, economy, inventory).
- Standing up a **test project** for a Unity solution or a companion .NET service.
- Any code review where the question is "is this idiomatic, safe, and testable C#" rather than "is this the right scene/prefab structure."

---

## Part 1 - Idiomatic C#/.NET (the quality bar)

### 1. Nullable reference types ON, and honor them

Enable `<Nullable>enable</Nullable>` in the `.csproj`. Then the compiler tracks intent: `string` is non-null, `string?` is nullable. Treat warnings as the contract.

- Do not paper over a warning with `!` (null-forgiving) unless you can prove non-null at that point. A stray `!` is a future `NullReferenceException`.
- Public API surfaces declare nullability honestly: `Task<User?> FindByIdAsync(...)` says "may not exist"; `Task<User> GetByIdAsync(...)` says "throws if missing."
- Guard at the boundary, then trust the type inside. `ArgumentNullException.ThrowIfNull(arg);` at the top of a public method, then the body assumes non-null.

> **Unity caveat.** Unity-serialized fields (`[SerializeField] private Foo _foo;`) are assigned by the Editor, not the constructor, so the compiler thinks they are null. Initialize with `= null!;` for required serialized refs **and** null-check them in `Awake`/`OnValidate` with a clear error - the `null!` silences the compiler, the runtime check catches the unwired reference. Do not let `null!` be the only line of defense.

### 2. Prefer immutability

Use `record` and `init`-only properties for data. Mutability is an explicit, justified choice, not the default.

```csharp
public sealed record Money(decimal Amount, string Currency);

public sealed class CreateOrderRequest
{
    public required string CustomerId { get; init; }
    public required IReadOnlyList<OrderItem> Items { get; init; }
}
```

Expose collections as `IReadOnlyList<T>` / `IReadOnlyDictionary<TKey,TValue>`, not `List<T>`, on public surfaces so callers cannot mutate your internals.

> **Unity caveat.** `MonoBehaviour`/`ScriptableObject` cannot be `record`s and need parameterless construction + serializable fields, so immutability there is partial. Keep the **pure data and logic** (DTOs, value objects, config snapshots passed between systems) immutable; the engine objects stay mutable by necessity.

### 3. Explicit over implicit

Always state access modifiers and nullability. `sealed` by default on classes that are not designed for inheritance (it is also a small perf win). Constructor-inject dependencies and validate them.

```csharp
public sealed class UserService
{
    private readonly IUserRepository _repository;
    private readonly ILogger<UserService> _logger;

    public UserService(IUserRepository repository, ILogger<UserService> logger)
    {
        _repository = repository ?? throw new ArgumentNullException(nameof(repository));
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
    }
}
```

### 4. Depend on abstractions

Interfaces at service boundaries; register via DI. This is what makes the code testable (Part 3).

```csharp
public interface IOrderRepository
{
    Task<Order?> FindByIdAsync(Guid id, CancellationToken cancellationToken);
    Task AddAsync(Order order, CancellationToken cancellationToken);
}
```

> **Unity caveat.** Unity has no built-in DI container. Either keep companion .NET services on real DI (`Microsoft.Extensions.DependencyInjection`) or use a Unity DI framework (VContainer/Zenject) inside the game. Even without a container, the **interface boundary still pays off** - it lets you unit-test the logic with a hand-rolled fake, which is the whole point.

### 5. Guard clauses, flat happy path

Validate and bail early; do not nest the happy path inside `if` pyramids.

```csharp
public async Task<ProcessResult> ProcessPaymentAsync(PaymentRequest request, CancellationToken ct)
{
    ArgumentNullException.ThrowIfNull(request);
    if (request.Amount <= 0)
        throw new ArgumentOutOfRangeException(nameof(request.Amount), "Amount must be positive");
    if (string.IsNullOrWhiteSpace(request.Currency))
        throw new ArgumentException("Currency is required", nameof(request.Currency));

    // happy path, un-nested
    var gateway = _gatewayFactory.Create(request.Currency);
    return await gateway.ChargeAsync(request, ct);
}
```

### 6. The Result pattern for expected failures

Throw for **programmer errors and truly exceptional conditions**; return a `Result<T>` for **expected, recoverable failures** (validation, "not found that the caller handles," business-rule rejections). Exceptions are expensive and noisy on a hot path - in a game loop especially, do not throw for "the player tried an illegal move."

```csharp
public sealed record Result<T>
{
    public bool IsSuccess { get; }
    public T? Value { get; }
    public string? Error { get; }
    private Result(T value) { IsSuccess = true; Value = value; }
    private Result(string error) { IsSuccess = false; Error = error; }
    public static Result<T> Success(T value) => new(value);
    public static Result<T> Failure(string error) => new(error);
}
```

### 7. Options pattern for configuration

Bind config sections to strongly-typed, validated objects instead of reading magic strings.

```csharp
public sealed class SmtpOptions
{
    public const string SectionName = "Smtp";
    public required string Host { get; init; }
    public required int Port { get; init; }
    public bool UseSsl { get; init; } = true;
}
// builder.Services.Configure<SmtpOptions>(config.GetSection(SmtpOptions.SectionName));
```

> **Unity caveat.** In-game config usually lives in a `ScriptableObject` rather than `IConfiguration`. The principle carries over: **one typed, validated config object**, not scattered literals.

---

## Part 2 - async/await idioms (the deadlock and leak killers)

### Async all the way; never block on async

```csharp
// GOOD
public async Task<OrderSummary> GetOrderSummaryAsync(Guid id, CancellationToken ct)
{
    var order = await _repository.FindByIdAsync(id, ct)
        ?? throw new NotFoundException($"Order {id} not found");
    var customer = await _customerService.GetAsync(order.CustomerId, ct);
    return new OrderSummary(order, customer);
}

// BAD - .Result / .Wait() can deadlock and always wastes a thread
var order = _repository.FindByIdAsync(id, CancellationToken.None).Result;
```

### Thread a `CancellationToken` through every async method

Accept it, pass it down, and honor it. This is how you cancel a load when the player backs out, time out a stuck network call, and stop tests from hanging. **Always plumb it; never swallow it.**

### Run independent async work concurrently

```csharp
var ordersTask  = _orderService.GetRecentAsync(ct);
var metricsTask = _metricsService.GetCurrentAsync(ct);
var alertsTask  = _alertService.GetActiveAsync(ct);
await Task.WhenAll(ordersTask, metricsTask, alertsTask);
return new DashboardData(await ordersTask, await metricsTask, await alertsTask);
```

### `async void` is banned (except UI/event handlers)

`async void` cannot be awaited and its exceptions crash the process instead of surfacing to a caller. Return `Task`. The only exception is a genuine event handler, and even then keep its body tiny and try/catch it.

> **Unity caveat.** Unity's natural async unit is the **coroutine** (`IEnumerator` + `yield return`) and, on modern Unity, `Awaitable`/`UniTask`. Raw `Task`-based async works but watch two things: (1) `Task` continuations may not resume on the main thread - use `UniTask` or `Awaitable` for main-thread affinity before touching the scene; (2) tie cancellation to the object's lifetime (`destroyCancellationToken` / `MonoBehaviour` `OnDestroy`) so a `Task` does not run after the GameObject is gone. The **idioms** (token-threaded, no blocking, no `async void`) are identical; the **scheduler** differs.

---

## Part 3 - C#/.NET testing patterns

### Framework stack

| Tool | Purpose |
|---|---|
| **xUnit** | Test framework (preferred for .NET; fresh class instance per test = isolation by default) |
| **FluentAssertions** | Readable assertions (`result.Should().Be(...)`) |
| **NSubstitute** / **Moq** | Mock dependencies behind interfaces |
| **Testcontainers** | Real infrastructure (Postgres, Redis) in integration tests |
| **WebApplicationFactory** | In-process ASP.NET Core integration tests |
| **Bogus** | Realistic fake data |

> **Unity caveat.** Inside the Unity project itself, tests run on the **Unity Test Framework (UTF / NUnit)** in EditMode/PlayMode via `tests-run` (see `unity-testing-pipeline.md` Tier 0), not xUnit. Use the xUnit/FluentAssertions stack for **companion .NET projects and pure-C# libraries** that build outside Unity. The discipline below - AAA, behavior-not-implementation, one logical assertion, fakes behind interfaces, deterministic async - applies to **both** stacks. Pure gameplay logic that does not touch `UnityEngine` is worth extracting into a plain C# assembly precisely so it can be tested with the faster, richer xUnit stack.

### Arrange-Act-Assert + the SUT convention

```csharp
public sealed class OrderServiceTests
{
    private readonly IOrderRepository _repository = Substitute.For<IOrderRepository>();
    private readonly OrderService _sut;
    public OrderServiceTests() => _sut = new OrderService(_repository,
        Substitute.For<ILogger<OrderService>>());

    [Fact]
    public async Task PlaceOrderAsync_ReturnsFailure_WhenNoItems()
    {
        // Arrange
        var request = new CreateOrderRequest { CustomerId = "c1", Items = [] };
        // Act
        var result = await _sut.PlaceOrderAsync(request, CancellationToken.None);
        // Assert
        result.IsSuccess.Should().BeFalse();
        result.Error.Should().Contain("at least one item");
    }
}
```

Name tests by behavior: **`Method_ExpectedResult_WhenCondition`**.

### Parameterized cases - `[Theory]` over copy-pasted `[Fact]`s

```csharp
[Theory]
[InlineData("", false)]
[InlineData("user@example.com", true)]
public void IsValidEmail_ReturnsExpected(string email, bool expected)
    => EmailValidator.IsValid(email).Should().Be(expected);
```

Use `[MemberData]` / `TheoryData<...>` for complex object cases.

### Mocking and verifying interactions (NSubstitute)

```csharp
_repository.FindByIdAsync(id, Arg.Any<CancellationToken>()).Returns((Order?)null);
// ... act ...
await _repository.Received(1).AddAsync(
    Arg.Is<Order>(o => o.CustomerId == request.CustomerId),
    Arg.Any<CancellationToken>());
```

### Test data builders (fluent, readable setup)

```csharp
var order = new OrderBuilder()
    .WithCustomer("cust-vip")
    .WithItem("SKU-PREMIUM", 3, 99.99m)
    .Build();
```

### Integration tests

- **`WebApplicationFactory<Program>`** for ASP.NET Core companion APIs - swap the real DB for in-memory or a Testcontainer in `ConfigureServices`.
- **Testcontainers** (`IAsyncLifetime` to start/stop a real `postgres:16-alpine`) when the in-memory provider hides real SQL behavior. Start in `InitializeAsync`, dispose in `DisposeAsync`.

### Test organization

```
tests/
  MyApp.UnitTests/{Services,Validators}/...
  MyApp.IntegrationTests/{Api,Repositories}/...
  MyApp.TestHelpers/{Builders,Fixtures}/...
```

### Running

```bash
dotnet test                                   # all
dotnet test --collect:"XPlat Code Coverage"   # coverage
dotnet test --filter "FullyQualifiedName~OrderService"
dotnet watch test --project tests/MyApp.UnitTests/
```

---

## Part 4 - anti-pattern review checklist

When reviewing C#/.NET code (the `dotnet-patterns` "reviewing C# code" mode), flag these:

| Anti-pattern | Fix |
|---|---|
| `async void` (non-event-handler) | return `Task` |
| `.Result` / `.Wait()` on async | `await` (deadlock + thread-starvation risk) |
| Swallowing `CancellationToken` | accept it, thread it, honor it |
| `catch (Exception) { }` empty | handle, or rethrow with context |
| `new Service()` inside a constructor | constructor injection |
| `public` mutable fields | properties with proper accessors |
| Mutable `static` state | DI scoping / `ConcurrentDictionary` |
| `dynamic` in business logic | generics or explicit types |
| `string.Format` in a loop / hot path | `StringBuilder` / interpolated handlers (and in a game loop, avoid per-frame allocation entirely) |
| `!` null-forgiving used to mute a warning | prove non-null, or model the null honestly |
| Exposing `List<T>` on a public API | `IReadOnlyList<T>` |
| Throwing for expected/recoverable failure | `Result<T>` |

### Test anti-patterns

| Anti-pattern | Fix |
|---|---|
| Testing implementation details | test behavior and outcomes |
| Shared mutable test state | fresh instance per test (xUnit constructor) |
| `Thread.Sleep` in async tests | `Task.Delay` + timeout, or polling helper |
| Asserting on `ToString()` | assert on typed properties |
| One giant multi-concern assertion | one logical assertion per test |
| Test name describing implementation | name by behavior |

---

## One-line takeaway

**Nullable on and honored, immutable by default, abstractions at boundaries, async all the way with a threaded `CancellationToken`, `Result<T>` for expected failure - then test the behavior (not the implementation) with xUnit/FluentAssertions/fakes for plain C#, and UTF EditMode/PlayMode for engine code. Extract pure gameplay logic out of `MonoBehaviour`s so it can be tested with the faster stack.**
