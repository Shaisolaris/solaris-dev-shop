# Android Architecture Reference - NowInAndroid Patterns

> **Absorbed v0.3.0 (2026-04-25)** from `dpconde/the coding agent-android-skill` - Google's official Android architecture guidance + NowInAndroid reference app patterns. The skill scanner v2 caught this. Use this for any Kotlin/Jetpack Compose work.

## Core principles (non-negotiable)

1. **Offline-first** - Local DB (Room) is source of truth. Network sync is secondary. Never make UI directly depend on network state.
2. **Unidirectional data flow (UDF)** - Events flow DOWN (UI → ViewModel → Repository → DataSource). Data flows UP (DataSource → Repository → ViewModel → UI as immutable state).
3. **Reactive streams** - Expose data as `Flow<T>` everywhere. Never callbacks. Never RxJava in new code.
4. **Modular by feature** - Each feature is a self-contained module pair (`feature/X/api` + `feature/X/impl`). Never let features depend on each other directly - use the `api` module as a contract.
5. **Testable by design** - Use interfaces and test doubles. AVOID Mockito/MockK for new code where a fake works.

## The 3 layers

```
┌─────────────────────────────────────┐
│ UI Layer                            │
│  Compose Screens + ViewModels       │
│  StateFlow<UiState>                 │
├─────────────────────────────────────┤
│ Domain Layer (optional)             │
│  Use Cases - only when reused       │
│  across multiple ViewModels         │
├─────────────────────────────────────┤
│ Data Layer                          │
│  Repositories (interface)           │
│  DataSources (Room + Retrofit)      │
└─────────────────────────────────────┘
```

## Module structure (canonical)

```
app/                       # Android Application module
feature/
  ├── settings/
  │   ├── api/             # Public navigation contracts only - NavHost destinations, route definitions
  │   └── impl/            # Internal: Screen, ViewModel, UiState, internal composables
  ├── login/
  │   ├── api/
  │   └── impl/
  └── ...
core/
  ├── data/                # Repository implementations
  ├── database/            # Room DAOs + entities
  ├── network/             # Retrofit interfaces + DTOs (Kotlinx Serialization)
  ├── model/               # Pure domain models - NO Android dependencies
  ├── ui/                  # Reusable composables (buttons, cards, list items)
  ├── designsystem/        # Theme, typography, color tokens, spacing
  └── testing/             # Test fakes, fixtures, fake repositories
build-logic/
  └── convention/          # Gradle convention plugins - DRY for build setup
```

## Canonical patterns

### ViewModel

```kotlin
@HiltViewModel
class SettingsViewModel @Inject constructor(
    private val repository: SettingsRepository,
) : ViewModel() {
    val uiState: StateFlow<SettingsUiState> = repository
        .getSettings()
        .map<Settings, SettingsUiState> { SettingsUiState.Success(it) }
        .catch { emit(SettingsUiState.Error(it.message ?: "Unknown")) }
        .stateIn(
            scope = viewModelScope,
            started = SharingStarted.WhileSubscribed(5_000),  // 5s grace for config changes
            initialValue = SettingsUiState.Loading,
        )

    fun onToggleDarkMode(enabled: Boolean) = viewModelScope.launch {
        repository.setDarkMode(enabled)
    }
}

sealed interface SettingsUiState {
    data object Loading : SettingsUiState
    data class Success(val settings: Settings) : SettingsUiState
    data class Error(val message: String) : SettingsUiState
}
```

### Screen + Route separation

```kotlin
// Public - wired into NavHost
@Composable
internal fun SettingsRoute(
    onBack: () -> Unit,
    viewModel: SettingsViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    SettingsScreen(
        uiState = uiState,
        onToggleDarkMode = viewModel::onToggleDarkMode,
        onBack = onBack,
    )
}

// Stateless - testable in isolation
@Composable
internal fun SettingsScreen(
    uiState: SettingsUiState,
    onToggleDarkMode: (Boolean) -> Unit,
    onBack: () -> Unit,
) {
    when (uiState) {
        SettingsUiState.Loading -> LoadingIndicator()
        is SettingsUiState.Error -> ErrorView(uiState.message)
        is SettingsUiState.Success -> SettingsContent(uiState.settings, onToggleDarkMode, onBack)
    }
}
```

