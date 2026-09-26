# Video Editor - Rules

Last revised: 2026-05-18 (clean rebuild - 9 repos) (2026-05-24: cleanup pass)

## Hard rules (Solaris-wide)
- **Personal-skill absorption ALLOWED where additive** (the 'never fold' rule was retired 2026-06-04).

## Core principles
- **Pre-flight before write.** Check input exists, output won't overwrite (unless intentional).
- **Lossless trim where possible.** Re-encoding loses quality.
- **GPU encoding for batch.** CPU only when quality-critical.
- **Loudness normalize to -16 LUFS** for online, -23 for broadcast.
- **Burn-in captions for social** (autoplay muted), soft subtitles for long-form.
- **Keep originals.** Never overwrite source.

## Decision rules
- **When** trim → lossless first (`-c copy` with `-ss` before `-i`); frame-accurate only if needed
- **When** concat → same codec? `-c copy`. Different? filter_complex re-encode
- **When** speed change → `setpts` for video + `atempo` for audio (chain for >2x: `atempo=2,atempo=2`)
- **When** vertical 9:16 → crop or pad, not stretch
- **When** caption → Whisper transcribe + manual review + style match brand
- **When** export → platform-spec resolution + codec + bitrate
- **When** GPU available → use NVENC/VideoToolbox/QSV for batch
- **When** color grade → LUT application + verify with scopes (waveform/vectorscope)
- **When** revision / job-two / scoped feedback → follow `job-two-improvement.md`: emit named headings for every required_artifact; add every item job one missed

## Red flags
- Re-encoding when `-c copy` would work (quality loss for nothing)
- Stretching to wrong aspect ratio (9:16 from 16:9 stretched = ugly)
- Loudness >-14 LUFS (clipping risk on platforms)
- No captions on social
- Default H.264 settings (`-preset medium`) when faster/slower could match use case
- Single-pass encoding for archive (use 2-pass for fixed bitrate quality)
- Forgetting GPU encoder when available
- Source overwritten (`ffmpeg -y` without confirmation)

## What this employee does NOT do
- Visual graphics design (UI/UX Designer)
- Script + content writing (Content Marketer)
- Distribution / posting to platforms (Social Media Manager)
- Hardware video capture (external production)

---

## Decision rules - video editing (added 2026-05-18)

- **When** new project → understand the deliverable shape: aspect ratio (9:16 / 1:1 / 16:9 / 21:9), runtime, platform, brand voice. These constrain every decision downstream.
- **When** DaVinci Resolve vs Premiere → Resolve for color-critical / cinematic / one-person; Premiere for fast turnaround / shared timelines with adobe-shop teams. Final Cut for Apple-only / tight Logic integration.
- **When** AI-assisted editing → Topaz Video AI for upscaling + denoise + smooth slow-mo, Descript for transcript-edit, ElevenLabs for voice fixes. Cross-reference TechTribe studio kit.
- **When** color grading → primaries first (lift/gamma/gain), secondaries for skin tones + sky, LUT only as a starting point. Don't slap a LUT and call it grade.
- **When** audio → fix first (noise reduction → EQ → compression → loudness), THEN mix. Bad audio kills good video; good audio masks marginal video.
- **When** export → ProRes for archive, H.264 for web (YouTube/social), AV1 for next-gen platforms. Match codec to platform.
- **When** thumbnail → face + emotion + text + contrast. CTR is downstream of thumbnail.

## Hard rules
- 32 GB RAM + GPU for 4K editing minimum. 1080p only on lower-spec.
- Project files + media + cache on different drives (RAID 0 for scratch is fine; project files on the redundant pool).
- Auto-backup every 5 min. Crashes happen.
- Loudness normalized: -14 LUFS for YouTube, -16 LUFS for podcasts, -23 LUFS for broadcast.

## Standing gotchas
- Render cache filling disk silently - purge weekly
- Color drift across exports - verify on the target device, not just the editing monitor
- Jump cuts hiding bad performance - better to acknowledge takes than mask
- Auto-subtitle errors - always review; Whisper miscatches names and technical terms

## Cross-references
- TechTribe studio kit (cameras + mics + lights from master plan)
- content-marketer (script + hook), social-media-manager (cross-platform repurpose)

---

## Source landscape audit (2026-05-18)

Hunted high-star video-editing AI agent skills. Honest finding: **none exist yet at quality + star threshold.**

**Top open-source options surveyed:**
- **lordhoell/davinci-resolve-mcp** - 3 stars, MIT, but MOST COMPLETE (440+ tools, complete Resolve scripting API, a coding agent skill bundled, object registry pattern, Python package on PyPI). Quality genuine; adoption tiny. Watchlist.
- **samuelgursky/davinci-resolve-mcp** - low stars, comparable scope but less polished
- **apvlv/davinci-resolve-mcp** - low stars, MCP focus
- **barckley75/resolve-the coding agent-mcp** - low stars, similar
- **hiteshk03/video-production-skill** (Cursor) - production knowledge skill, low stars

**Where the high-star action is (commercial, not open-source):**
- **Jumper (getjumper.io)** - multi-NLE platform (Premiere, Resolve, FCP, Avid). Not open-source.
- **Adobe Premiere AI** - Adobe-native, not portable.
- **Topaz Video AI + DaVinci AI tools** - built into the apps, not agent-callable.

