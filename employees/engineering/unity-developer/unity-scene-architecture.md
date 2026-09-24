# Unity Scene Architecture

Load this file for anything involving: scene structure, screen transitions, state machines, UIManager, SceneManager, Manager singletons, ScriptableObjects, or the "how do my screens connect" problem.

This is the reference that fixes "slapping things on without context that they should come at a different screen." The root cause of that problem is always the same: **no state machine exists, so every screen floats free.** The fix is to make the state machine explicit and central.

## The three-layer architecture every Unity game should use

Before adding any new screen, confirm these three layers exist. If they don't, build them first.

### Layer 1 - GameStateManager (the brain)

A singleton MonoBehaviour or ScriptableObject that owns the current global state of the game. One source of truth.

States are an enum - finite and explicit:
```csharp
public enum GameState {
    Boot,
    MainMenu,
    Loading,
    Playing,
    Paused,
    Win,
    Lose,
    Shop,
    Settings,
    Credits
}
```

GameStateManager exposes:
- `CurrentState` (readonly)
- `RequestTransition(GameState next)` - validates and fires transition events
- `OnStateChanged` event - everyone else listens, nobody polls

**Why this matters:** if every screen knows how to ask "what state should come next" instead of hard-coding "load MainMenu scene", the flow becomes reconfigurable. Adding a new pre-gameplay screen doesn't require editing five different scripts - you just insert a state.

### Layer 2 - UIManager (the stack)

UI screens (menus, HUDs, popups) live on a **stack**, not a flat list. At any moment, one screen is on top and owns input. Others are paused or hidden below.

```csharp
public class UIManager : MonoBehaviour {
    private Stack<UIScreen> screenStack = new Stack<UIScreen>();
    public void Push(UIScreen screen) { /* show new, pause previous */ }
    public void Pop() { /* close top, resume previous */ }
    public void Replace(UIScreen screen) { /* swap top */ }
}
```

Screen transitions become:
- Open pause menu → `Push(pauseScreen)`
- Close it with Resume → `Pop()`
- Go from Settings back to Main menu → `Pop()`
- Game over → `Replace(gameOverScreen)`

**This single pattern kills 80% of "back button does nothing" bugs.** Because the stack knows where you came from, back is always `Pop()`. No screen needs to remember its parent.

### Layer 3 - Scenes (the world)

Unity scenes are for big context changes - different levels, fundamentally different environments. NOT for every menu.

**Rule of thumb:**
- Different 3D environment / level geometry → new Scene
- Different UI menu / overlay → UIScreen on the stack, same Scene
- Loading between heavy scenes → additive-load a LoadingScene, transition when ready

Common anti-pattern: one scene per menu. This leads to slow transitions, lost state between menus, and a nightmare to debug. Use additive UI on a single menu scene instead.

## The screen flow map - make it a file, not a mental model

At the root of every Unity project, maintain `docs/screen-flow.md` with:
1. List of all game states (from the enum above)
2. List of all UIScreens (stack items)
3. Arrow diagram showing every legal transition

Example for a simple runner:
```
Boot → MainMenu
MainMenu → [Start] → Loading → Playing
Playing → [Pause button] → Paused
Paused → [Resume] → Playing
Paused → [Main menu] → MainMenu
Playing → [Death] → Lose
Lose → [Retry] → Loading → Playing
Lose → [Home] → MainMenu
Playing → [Win condition] → Win
Win → [Continue] → Loading → Playing (next level)
Win → [Home] → MainMenu
```

**If a screen isn't on the map, it doesn't exist yet.** New screens get added to the map BEFORE any GameObject is created. This is the single most important discipline.

## Manager singletons - when and how

### Use singletons for TRULY global systems

Legit singleton candidates:
- GameStateManager
- UIManager
- AudioManager
- SaveManager
- AnalyticsManager (if present)
- InputManager (for complex input remapping)

Singleton pattern (standard Unity flavor):
```csharp
public class GameStateManager : MonoBehaviour {
    public static GameStateManager Instance { get; private set; }
    private void Awake() {
        if (Instance != null && Instance != this) {
            Destroy(gameObject);
            return;
        }
        Instance = this;
        DontDestroyOnLoad(gameObject);
    }
}
```

### Do NOT make singletons of

- Player (use tagged GameObject + cached reference)
- Camera (use `Camera.main` or Cinemachine)
- Enemies, items, pickups (these are scene-scoped)
- Any "manager" that only exists in one scene

## ScriptableObjects - the underused weapon

ScriptableObjects are Unity's answer to "game data that lives in the project, not in a scene." They are criminally underused by coders who default to hardcoding values.

**Use a ScriptableObject when:**
- Game balance values (enemy HP, weapon damage, level speeds) - edit in Inspector without recompile
- Event channels (decoupled messaging between systems)
- Level configs (spawn tables, layouts)
- Character stats
- Item databases

**Event Channel pattern - kills tight coupling:**
```csharp
[CreateAssetMenu(menuName="Events/GameEvent")]
public class GameEventChannelSO : ScriptableObject {
    public event Action OnEventRaised;
    public void Raise() => OnEventRaised?.Invoke();
}
```
Now any system can listen to `onPlayerDied.OnEventRaised` without knowing who raises it. UI reacts, audio reacts, analytics react - all independent.

## Scene transitions - the right way

### Fast, light transitions (same scene, different UI)
Use UIManager.Push/Pop. Zero load time.

