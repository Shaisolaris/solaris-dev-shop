# HyperFrames - agent HTML-to-MP4 video rendering (methodology)

Absorbed 2026-06-14 from heygen-com/hyperframes (Apache-2.0, ~27.6k stars, used in production at HeyGen). Methodology only; no code bundled. License note: Apache-2.0, no per-render fees and no commercial-use thresholds, so it is the open license-clean alternative to the source-available Remotion license already flagged in motion-graphics-and-compositing.md.

## What it is and when to reach for it

HyperFrames turns an HTML/CSS/media file with seekable animations into a deterministic MP4. It is the right tool when the video is generated from code/data rather than cut from existing footage: product-launch promos, PR/changelog walkthroughs, data-viz and chart races, docs-to-video / website-to-video explainers, kinetic-caption social clips, and reusable templated motion graphics for automated pipelines.

It is NOT an NLE. It composes frames; it does not edit a finished video stream. So:
- Existing footage is overlaid, never edited. Captions or designed graphic overlays (lower-thirds, data callouts, titles) play on top; the clip underneath is untouched. Re-timing, recolor, reframe, reorder, or audio changes to the source are NLE work and stay with the FFmpeg/Resolve lane in this employee.
- It cannot conjure inputs it does not have: no screen/session recording, no camera capture, no AI talking-head generation. Supply the asset first.
- The render is self-contained: every value, asset, and string is baked in at author time. No live at-render-time data pull.

vs Remotion (already in this employee, license-flagged): same headless-Chrome + FFmpeg render core. Authoring model differs - Remotion bets on React components and needs a bundler; HyperFrames bets on plain HTML with no build step, which is what makes it agent-friendly (agents already write HTML; an index.html composition plays as-is in a browser). Pick HyperFrames when you want a license-clean, no-build, HTML-native path; pick Remotion when the client is already on a React video stack (mind its seat/render pricing).

## The composition contract (author-time rules)

A composition is an HTML file driven by data attributes. The authoring contract:
- Stage element carries the composition id and frame size, e.g. data-composition-id, data-start, data-width, data-height.
- Every timed element needs data-start, data-duration, and data-track-index, and must carry class="clip".
- Animation is seekable, plugged in via a frame-adapter pattern. GSAP is the primary adapter (also CSS, Lottie, Three.js, Anime.js, WAAPI, or a custom runtime). GSAP timelines must be created paused and registered on window.__timelines so the engine can seek them frame by frame.
- Deterministic logic only: no Date.now(), no unseeded Math.random(), no render-time network fetches. This is what guarantees same input -> same frames -> same output (the property that makes it CI- and regression-test-friendly).

## The agent production loop

Plan the video -> write valid HTML -> wire seekable animations -> add media -> lint -> preview -> render. Operationally:
1. Plan: pick aspect (16:9 default; 9:16 for TikTok/Reels/Shorts), length, scenes/beats, and the design tokens. A frame.md (a DESIGN.md superset written for the camera, with scale and motion rules) keeps tokens consistent across scenes.
2. Author the composition HTML against the contract above.
3. Lint then validate every composition after any edit: a static HTML-structure check, then a runtime check in headless Chrome that catches JS errors and missing assets. Both must pass before previewing or calling the work done.
4. Preview in-browser with live reload to eyeball timing.
5. Render to MP4: the engine seeks each frame in headless Chrome and FFmpeg encodes the result. Local render or distributed (AWS Lambda render path) for scale/CI.

Determinism is the discipline here: because the output is reproducible, treat renders like build artifacts - golden-baseline regression tests on output frames are a first-class workflow, not an afterthought.

## Intent routing (when an agent is asked to "make a video")

HyperFrames ships agent skills that route intent to a concrete workflow. The useful shape to remember:
- Input TYPE is the primary axis; length is only a ceiling. The dedicated workflows handle up to ~3 min; genuinely longer pieces (3-5 min tutorial, 5 min+ deep dive) and static/loops fall back to a general authoring flow.
- Product URL or brief -> product-launch/promo. General website/URL -> a tour/showcase video of the site. GitHub PR -> code-change explainer. Topic/text with no URL -> faceless explainer (every visual LLM-invented). Existing talking-head clip -> captions, or designed graphic overlays (split by intent, any length; footage untouched). Short (<~10s) unnarrated design-led piece -> motion graphic (an output genre that short-circuits the input table).

## CONNECT note

CONNECT, host-installed. The host installs the HyperFrames CLI (Node.js 22+ and FFmpeg required); the agent then drives `hyperframes init / preview / lint / validate / render` (and `hyperframes add <block>` to pull from the 50+ block catalog). The agent skills can be installed with `npx skills add heygen-com/hyperframes`. No HyperFrames code is vendored into this employee - this file is the methodology; the runtime lives on the host. FFmpeg is already the core dependency of this employee, so the marginal install is the HyperFrames CLI itself.

## Cross-reference

- motion-graphics-and-compositing.md - Remotion (license-flagged) + MoviePy + basic templated render. HyperFrames is the no-build, Apache-licensed sibling path; both render via headless Chrome + FFmpeg.
- For routing: when content marketing or another employee needs an HTML/data-driven or templated promo/explainer video (not footage editing), route to video-editor for the HyperFrames path.
