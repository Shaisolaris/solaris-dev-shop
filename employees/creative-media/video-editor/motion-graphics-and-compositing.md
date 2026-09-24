# Templated motion graphics + programmatic compositing

## Remotion - branded templated motion graphics (ABSORB, license flag)
Remotion (~48k stars, source-available - FREE for individuals/orgs up to 3 employees; PAID at 4+ - flag the license before client commercial use). Write motion graphics in React; render to video programmatically.
- Use for: branded lower-thirds, intros/outros, data-driven explainers, templated Shorts where text/assets are parameters.
- Pattern: build a React composition with props → render via Remotion CLI / `@remotion/renderer` with a props JSON → MP4. Templated = same design, swapped content per video.
- License: confirm employee count vs the 3-seat free threshold before using on paid client work.

## MoviePy - programmatic compositing / caption burn-in (ABSORB, MIT)
MoviePy (~15k stars, MIT). Python video compositing for headless renders.
- Use for: burning captions onto clips, overlaying text/images, concatenation with effects, programmatic Shorts assembly where FFmpeg filtergraphs get unwieldy.
- Plays well with WhisperX output: take word-level timestamps → render styled captions onto a 9:16 clip.

## When to use which
- **Resolve MCP** - manual/finishing motion graphics + Fusion comps in a real timeline.
- **Remotion** - repeatable, parameterized, code-defined templates (do it 100x with different data).
- **MoviePy** - quick headless compositing/caption burn-in in a Python pipeline.
- **FFmpeg (existing)** - the lowest-level filtergraph/overlay/burn-in baseline.