### Repository (offline-first)

```kotlin
interface SettingsRepository {
    fun getSettings(): Flow<Settings>
    suspend fun setDarkMode(enabled: Boolean)
}

internal class OfflineFirstSettingsRepository @Inject constructor(
    private val dao: SettingsDao,                  // Room - source of truth
    private val api: SettingsNetworkApi,           // Retrofit - secondary
    @Dispatcher(IO) private val ioDispatcher: CoroutineDispatcher,
) : SettingsRepository {
    override fun getSettings(): Flow<Settings> = dao.getSettings()
        .map { it.toModel() }                      // Entity → domain model
        .flowOn(ioDispatcher)

    override suspend fun setDarkMode(enabled: Boolean) {
        dao.updateDarkMode(enabled)                // Local first
        try {
            api.updateDarkMode(enabled)            // Sync to network
        } catch (e: Exception) {
            // Mark for retry - local change still persisted
        }
    }
}
```

### Hilt module

```kotlin
@Module
@InstallIn(SingletonComponent::class)
internal abstract class SettingsModule {
    @Binds
    abstract fun bindSettingsRepository(impl: OfflineFirstSettingsRepository): SettingsRepository
}
```

## Tech stack (default for new projects)

| Concern | Choice | Why |
|---------|--------|-----|
| Language | Kotlin | Default |
| UI | Jetpack Compose | NEVER XML for new code |
| Architecture | MVVM + UDF | Google guidance + NowInAndroid |
| DI | Hilt | Standard |
| Database | Room | Source of truth |
| Network | Retrofit + Kotlinx Serialization | Type-safe |
| Async | Coroutines + Flow | NEVER RxJava in new code |
| Testing | JUnit + Turbine + Compose Testing | Turbine for Flow assertions |
| Build | Gradle KTS + Convention Plugins | DRY across modules |
| Navigation | Navigation Compose + Navigation3 (Drjacky pattern) | Type-safe routes |

## Build setup essentials

- **Version catalog** (`gradle/libs.versions.toml`) - single source for all dep versions
- **Convention plugins** (`build-logic/convention/`) - extract repeated Gradle config into reusable plugins (`androidLibrary`, `androidApplication`, `androidFeature`, `androidHilt`, etc.)
- **No direct deps in module `build.gradle.kts`** - apply convention plugins, declare only feature-specific deps

Example convention plugin usage in a feature module:

```kotlin
plugins {
    alias(libs.plugins.solaris.android.feature)
    alias(libs.plugins.solaris.android.library.compose)
    alias(libs.plugins.solaris.android.hilt)
}

dependencies {
    implementation(projects.core.data)
    implementation(projects.core.designsystem)
}
```

## Testing strategy

- **Unit tests** - ViewModels, Repositories, Mappers. Use fakes from `core/testing/`.
- **Compose UI tests** - Stateless screens (`@Composable internal fun XScreen(...)`). Test-driven by passing `uiState` directly.
- **Integration tests** - Full feature module with Hilt test rule + fake DataSources.
- **Avoid Mockito/MockK** - Use `class FakeSettingsRepository : SettingsRepository` instead.

## Source provenance

- Repo: https://github.com/dpconde/the coding agent-android-skill
- Reference app: https://github.com/android/nowinandroid (Google official)
- Android arch guide: https://developer.android.com/topic/architecture
- Compose guide: https://developer.android.com/jetpack/compose
- Caught by: the skill scanner v2 (after v1 missed it - see `references/deep-discovery-protocol.md`)

## Cross-references

- For real-device interaction (install / launch / interact / screenshot) → load `mobile-mcp-operator.md`
- For ASO + store strategy → escalate to seo-aso-specialist employee
- For UI design handoff → cross-reference ui-ux-designer employee
