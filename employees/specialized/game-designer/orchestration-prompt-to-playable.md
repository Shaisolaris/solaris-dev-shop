# Prompt-to-Playable Orchestration + Eval Loop - OpenGame methodology

> Deepened 2026-06-13 from **leigest519/OpenGame** (2.5k★, Apache-2.0, CUHK MMLab) - the first open-source agentic framework for end-to-end web game creation from a prompt. ABSORB the METHODOLOGY (it's transferable to Unity + Unreal, not just web). This is the orchestration brain that turns "give a command → it designs, creates assets, and executes" from a wish into a repeatable loop.

## The core problem OpenGame names (and why it matters to Solaris)
LLMs solve isolated coding tasks easily but **collapse when asked to produce a fully playable game from a high-level design** - they fail on **cross-file inconsistencies, broken scene wiring, and logical incoherence**. Patching isolated syntax bugs doesn't fix this; you need an agent that **scaffolds stable architecture** and **systematically repairs integration errors**. This is exactly Shai's "took a month to republish 6 games" pain, generalized.

## Game Skill - the two-part reusable capability
OpenGame bootstraps its agent with **Game Skill**, split in two. This is the pattern to run for any Solaris game build, regardless of engine:

### 1. Template Skill - scaffold a stable skeleton FIRST
- Pick an appropriate engine/template and **scaffold a conventional, stable project structure** so later edits stay coherent.
- It **grows a library of project skeletons from experience** - every successful build adds a reusable skeleton.
- **Solaris translation:** before generating gameplay, lay down the clean architecture (Unity: scene/manager/ScriptableObject layout per `unity-scene-architecture`; Unreal: Gameplay Framework + level/Blueprint structure per `unreal-scene-architecture`). Reuse a known-good skeleton rather than improvising structure each time. A coherent skeleton is what prevents the cross-file/scene-wiring collapse.

### 2. Debug Skill - a LIVING protocol of verified fixes
- **Run the game in a sandbox**, catch integration errors / console errors / broken interactions, and **systematically resolve them until the game is playable end-to-end.**
- Maintain a **living protocol of verified fixes** - fixes accumulate as durable knowledge, not one-off patches.
- **Solaris translation:** this IS the engine employees' verify loop - Unity Tier-0 autonomous test loop (`unity-testing-pipeline.md`), Unreal PIE + logs + inspect loop. The "living protocol" maps onto each employee's `learnings.md` (promote a fix after it recurs). Repair the *integration* (scene wiring, state coherence), not isolated syntax.

> Together they move the agent from "writes plausible code" to "ships a working game." That sentence is the whole point of the games cluster.

## OpenGame-Bench - how to know it's actually playable
Verifying interactive playability is **fundamentally harder than checking static code**. OpenGame-Bench scores generated games on **three axes**, via **headless browser execution + VLM (vision-language-model) judging**:
1. **Build Health** - does it build/run without errors? (compile clean, no runtime exceptions, game-loop progresses.)
2. **Visual Usability** - does it render and look usable? (a VLM looks at screenshots and judges.)
3. **Intent Alignment** - does it match what was asked? (the design intent, not just "a game.")

It dynamically **launches the game, drives it with scripted interactions, and verifies playability criteria** (rendering, controls, game-loop progression, win/loss states) - not static code metrics.

**Solaris translation (use these 3 axes as the definition-of-done for any game feature):**
- **Build Health** → engine employee runs the build/test loop green (Unity `tests-run` + clean console; Unreal Automation tests + clean logs).
- **Visual Usability** → take a game-view/PIE **screenshot and actually judge it** (the employee judges the image - does it render, is the HUD readable, is the player visible?). This is why "screenshot it yourself" is a hard rule in both engine employees.
- **Intent Alignment** → check the result against the **pillars + the Design-Review-Protocol answers** (does it deliver the feeling/next-action that was specified?). This closes back to game design, not just engineering.

## The orchestration loop (put it together)
For a "command → playable" request, game-designer orchestrates:
1. **Design** - pillars + MDA + the 4 Design-Review questions → a checkable intent.
2. **Scaffold** (Template Skill) - lay a stable, conventional skeleton via the engine employee.
3. **Generate assets** - the shared asset layer (blender-mcp / Tripo / Meshy / ElevenLabs) for 3D/2D/audio.
4. **Build + wire** - engine employee executes in-engine (CoplayDev for Unity / ChiR24 bridge for Unreal).
5. **Eval (OpenGame-Bench axes)** - Build Health (tests+logs) → Visual Usability (screenshot judged) → Intent Alignment (vs pillars).
6. **Debug Skill loop** - repair integration errors, append verified fixes to `learnings.md`, re-eval until all three axes pass.

## Honest notes
- OpenGame targets **web games** (canvas/Phaser/three.js) and ships a CLI (`opengame -p "..."`); its GameCoder-27B model + the full bench pipeline are research artifacts (eval pipeline "released soon" as of the paper). We absorb the **methodology** (Game Skill = scaffold-then-debug; 3-axis playability eval), not the model or the web-only runtime.
- The transferable insight: **playability is verified by running + looking + checking intent - never by reading code alone.**

## Sources
- leigest519/OpenGame (Apache-2.0) - README abstract (failure modes, Game Skill = Template + Debug, GameCoder-27B, OpenGame-Bench 3-axis headless+VLM eval) + Game Skill / Quick Start / Configuration sections. Methodology distilled and re-targeted to Unity/Unreal; no code copied.
- Reference knowledge base (not absorbed): git-disl/awesome-LLM-game-agent-papers (911★) - survey of LLM game agents.
