# Game Design Mentor (Unreal)

Load when the task involves a new level, feature, mechanic, or the question "how should this work?" This is the highest-leverage reference in the stack - it protects Shai from his coder instincts. It is the engine-neutral design spine, mirrored from unity-developer's `game-design-mentor.md` so both engine employees enforce the same discipline. **For the deep design brain - full MDA theory, Self-Determination Theory, Flow, Bartle types, narrative authoring (ink), economy balance, and the prompt-to-playable eval loop - defer to the `game-designer` employee.** This file is the in-engine execution gate, not a duplicate of that theory.

## The core mental model: MDA
1. **Mechanics** - the rules. The C++ logic, Blueprint graphs, physics, state transitions. What coders see.
2. **Dynamics** - what emerges when a player interacts with the mechanics. Emergent, not authored line-by-line.
3. **Aesthetics** - how it feels: tension, mastery, delight, surprise. Players remember this, not your mechanics.

**Rule of thumb: start from aesthetics, design backwards to mechanics.** Ask "what should the player FEEL here?" before "what should the code DO?" If Shai can't name the feeling, the level isn't designed - it's just wired.

## The player loop - the single most important question
Every level, mechanic, and button must answer:
> **What does the player do, what feedback do they get, what do they do next, and why do they care?**

If any part is missing, it's broken. In UE the feedback layer is concrete: hit reactions, Niagara VFX, camera shake (`manage_effect` + `manage_character`), MetaSound/audio cues (`manage_audio`), UMG juice (`manage_widget_authoring`). Silence is death - every interaction needs immediate, unambiguous feedback (visual + audio). A simple scale-pulse + a tone beats nothing while art is pending.

## Design Review Protocol - the four questions (MANDATORY before any C++/Blueprint)
1. **Who is in this moment, and in what mood?** First-time (hand-hold, clear hierarchy) / returning mid-session (speed, no tutorials) / post-loss (fast retry, no "you lost!" wall) / post-win (show reward, tee up next) / stuck (visible way forward) / sandbox (more options tolerated).
2. **What is their single next action?** Name it in five words or the moment is unclear.
3. **Where did they come from and where do they go next?** This defines its place in the Gameplay-Framework state machine (GameMode/GameState/PlayerController flow - see `unreal-scene-architecture.md`). "I don't know yet" → map the flow first.
4. **What happens if they do nothing for 10 seconds?** Idle state, tooltip, auto-advance, or nothing - decide deliberately. Games that forget this feel broken.

Code written before clean answers gets thrown away. If Shai can't answer, your job is to help him work through them - not to open the editor.

## Game feel checklist (UE specifics)
- **Input latency** target <100ms perceived - Enhanced Input mapped tightly (`manage_input`).
- **Animation responsiveness** - anim notifies + montages that cancel cleanly; Control Rig for procedural reactions (`animation_physics`).
- **Feedback stack per action** - Niagara + camera shake + MetaSound, layered.
- **Camera dynamics** - spring arm tuning, FOV punches on impact.

## Pillars first
Before a new game (or major mode): define 3-5 pillars - the core experiences this game delivers. "Fun" is not a pillar; "frantic moment-to-moment combat" is. Record them in `CLAUDE.md`. Every feature decision checks against the pillars.

## What lives here vs. in game-designer
- **Here (unreal-developer):** the gate that stops Claude from building before the four questions are answered, plus how feedback/feel is wired in UE.
- **In game-designer:** the full theory (MDA depth, SDT, Flow, Bartle), GDD authoring, narrative (ink), economy/balance (Machinations), and the OpenGame prompt-to-playable + eval methodology. Pull that employee in for design-heavy work; don't reinvent it here.
