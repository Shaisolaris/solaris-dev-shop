# AGENTS.md - Project Memory for [GAME NAME]

This file lives at the root of the Unity project. It's read by the coding agent at the start of every session so no question gets asked twice. Fill in what you know; leave blanks for what you don't - the coding agent will help close them.

Last updated: [DATE]

---

## 1. Game concept (one paragraph)

> Example: *"TrafficRush is a casual mobile game where players guide cars through intersections by tapping at the right moment. One tap = release one car. Miss and cars crash; the level ends. Rewards come from level stars and daily challenges. Target audience is casual players 25-45 who play in 3-5 minute sessions."*

**Write your version here:**

[fill in]

---

## 2. Target platform and technical constraints

- **Primary platform:** [iOS / Android / PC / WebGL / Console / Multiple]
- **Minimum device:** [e.g. "iPhone 8 / Android 8.0 / 2GB RAM"]
- **Orientation:** [Portrait / Landscape / Both]
- **Target framerate:** [30 / 60 / 120]
- **Max install size target:** [e.g. "150MB for mobile"]
- **Internet requirement:** [Always online / Online for X only / Fully offline]
- **Unity version:** [e.g. "2022.3 LTS" - check `ProjectSettings/ProjectVersion.txt`]
- **Render pipeline:** [Built-in / URP / HDRP]
- **Input system:** [New Input System / Old Input Manager / Both]

---

## 3. The player loop (one screen at a time)

> Example: *"Player opens app → sees Main Menu → taps Play → Loading → Level X → taps to release cars → wins or loses → win screen or lose screen → back to Main Menu or next level."*

**Write your version here:**

[fill in]

---

## 4. Screen flow map

Every screen in the game, and the legal transitions between them. Update this WHENEVER a new screen is added. This is the single most important section - it prevents "slapping on" new screens without thinking about where they fit.

```
[Boot]
  ↓
[Main Menu]
  ↓ (tap Play)
[Loading] → [Gameplay]
                ↓ (pause button)
              [Paused] ↔ [Settings]
                ↓ (quit)
              [Main Menu]
                ↓ (win)
              [Win Screen] → (tap continue) → [Loading] → next level
                ↓ (lose)
              [Lose Screen] → (retry) → [Loading] → same level
                             → (home) → [Main Menu]
```

Replace with your actual flow. Any screen not on this map doesn't exist yet.

---

## 5. Tech stack decisions (finalized)

| Decision | Choice | Reason |
|----------|--------|--------|
| Save system | [PlayerPrefs / JSON file / SQLite / cloud] | [why] |
| Audio | [Unity Audio / FMOD / Wwise] | [why] |
| Analytics | [none / Unity Analytics / GameAnalytics / custom] | [why] |
| Monetization | [none / IAP / ads / both / subscription] | [why] |
| Ads provider | [none / AdMob / UnityAds / IronSource] | [why] |
| IAP provider | [none / Unity IAP / RevenueCat] | [why] |
| Multiplayer | [none / Netcode for GameObjects / Mirror / Photon] | [why] |
| UI framework | [UGUI / UI Toolkit] | [why] |
| Tween library | [DOTween / LeanTween / none] | [why] |

---

## 6. Architecture status - what's in place vs. what's missing

Check the boxes that are actually done. Empty ones are known technical debt.

- [ ] `GameStateManager` singleton exists with enum-based states
- [ ] `UIManager` with screen stack (push/pop) exists
- [ ] `AudioManager` singleton exists
- [ ] `SaveManager` singleton exists with save/load API
- [ ] Screen flow is documented (section 4 above)
- [ ] Game balance values live in ScriptableObjects (not hardcoded)
- [ ] Event channel pattern used for cross-system messaging
- [ ] New Input System used (or wrapper around old Input Manager)
- [ ] Scenes are loaded additively where appropriate (not one per menu)
- [ ] Prefabs used for any repeated GameObject type
- [ ] No `GameObject.Find()` calls in Update() loops
- [ ] Debug HUD exists (toggleable on-screen dev panel)

---

## 7. Testing setup

- **Editor Play Mode ready:** [yes / partial / no]
- **Device Simulator configured:** [yes / no] - if no, install from Package Manager
- **Unity Remote 5 set up:** [yes / no] - if yes, which device(s)?
- **AltTester installed:** [yes / no]
- **Automated test flows:** [list them - e.g. "happy path, lose-retry, pause-resume"]
- **Screenshot baseline exists:** [yes / no]
- **CI builds on commit:** [yes / no]

---

## 8. Art and audio assets

- **Art style:** [e.g. "flat 2D, low-poly 3D, pixel art, hand-drawn"]
- **Color palette:** [hex values or reference]
- **Font:** [name and source]
- **Icon style:** [reference]
- **Music direction:** [genre, mood, reference tracks]
- **SFX philosophy:** [e.g. "chunky, satisfying, UI tones under 100ms"]
- **Assets source:** [self-made / Asset Store / commissioned / placeholder]

---

## 9. Monetization and economy (if applicable)

- **Primary currency:** [coins / gems / energy / N/A]
- **Secondary currency:** [if any]
- **Earn rates:** [e.g. "10 coins per level, 1 gem per 5 levels"]
- **Sink rates:** [what costs what]
- **Retention hooks:** [daily login, streaks, timed events]

---

## 10. Standing answers to "don't ask me this again"

Running list. Every time the owner finds themselves explaining something the coding agent should have remembered, add it here.

- **[Date]** - [Question the coding agent re-asked]: [The answer, written as a standing rule]

Examples to kickstart:
- **2026-04-23** - "What's the target framerate?" → 60 on capable devices, 30 on low-end. Locked.
- **2026-04-23** - "Should I use the new or old Input System?" → New. Migration of any old input code is welcome.

---

## 11. Current active work

What's being built right now. Update weekly or whenever focus shifts.

- **Current milestone:** [e.g. "L3 build" / "soft launch prep"]
- **Blocking decisions:** [what the owner needs to answer before progress continues]
- **Known bugs in current build:** [list, linked to tracker if exists]

---

## 12. Links and references

- GitHub repo: [url]
- Design doc (if separate): [url or path]
- Art reference board: [url]
- Public beta / TestFlight / Play Store internal track: [url]
- Project tracker (ClickUp / Trello / etc.): [url]
