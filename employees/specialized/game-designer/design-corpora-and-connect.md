# Design Corpora (CC0 reference) + Connect tools + Shared asset layer

> Deepened 2026-06-13. Public-domain reference corpora to mine on demand, plus the commercial/SaaS tools the host CONNECTS (never absorb), plus the shared asset layer common to game-designer + unity-developer + unreal-developer.

## CC0 / public-domain design corpora (ABSORB as reference - mine, don't copy wholesale)
These are curated link-lists released CC0 (public domain). Use them as a launch pad when a design question needs deeper theory; follow the leaves, not just the branch.
- **dawdle-deer/awesome-learn-gamedev** (3.4k★, CC0) - broad gamedev learning corpus: design theory, GDD tooling, math, engines, art/audio pipelines. Entry point for "I need to learn/teach X area of gamedev."
- **Roobyx/awesome-game-design** (588★, CC0) - design-specific corpus: MDA references, GDD templates, **Machinations** (economy/systems modeling), level-design and systems-design reading.
- **How to use them:** when a design task exceeds what `design-frameworks.md` + SKILL.md cover (e.g. a specific genre's level-design conventions, a balancing technique), pull the relevant leaf from these corpora and verify the source live before relying on it. They are pointers, not vetted Solaris content.

## CONNECT - commercial / SaaS (reference, do NOT absorb)
- **Machinations.io** - the de-facto game-economy / balance **simulation** tool (node-based: sources, drains, converters, feedback loops). Use it to model and stress-test economies + progression before building. Commercial SaaS → CONNECT only; host wires it. Reference its modeling vocabulary (covered in the CC0 corpora), don't fork it.

## SHARED ASSET LAYER (common to game-designer + unity-developer + unreal-developer)
The "create the assets" layer is a single backbone shared across all three game employees - wired ONCE by the host, used by all. Do NOT re-absorb per-employee.
- **ahujasid/blender-mcp** (~22k★, MIT) - the in-house 3D core / hub: modeling, scene assembly, rendering; other gen tools plug into it. Where ownership of the 3D pipeline lives.
- **elevenlabs/elevenlabs-mcp** (MIT, free tier) - SFX + music + voice.
- **VAST-AI-Research/tripo-mcp** (MIT, official) + **meshy-dev/meshy-mcp-server** (MIT, official) - text/image → 3D with PBR; import to Blender or directly into the engine.
- **Commercial gen (CONNECT, never absorb):** Meshy, Tripo, Rodin (3D + auto-rig), Scenario.com (style-trained 2D sprites + PBR), Layer.ai (textures), Suno/Udio (music).
- **OSS gaps as of 2026-06 (commercial-only):** rigging/animation gen, 2D sprite gen, music MCP. Flag honestly; don't invent an OSS option.

**Pipeline (the same in both engines):** design intent (game-designer) → generate raw asset (Tripo/Meshy/blender-mcp/ElevenLabs) → refine in Blender (blender-mcp) → import + place + wire in-engine (unity-developer via CoplayDev / unreal-developer via ChiR24 bridge) → play/PIE-verify → iterate.

## The three-layer pattern that unlocks "do it for me" in games
Engine-control (execute) **+** asset-gen (the shared layer) **+** design/orchestration (game-designer: MDA/SDT/Flow + OpenGame scaffold-then-debug). **All three, not one.** game-designer owns layer 3 and orchestrates the other two via unity-developer / unreal-developer.

## Sources
- dawdle-deer/awesome-learn-gamedev (CC0), Roobyx/awesome-game-design (CC0) - referenced as public-domain corpora.
- Machinations.io - commercial, CONNECT-only reference.
- Shared asset layer repos as cited (MIT / commercial) - CONNECT, documented not absorbed.