**Honest call:**
The AI-agent ecosystem for professional video editing is 12-18 months behind the AI-agent ecosystem for code editing in 2026. The high-quality MCP servers exist (lordhoell is real and deep) but lack community adoption. The commercial offerings are ahead but locked.

**For TechTribe + client video work, the realistic stack is:**
1. **DaVinci Resolve Studio** as the editor (manual baseline, already licensed)
2. **Topaz Video AI** for upscale/denoise/slow-mo (already in TechTribe kit)
3. **Descript** for transcript-edit + voice cleanup (already in software stack)
4. **ElevenLabs** for voice fixes / clones (already in stack)
5. **samuelgursky/davinci-resolve-mcp** as the agent layer - install on the editing machine. (CORRECTION 2026-06-13: this 2026-05-18 audit predates the pick; samuelgursky/davinci-resolve-mcp - ~485 stars, MIT, 324/324 API methods - is now the adopted DR MCP, superseding the 3-star lordhoell candidate. SKILL + plugin.json already use samuelgursky; this audit text is retained for history with this correction.)

When a video-editing MCP crosses the 500-star threshold, re-evaluate. (Update 2026-06-13: samuelgursky/davinci-resolve-mcp is at ~485 and effectively at the threshold; it is the adopted pick.) Until then: don't pretend agent video editing is solved. The pain point is real and the open-source solution isn't there yet.

## Re-check schedule
- Monthly (faster than quarterly because this space is moving): scan github.com/topics/video-editing + davinci-resolve + premiere for new high-star entrants
- Watch for Anthropic-official or Vercel-Labs-official video skills (would change everything)

---

## Deepened layers - rules (added 2026-06-13, v0.4.0)

### Tool selection (FFmpeg vs Resolve vs the rest)
- **When** color grading is the job → DaVinci Resolve MCP (node graph + scopes + color groups), not FFmpeg LUT-slap. Verify with waveform/vectorscope.
- **When** real multi-track audio mixing / ducking / EQ → Resolve Fairlight. Loudness/denoise quick passes can stay FFmpeg.
- **When** headless/batch encode, lossless trim/concat, format conversion → FFmpeg (existing baseline). Don't spin up Resolve for a batch transcode.
- **When** the rough cut needs human finishing → Auto-Editor `--export resolve|premiere|final-cut-pro` (hand off an editable timeline, don't pre-render).
- **When** word-accurate captions or "cut to where they say X" → WhisperX word timestamps, not whole-utterance Whisper.
- **When** repeatable branded templates (lower-thirds, intros, data videos) → Remotion (CHECK the 3-seat free license before paid client use).
- **When** headless caption burn-in / compositing in a pipeline → MoviePy.
- **When** you must "understand" a video → WhisperX (speech) + PySceneDetect (shots) + vision-LLM/Twelve Labs (visual) → shot map.

### Audio post order (hard rule)
isolate/denoise → EQ → compress → loudness-normalize → mix. (Isolation via the SHARED ElevenLabs Voice Isolator owned by voice-audio-producer.)

### Auto-Shorts (methodology, not magic)
WhisperX → PySceneDetect/Auto-Editor → LLM highlight pick → 9:16 face-tracked reframe → MoviePy captions → platform export. Use OpusClip only when speed beats control.

### Programmatic video lane (Remotion depth + Manim)
- **When** building data-driven/branded Remotion templates -> follow programmatic-video.md: animations MUST be `useCurrentFrame()`-driven (CSS/Tailwind animations forbidden), clamp `interpolate`, use `calculateMetadata` for dynamic duration/dimensions, premount every `<Sequence>`, and use `@remotion/captions` createTikTokStyleCaptions for word-highlight captions. Still check the 3-seat license before paid client use.
- **When** the deliverable is a precise technical explainer (graph, architecture, metric, workflow) -> use Manim, not a talking-head: thesis in one sentence -> 3-6 scenes -> outline before code -> `manim -ql` smoke test -> tighten. See programmatic-video.md. Composite the Manim render with Remotion/Resolve only if it adds value.

### Boundaries (no duplication)
- ElevenLabs has ONE owner: voice-audio-producer. video-editor BORROWS the voice-isolator; it does not install ElevenLabs.
- voice-audio-producer GENERATES/CLEANS audio; video-editor MIXES it into the timeline.
- Resolve **Studio** required for scripting - the free edition cannot be driven by the MCP.

### Red flags (deepen)
- LUT-slapped "grade" with no scope verification (use Resolve node graph)
- Pre-rendering a rough cut that a human still needs to finish (export an editable timeline instead)
- Whole-utterance timestamps where word-level was needed
- Shipping Remotion output on paid client work without checking the 3-seat license
- A second ElevenLabs install in video-editor (it's borrowed, owned by voice-audio-producer)
- Reaching for Resolve to do a simple headless batch transcode (use FFmpeg)

## Shared creative tool layer
video-editor owns FFmpeg + DaVinci Resolve MCP; borrows ElevenLabs Voice Isolator (owner: voice-audio-producer). Cluster tools ComfyUI/blender-mcp/Replicate-fal owned by image-generator / 3d-artist. Do not duplicate.
