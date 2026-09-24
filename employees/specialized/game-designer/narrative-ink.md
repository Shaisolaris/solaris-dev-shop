# Branching Narrative Authoring - ink (inkle)

> Deepened 2026-06-13 from **inkle/ink** (4.8k★, MIT) - the industry-standard scripting language for interactive narrative. ABSORB the authoring methodology; CONNECT the tooling (host installs Inky / ink-unity-integration). Use whenever a game needs branching dialogue, choice-driven story, or text-centric content.

## What ink is (and what it isn't)
ink is inkle's **scripting language for interactive narrative** - branching stories for text-centric games AND graphical games with highly branching dialogue. It is **not** an end-to-end narrative game engine: it's designed to slot into your own game + UI. The core engine is C# (includes the compiler); a JS port (inkjs) powers web.

**The toolchain (know which piece each role needs):**
- **Inky** - the ink editor; a text editor that plays your story as you write. *Writers need only this.* Best starting point.
- **ink-unity-integration** - Unity plugin (includes the full ink engine source); auto-compiles `.ink` on edit. *Unity devs need this.* (NOASSERTION on the package - check before redistribution; fine to use in-project.)
- **inklecate** - the command-line compiler/player (Inky uses it under the hood). `inklecate -p story.ink` to play; drop `-p` to emit compiled `.json`.
- **inkjs** - community JS port for web games (one major version behind core; bundled when you export web from Inky).
- **inklewriter** - an unrelated, simpler tool; can export TO ink but not vice-versa.

## The ink syntax - what makes it the standard
A few primitives compose into deep branching. Teach Shai these, not a wall of grammar:
- **Content** - plain text lines are the story.
- **Choices** - `*` for once-only choices, `+` for repeatable (sticky) choices. Nesting (`* *`, `* * *`) builds choice trees.
- **Gathers** - `-` (and `- -`, `- - -`) collect divergent branches back to a common point, so branches don't have to each re-write the shared continuation.
- **Diverts** - `-> knot_name` jumps to a named section; `-> END` ends the flow.
- **Knots / stitches** - named sections (`== knot ==`, `= stitch`) structure the story into addressable units.
- **Glue** - `<>` joins lines without a line break, for assembling sentences from fragments.
- **Suppression** - `[bracketed]` text shows in the choice but not in the resulting output, so a choice can read differently from what it prints.
Beyond these: **variables + logic** (state, conditions), **weave** (the flat authoring style above), **threads** + **tunnels** (reusable sub-flows), and **functions** for computed text.

## How it runs in a game (the integration contract)
ink compiles to a `.json` story file; your game loads it and pumps it:
```csharp
using Ink.Runtime;
_story = new Story(sourceJsonString);          // 1) load compiled ink
while (_story.canContinue)                       // 2) get content line-by-line
    Display(_story.Continue());
ShowChoices(_story.currentChoices);              // 3) present choices
_story.ChooseChoiceIndex(0);                      // 4) player picks -> back to 2
```
The game owns presentation (UI, voice, pacing); ink owns the branching state. Variables can be read/written across the C#/ink boundary so story state drives gameplay and vice-versa.

## Design discipline for branching narrative
- **Weave first, structure later.** Author the flat weave (choices + gathers) before carving knots; ink is built so branches converge cheaply via gathers - don't hand-wire every recombination.
- **Choices are dynamics, not just text.** Apply MDA: a choice's *aesthetic* (agency, dread, humor) matters more than its branch count. Two meaningful choices beat eight cosmetic ones (and serve SDT autonomy).
- **Keep narrative state in ink, gameplay state in the engine** - but let them read each other through ink variables. Don't fork the story into engine `if`-spaghetti.
- **Validate with playthroughs in Inky** before integrating - the same "playtest > theory" rule applies to narrative.

## Connect / install (host-side)
- Writer: install **Inky** (github.com/inkle/inky).
- Unity: add **ink-unity-integration** (Unity AssetStore or git package) - auto-compiles `.ink`, gives an in-inspector play button.
- Web: export web from Inky (bundles inkjs).
- CLI/CI: build **inklecate** (`dotnet build -c Release` in the ink repo) to compile `.ink → .json` headlessly.

## Sources
- inkle/ink (MIT) - README (toolchain roles, syntax taster, runtime integration contract, versioning). ink-unity-integration carries NOASSERTION - usable in-project, verify before redistribution. Methodology distilled, not copied.