### Heavy transitions (new level, new environment)
1. **Push a LoadingScreen** onto the UI stack immediately (no loading indicator = player thinks game froze)
2. Call `SceneManager.LoadSceneAsync(nextScene, LoadSceneMode.Single)` - get the `AsyncOperation`
3. Poll `op.progress` to update a progress bar (note: Unity caps progress at 0.9 until the scene activates)
4. When progress ≥ 0.9, allow activation (`op.allowSceneActivation = true`)
5. Pop the LoadingScreen once the new scene signals ready

### The "loading is instant but feels slow" problem
If the real load is <100ms, ADD a minimum loading screen time (~500ms with a small animation). Instant transitions feel jarring and confuse players.

## Input - the abstraction layer that saves weeks

**Anti-pattern:** scripts directly call `Input.GetKeyDown(KeyCode.Space)` or check raw touches. This is what gets refactored 6 months in when you add controller support, remap, or go mobile.

**Correct pattern:** Unity's new Input System (Package Manager → Input System). Define actions ("Jump", "Attack", "Pause") in an InputActionAsset, then subscribe to them. Switching from keyboard to gamepad to touch becomes a binding change, not a rewrite.

If the project uses the OLD Input Manager, create a thin wrapper class (`GameInput.Jump`) so scripts never call `Input.GetKey` directly. Migration becomes swap-one-class instead of refactor-everything.

## Prefabs - scenes are for instances, prefabs are for types

Rule: if a GameObject exists more than once, or is likely to, make it a prefab.

**Nested prefabs** (Unity 2018.3+) are essential. A boss enemy is a prefab. Its weapon is a nested prefab. Edit the weapon prefab → all bosses update. Don't fight this; embrace it.

**Prefab variants** for minor alterations - "Red goblin" as a variant of "Goblin", shared behavior, different tint/stats.

## Gameplay design patterns - the toolkit beyond singletons

The singleton + ScriptableObject-event-channel patterns above cover global state and decoupled messaging. For everything else, reach for the right named pattern rather than reinventing it. (Study reference: Unity's free e-book "Level up your code with game programming patterns" and its companion demo repo - patterns summarized here from general knowledge; do not copy the demo code, the repo carries no license.)

- **Observer** - decouple "something happened" from "who reacts." The ScriptableObject event channel above is one flavor; plain C# `event Action` is the lightweight in-code flavor. Use when many systems must react to one event (player died -> UI, audio, analytics, achievements) without the raiser knowing the listeners.
- **State** - model a thing that behaves differently per mode as explicit state objects with `Enter()/Tick()/Exit()`, not a pile of bool flags. Use for: the GameStateManager itself, enemy AI (Patrol/Chase/Attack/Flee), the player (Grounded/Jumping/Dashing). Kills the "if (isJumping && !isDashing && wasGrounded)" tangle.
- **Command** - wrap an action as an object so you can queue, log, replay, or undo it. Use for: undo/redo, input buffering and replays, turn-based move queues, tutorial recording.
- **Object Pool** - reuse instead of Instantiate/Destroy (see `unity-performance-mobile.md` for the perf rationale). Use for bullets, enemies, particles, damage numbers, recycled UI cells. Unity ships `UnityEngine.Pool.ObjectPool<T>`.
- **Factory** - centralize "create the right object from a key/config" so spawn logic is not duplicated. Use for enemy/item spawners driven by ScriptableObject spawn tables.
- **MVC / MVP** - separate UI rendering (View) from data (Model) via a Controller/Presenter so screens are testable and data changes do not require touching layout. Pairs well with the UIManager stack above.

**Rule of thumb:** if you find yourself adding a fourth bool flag to a class, you want the State pattern. If you are copy-pasting "create object X" logic in three places, you want a Factory. If a class reaches into five other systems to tell them something changed, you want Observer. Pick the pattern that removes the coupling, not the one that looks clever.

## Common architecture mistakes and their fixes

| Mistake | Symptom | Fix |
|---------|---------|-----|
| Flat scene list, no state machine | Back button goes to wrong place; adding screen breaks three others | Introduce GameStateManager, put every screen on a state |
| One scene per menu | Slow transitions, lost state | Additive UI on one menu scene |
| Everything in the Player script | Player.cs is 2000 lines and fragile | Extract: Movement, Health, Inventory, Animation into separate components |
| Hardcoded game balance | Every balance change is a code change | ScriptableObjects with Inspector-tweakable values |
| GameObject.Find() everywhere | Slow, fragile, breaks on renames | Cache references in Awake; use tags or SerializeField |
| Public static fields for "global" data | Impossible to debug; state leaks across sessions | Singleton with explicit API, or ScriptableObject |
| Empty Update() methods on 200 GameObjects | Measurable frame drop | Delete them; Unity still calls empty Update methods |
| Direct scene-to-scene coupling | Scene A references GameObjects in Scene B | Event channels (ScriptableObject) or DontDestroyOnLoad managers |

## The architecture audit - run this on any inherited Unity project

Before writing a single line of code in an unfamiliar project, answer:

1. Is there a GameStateManager? (If no → all screens are islands, flag risk)
2. Is there a UIManager with a stack? (If no → back-button bugs are guaranteed)
3. Is the screen flow documented? (If no → start `docs/screen-flow.md` before adding features)
4. Are balance values in ScriptableObjects or hardcoded? (Hardcoded → flag technical debt)
5. Is the Input System new or old? (Old → flag for migration if platform expansion planned)
6. How many scenes exist? (If one per menu → flag for consolidation)

If 3+ of these are "no", we're in a rescue job. Fix architecture first, add features second. Load `codebase-onboarding` skill if available.
