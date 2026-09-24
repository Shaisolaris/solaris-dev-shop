# Design Frameworks - motivation, flow, audience, studio structure

> Deepened 2026-06-13 from **Donchitos/the coding agent-Code-Game-Studios** (~18.6k★, MIT) - "Design Philosophy" + studio hierarchy + verification-driven development. MDA is covered in SKILL.md + rules.md already (Gate 0: not duplicated here). This file adds the net-new theory and the studio operating model.

## The four philosophies a coding agent Game Studios grounds every design in
Donchitos builds its 49-agent studio on five professional pillars. MDA we already have; the net-new four:

### 1. Self-Determination Theory (SDT) - why players keep playing
Intrinsic motivation comes from three needs. A design that starves any one of them bleeds retention:
- **Autonomy** - the player feels their choices are their own. Meaningful options, not illusory ones. (Forced tutorials, on-rails sequences, and "only one right answer" puzzles violate autonomy.)
- **Competence** - the player feels capable and improving. Difficulty that rises with skill; clear feedback that "I'm getting better." (Both boredom and overwhelming difficulty kill competence.)
- **Relatedness** - the player feels connected - to other players, to characters, or to a world that reacts to them.
**Use it as a checklist:** for any new system, ask which of A/C/R it serves and which it might starve. A loot system serves competence; if it's pure RNG with no skill input it can starve autonomy.

### 2. Flow State - the challenge/skill balance
Flow (Csikszentmihalyi) is the channel between anxiety (challenge > skill) and boredom (skill > challenge). Players stay engaged when difficulty tracks their rising skill.
- **Design implication:** difficulty is a *curve that follows the player*, not a fixed wall. Dynamic difficulty, optional challenge tiers, and skill-gated content keep players in the channel.
- **Pair with SDT competence:** flow IS the felt experience of competence being continuously met.
- **The 4 Design-Review-Protocol questions** (in rules.md) are a flow tool: "what's their single next action" keeps the challenge legible.

### 3. Bartle Player Types - who you're designing for
Four archetypes; most games over-serve one and ignore the others:
- **Achievers** - want mastery, completion, leaderboards, 100%.
- **Explorers** - want to discover systems, secrets, lore, edge-cases.
- **Socializers** - want to interact, cooperate, show off, belong.
- **Killers** - want to compete against and dominate other players.
**Use it for audience targeting + validation:** name the primary + secondary type your game serves, record it in the pillars. Validate playtest recruiting against it - testing a socializer game only with achievers gives false signal.

### 4. Verification-Driven Development - tests before implementation
Donchitos enforces "tests first, then implementation" as a design discipline, not just an engineering one: a feature's *success criteria* are defined (and made checkable) before it's built. For Solaris this dovetails with the OpenGame eval loop (see `orchestration-prompt-to-playable.md`) and with unity-developer's Tier-0 autonomous test loop - design states the win condition, engineering verifies it.

## The studio operating model (agent/skill patterns)
Donchitos models a real studio as a 3-tier hierarchy. We don't adopt its 49 agents wholesale (Solaris has its own roster), but the **coordination patterns** are the absorbable wisdom:

**Tier structure (the pattern, not the headcount):**
- **Directors** guard the vision (creative-director, technical-director, producer).
- **Department leads** own a domain (game design, programming, art, audio, narrative, QA, release).
- **Specialists** do the hands-on work (gameplay/engine/AI/UI programmers, systems/level/economy designers, technical artists, writers, testers).

**The five coordination rules (directly usable in how game-designer collaborates with unity-developer / unreal-developer / ui-ux-designer):**
1. **Vertical delegation** - directors → leads → specialists. Don't skip tiers.
2. **Horizontal consultation** - same-tier roles consult each other but can't make binding cross-domain decisions alone.
3. **Conflict resolution escalates to the shared parent** - design disputes → creative-director; technical disputes → technical-director.
4. **Change propagation is owned** - cross-department changes are coordinated by a producer role, not left to chance.
5. **Domain boundaries are respected** - don't modify files/decisions outside your domain without explicit delegation. (This is the same discipline as the Solaris "what this employee does NOT do" sections.)

**Collaborative, not autonomous (Donchitos's core stance, which matches Solaris doctrine):** Ask → present 2-4 options with pros/cons → user decides → draft → approve. Nothing ships without sign-off. The studio provides structure + expertise, not auto-pilot.

**Review intensity is a dial:** `full` (all director gates) / `lean` (phase gates only) / `solo` (none). Pick per project size - a Solaris Studio prototype runs `solo`/`lean`; a client deliverable runs `full`.

**Path-scoped standards (the idea):** coding/design standards enforced by *where a file lives* - gameplay code is data-driven + uses delta time + holds no UI refs; GDDs require their standard sections; prototypes get relaxed standards + a documented hypothesis. Translate to Solaris by keeping these as review checklists per area.

## Sources
- Donchitos/the coding agent-Code-Game-Studios (MIT) - README "Design Philosophy" (SDT, Flow, Bartle, verification-driven dev), "Studio Hierarchy", "How It Works" (coordination model, collaborative stance, review modes, path-scoped rules). Concepts distilled, not copied.
