# Programmatic video: Remotion depth + Manim explainers

Methodology absorbed from ECC `remotion-video-creation` (29 domain rules) and `manim-video` (affaan-m/ECC, MIT). Gate-0: motion-graphics-and-compositing.md already establishes Remotion's existence, the 3-seat license flag, and the basic build-a-React-composition-with-props-then-render pattern - that is NOT repeated here. This file is the net-new craft depth (how to actually animate correctly in Remotion) plus Manim, which the employee did not cover at all. License flag still governs paid client use - see motion-graphics-and-compositing.md and rules.md.

## Remotion - correctness rules that prevent broken renders

### Animation is frame-driven, never CSS
- Every animation MUST be driven by `useCurrentFrame()`. Write durations in seconds and multiply by `fps` from `useVideoConfig()` so the same composition is fps-portable.
- CSS transitions/animations and Tailwind animation class names are FORBIDDEN - they do not render deterministically frame-by-frame and will produce wrong or empty output.

### Timing / interpolation
- Linear: `interpolate(frame, [0, 100], [0, 1])`. Values are NOT clamped by default - pass `{extrapolateLeft:'clamp', extrapolateRight:'clamp'}` to hold at the ends (the common fade-in bug is an unclamped opacity going past 1 or below 0).
- Springs for natural motion: `spring({frame, fps})`. Default `{mass:1, damping:10, stiffness:100}` bounces; use `{damping:200}` for a settle-without-bounce.

### Sequencing and series
- `<Sequence from={1*fps} durationInFrames={2*fps} premountFor={1*fps}>` delays when an element appears. ALWAYS premount sequences so assets/components load before they play (prevents pop-in / blank frames).
- `<Sequence layout="none">` to avoid the default absolute-fill wrapper.
- `<Series>` with `<Series.Sequence durationInFrames={n}>` for back-to-back scenes with no overlap (intro/main/outro).
- Trimming: cut the start/end of an item via sequence offsets rather than editing source.

### calculateMetadata - dynamic duration/dimensions (the key to data-driven templates)
- Put `calculateMetadata` on the `<Composition>` to set duration/dimensions/props at render time from the actual inputs, instead of hardcoding `durationInFrames`.
- Match a source video: `durationInFrames = Math.ceil(durationInSeconds * fps)`, width/height from the media metadata. For multi-clip stitches, sum each clip's duration. This is what makes "render 100 videos with different data" actually correct - each output is exactly as long as its content.

### Captions (the auto-Shorts payoff)
- Install `@remotion/captions`. `createTikTokStyleCaptions({captions, combineTokensWithinMilliseconds})` groups word-level captions into pages; lower ms = more word-by-word, higher = more words per page. Render each page in its own `<Sequence>` with start/duration from the page timing -> TikTok-style word-highlight captions.
- Transcription options: `@remotion/install-whisper-cpp` (local, fast, free, needs server), `@remotion/whisper-web` (in-browser WASM, free, slower), `@remotion/openai-whisper` (cloud API, paid). Or import existing `.srt`/`.vtt` via `@remotion/captions`. (Inside this employee, WhisperX word timestamps from the auto-Shorts pipeline can feed the Caption format directly.)

### Media validation with Mediabunny (avoid render-time failures)
- `canDecode(src)` (Mediabunny `Input` + `UrlSource`, copy-paste helper) checks a video/audio can be decoded BEFORE you compose it - gate remote assets so a bad source fails fast instead of producing a black render.
- Mediabunny also gives audio duration, video duration, and dimensions for `calculateMetadata`, plus frame extraction at timestamps.

### Other rule areas to pull on demand (from the 29-rule set)
3D via Three.js / React Three Fiber, Lottie embedding, charts/data-viz compositions, fonts (Google + local), images (`<Img>`), GIFs synced to the timeline, transitions, text-animations (typewriter, word-highlight), measuring DOM nodes / text for fit-to-container, audio (trim/volume/speed/pitch), Tailwind setup. Read the specific ECC rule file when a render needs that area.

## Manim - precise technical explainers (net-new, not previously covered)

Use Manim when motion, structure, and clarity matter more than photorealism: graphs, workflows, architecture diagrams, metric progressions, system diagrams, short product/launch explainers. Choose this over a generic talking-head when the visual should feel precise, not cinematic.

### Tooling
- `manim` CLI to render scenes; `ffmpeg` (this employee's baseline) for post; hand off to the timeline (Resolve/FFmpeg) for final assembly, or to Remotion when the final package needs composited UI, captions, or extra motion layers on top of the Manim render.

### Workflow
1. State the core visual thesis in ONE sentence.
2. Break the concept into 3-6 scenes; decide what each scene proves.
3. Write the scene outline BEFORE any Manim code.
4. Render the smallest working version first (smoke test): `manim -ql scene.py SceneName`.
5. Only after composition + timing are stable, tighten typography, spacing, color, pacing and push to higher quality.
6. Hand off to the wider video stack only if it adds value.

### Scene-planning rules
- Each scene proves one thing; avoid overstuffed diagrams. Prefer progressive reveal over full-screen clutter. Use motion to explain state change, not just to keep the screen busy. Title cards short and loaded with meaning.

### Render conventions
- Default 16:9 landscape unless vertical is requested. Always start `-ql` (low-quality) smoke test, raise quality only when stable. Export one clean thumbnail/poster frame that reads at social size.

### Output to return
Core visual thesis, storyboard, scene outline, render plan, follow-on polish recommendations.

## When to use which (programmatic lane vs the rest)
- Manim -> precise technical/diagrammatic explainers (graphs, architecture, metrics).
- Remotion -> repeatable, parameterized, code-defined branded templates and motion-heavy compositing (incl. compositing a Manim render with UI/captions). License-flag before paid client use.
- Resolve MCP -> manual finishing / Fusion comps in a real timeline.
- MoviePy -> quick headless Python compositing / caption burn-in.
- FFmpeg -> lowest-level filtergraph/overlay/burn-in baseline.
(See motion-graphics-and-compositing.md for Remotion/MoviePy basics and rules.md for the full tool-selection rules.)
