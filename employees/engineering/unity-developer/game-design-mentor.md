# Game Design Mentor

Load this file when the task involves a new screen, new feature, new mechanic, or the question "how should this work?" This is the highest-leverage reference in the stack - it's what protects the owner from their coder instincts.

## The core mental model: MDA

Every game can be decomposed into three layers. Coders default to thinking only about the first. Designers think about all three.

1. **Mechanics** - the rules. The C# logic, the physics, the state transitions. This is what coders see.
2. **Dynamics** - what emerges when a player interacts with the mechanics. "When I shoot, the enemy dodges, so I have to lead my shot" is dynamics, not mechanics. Dynamics emerge.
3. **Aesthetics** - how it feels. Tension, mastery, delight, frustration, surprise. Players remember this; they don't remember your mechanics.

**Rule of thumb: start from aesthetics, design backwards to mechanics.** Ask "what should the player FEEL here?" before asking "what should the code DO?" A tutorial screen should feel reassuring. A boss fight should feel tense. A menu screen should feel inviting. If the owner can't name the feeling, the screen isn't designed - it's just wired.

## The player loop - the single most important question in game design

Every single screen, every single mechanic, every single button must answer:

> **What does the player do, what feedback do they get, what do they do next, and why do they care?**

This is the core game loop. If any part is missing, the screen is broken. Examples:

- **Good loop (a combat screen):** Player attacks → enemy reacts with juice (hit flash, sound, screen shake) → player sees HP drop → player feels progress → player attacks again, more confidently. Loop closes.
- **Broken loop (the owner's failure mode):** Player taps a button → something happens → screen just sits there → player doesn't know if it worked → player taps again out of confusion. No feedback = no loop = no game.

**The fix:** Every interaction needs immediate, unambiguous feedback. Visual (flash, scale, color), audio (click, whoosh), or both. If you can't afford polish art yet, a simple scale-pulse + a tone is enough. Silence is death.

## Design Review Protocol - the four questions, expanded

These are the four questions the master skill gates every new screen on. Here's how to actually run them.

### Q1: Who is on this screen, and in what mood?

Player states to consider:
- **First-time player** - no context, no muscle memory, will miss things. Needs hand-holding, clear hierarchy, no assumed knowledge.
- **Returning player mid-session** - knows the UI, wants speed. Hates tutorials. Wants shortcuts.
- **Post-loss** - frustrated. Wants either fast retry or gentle reassurance, NOT a "you lost!" wall.
- **Post-win** - satisfied. Wants the reward shown clearly and the next challenge teed up.
- **Stuck / confused** - looking for help. Needs a visible way out or forward.
- **Browsing / sandbox** - relaxed. Tolerates more options.

If the owner can't place the player in one of these, the screen's audience isn't defined. Ask them.

### Q2: What is their single next action?

Every screen has ONE primary action. Not two. Not three. One. If you have two, the screen fights itself and the player dithers.

- Title screen → primary action is "start". Everything else (settings, credits) is secondary and visually de-emphasized.
- Loss screen → primary action is "retry". Not "go to main menu".
- Shop screen → primary action is "buy this". Browsing is the flow, buying is the outcome.

Name the single primary action in five words. If it takes more than five words, it's unclear.

### Q3: Where did they come from and where do they go next?

This is the screen's place in the state machine. No screen is an island. If the owner doesn't know where this screen sits in the flow, stop - we fix the screen flow map before touching Unity.

Format:
```
[Previous screen(s)] → [This screen] → [Next screen(s)]
```

Example for a pause menu:
```
[Gameplay] → [Pause] → [Gameplay, Settings, Main menu]
```

Every arrow is a state transition that needs a trigger defined (button, timer, event). Load `unity-scene-architecture.md` for how to actually wire these up.

### Q4: What happens if they do nothing for 10 seconds?

This catches the idle state problem. Games that forget this feel broken.

Options:
- **Tooltip appears** - for screens where the player might be confused. "Tap to start" after 3s idle on title screen.
- **Auto-advance** - for cutscenes, transitions, win/loss screens. Don't force the player to tap through reward screens.
- **Nothing (deliberate)** - for sandbox/menu screens where idle is the expected state. But VERIFY it's deliberate, not forgotten.
- **Subtle animation** - characters breathe, UI pulses. Signals the game is alive, not frozen.

## Screen types and what they need

### Title / Main menu
- Feel: inviting, confident, on-brand
- Primary action: Start / Continue (one, based on save state)
- Secondary: Settings, Credits, Quit
- Idle: tooltip after 3s, or character animation
- Common mistake: equal-weight buttons making the primary action unclear

### Gameplay
- Feel: flow-state focused
- HUD should be glanceable, not readable - player eyes stay on the action
- Every important state change gets feedback (damage, score, powerup)
- Common mistake: HUD has too much info, distracting from the action

### Pause / in-game menu
- Feel: quick, safe, reversible
- Primary action: Resume
- Must be dismissible with one tap/button (including back gesture on mobile)
- Common mistake: pause menu feels like a "main menu" - too heavy, too many options

### Win / reward screen
- Feel: satisfying, celebratory
- Show what was earned clearly - coins, XP, unlocks
- Auto-advance OR one-tap forward
- Common mistake: requiring multiple taps to dismiss - player is already done

### Loss / fail screen
- Feel: quick recovery, not punishment
- Primary action: Retry (fast path)
- Show ONE reason the player lost if it's teaching moment
- Common mistake: big "YOU LOST" wall that feels punishing

### Shop / progression
- Feel: tempting, understandable
- Currency balance visible at all times
- Items grouped by utility, not alphabetically
- Common mistake: confusing pricing or too many categories

### Tutorial
- Feel: guided, competent-making
- Show, don't tell. Forced interaction > text explanation.
- One concept per step. No lecture screens.
- Skippable if the player asks
- Common mistake: walls of text the player skips without reading

## Game feel - the 80/20 rule

If time is limited, invest in "game feel" before new features. Game feel is what separates a prototype from a game.

**The cheap wins:**
- **Hit pause** - freeze gameplay for 50-100ms on big hits. Costs nothing, feels enormous.
- **Screen shake** - 200-400ms subtle shake on impacts. Use `Camera.main.transform` offset or Cinemachine Impulse.
- **Squash and stretch** - UI elements scale up on press (to 1.1x) and settle. Use DOTween or a simple `Mathf.SmoothDamp`.
- **Particle burst** - 10-20 particles on destroy/collect. Pre-made Unity Particle System preset works fine.
- **Audio is 50% of feel** - even a single `.wav` per interaction makes a prototype feel professional.

**The skip-for-now list:**
- Fancy shaders, unless central to the game's identity
- Complex animation trees, unless combat-focused
- Detailed sound design, unless rhythm/audio game
- Lighting polish, unless mood is central

## Design review checklist - run before any new feature

Copy this into chat at the start of a new feature request:

```
DESIGN REVIEW - [feature name]
□ Player state / mood defined
□ Single primary action named (5 words max)
□ Previous → this → next screens mapped
□ Idle state defined
□ Feedback loop: input → feedback → consequence → next input
□ What should the player FEEL?
□ Game feel minimums: scale-pulse on press, audio on interaction, idle life
□ Does it exist in the state machine yet?  [if no → define before coding]
```

If any line is blank, we don't code. We design until it's filled.
