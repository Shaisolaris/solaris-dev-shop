# Agentic video editing - the conversation-to-final.mp4 loop

Methodology absorbed from browser-use/video-use (MIT, ~7.9k stars, by the browser-use team; verified 2026-06-15). Methodology only; no code bundled or run. This is the editing-as-conversation operating doctrine: how an agent with shell + ffmpeg edits raw footage into a finished cut without presets or menus. It sits ON TOP of the existing FFmpeg/Resolve/WhisperX/Remotion/Manim/HyperFrames stack and tells the agent how to drive them.

Gate-0 dedup: this file deliberately does NOT re-cover transcription engines (WhisperX/auto-edit-and-vision.md owns that), animation engines (Remotion/Manim/HyperFrames already in programmatic-video.md + hyperframes-html-video.md), color-grade fundamentals or subtitle burn-in (SKILL.md + rules.md own those). It adds only the net-new agentic LOOP, the text-as-edit-surface technique, the production-correctness hard rules, and the self-eval discipline.

## Core insight: the LLM reads the video, it does not watch it

Naive frame-dumping is 30,000 frames x ~1,500 tokens = ~45M tokens of noise. The agentic approach gives the model a structured text surface plus on-demand visual drill-downs instead. Same idea as giving an LLM a structured DOM instead of a screenshot - applied to video.

Two layers:
1. **Text transcript (always loaded).** Word-level verbatim ASR -> a packed phrase-level markdown (`takes_packed.md`) that is the model's primary reading view. ~12KB for a whole multi-take shoot.
2. **Visual composite (on demand only).** A filmstrip + waveform + word-label PNG for a chosen time range. Called at decision points (ambiguous pauses, retake comparison, cut-point sanity check), never as a constant scan.

This packing layer is net-new vs the existing WhisperX note: WhisperX gives the timestamps; this is the discipline of turning them into a compact reading surface and reasoning from text first.

### The packed-transcript format
Break phrases on any silence >= 0.5s OR speaker change. Prefix each line with its `[start-end]` range and speaker tag. Example:
```
## C0103  (duration: 43.0s, 8 phrases)
  [002.52-005.36] S0 Ninety percent of what a web agent does is completely wasted.
  [006.08-006.74] S0 We fixed this.
```
The editor reasons over this to pick cuts with word-boundary precision from text alone, at roughly 1/10 the tokens of raw timestamp JSON.

## The operating loop (the part the employee was missing)

```
Inventory -> Pre-scan -> Converse -> Propose strategy -> [confirm] -> Execute -> Preview -> Self-eval -> Iterate -> Persist
```

1. **Inventory.** ffprobe every source. Transcribe all sources (this employee uses WhisperX; word-level verbatim, cached). Pack into the reading view. Sample one or two visual composites for a first impression.
2. **Pre-scan for problems.** One pass over the packed transcript noting verbal slips, mis-speaks, phrasings to avoid. Plain list, fed into the editor brief.
3. **Converse.** Describe what you see in plain English. Ask questions SHAPED BY THE MATERIAL (no fixed checklist). Collect: content type, target length + aspect, aesthetic/brand direction, pacing feel, must-preserve and must-cut moments, animation + grade + subtitle preferences.
4. **Propose strategy.** 4-8 sentences: shape, take choices, cut direction, animation plan, grade direction, subtitle style, length estimate. WAIT for confirmation.
5. **Execute.** Produce an EDL (cut decision list, JSON). Drill into the visual composite at ambiguous moments. Build animations in PARALLEL sub-agents. Apply grade per-segment. Compose.
6. **Preview.** Fast 720p render.
7. **Self-eval BEFORE showing the user** (see below).
8. **Iterate + persist.** Natural-language feedback, re-plan, re-render. Never re-transcribe. Append a session entry to `project.md`.

Discipline: **Ask -> confirm -> execute -> self-eval -> persist. Never touch the cut before the user has approved the plain-English plan.**

## Production-correctness hard rules (non-negotiable - silent failures otherwise)

These are correctness, not taste. They map directly onto the ffmpeg pipeline this employee already runs.

1. **Subtitles are applied LAST in the filter chain**, after every overlay. Otherwise overlays hide captions (silent failure).
2. **Per-segment extract -> lossless `-c copy` concat**, NOT a single-pass filtergraph. A single-pass graph double-encodes every segment once overlays are added.
3. **30ms audio fades at every segment boundary:** `afade=t=in:st=0:d=0.03,afade=t=out:st={dur-0.03}:d=0.03`. Otherwise an audible pop at every cut.
4. **Overlays use `setpts=PTS-STARTPTS+T/TB`** to shift the overlay's frame 0 to its window start. Otherwise you see the middle of the animation during the overlay window.
5. **Master SRT uses output-timeline offsets:** `output_time = word.start - segment_start + segment_offset`. Otherwise captions misalign after segment concat.
6. **Never cut inside a word.** Snap every cut edge to a word boundary from the transcript.
7. **Pad every cut edge** (working window 30-200ms). ASR timestamps drift 50-100ms; padding absorbs the drift. Tighter for fast-paced, looser for cinematic.
8. **Word-level verbatim ASR only.** Never SRT/phrase mode (loses sub-second gap data); never normalized fillers (loses editorial signal). This is WHY the employee uses WhisperX `--highlight_words` word output, not plain Whisper SRT.
9. **Cache transcripts per source.** Never re-transcribe unless the source file changed.
10. **Parallel sub-agents for multiple animations.** Never sequential; spawn N at once, total wall time approximately the slowest one.
11. **Strategy confirmation before execution.** Never touch the cut until the plain-English plan is approved.
12. **All session outputs in `<videos_dir>/edit/`.** Never write inside the skill/project directory. (Matches this employee's "keep originals, never overwrite source" rule.)

## Self-eval loop (net-new QA discipline)

Run the visual composite on the RENDERED OUTPUT (not the sources) at every cut boundary (+/-1.5s window). At each boundary check:
- Visual discontinuity / flash / jump at the cut.
- Waveform spike at the boundary (an audio pop that slipped past the 30ms fade).
- Subtitle hidden behind an overlay (Rule 1 violation).
- Overlay misaligned or showing wrong frames (Rule 4 violation).

Also sample first 2s, last 2s, and 2-3 mid-points for grade consistency, subtitle readability, coherence. ffprobe the output to verify duration matches the EDL. If anything fails: fix -> re-render -> re-eval. **Cap at 3 passes**; if issues remain, flag to the user rather than looping. Present the preview only after self-eval passes.

## EDL format (cut decision list)

```json
{
  "version": 1,
  "sources": {"C0103": "/abs/path/C0103.MP4"},
  "ranges": [
    {"source": "C0103", "start": 2.42, "end": 6.85, "beat": "HOOK",
     "quote": "...", "reason": "Cleanest delivery, stops before slip at 38.46."}
  ],
  "grade": "warm_cinematic",
  "overlays": [{"file": "edit/animations/slot_1/render.mp4", "start_in_output": 0.0, "duration": 5.0}],
  "subtitles": "edit/master.srt",
  "total_duration_s": 87.4
}
```
`grade` = a preset name or a raw ffmpeg filter. `overlays` = rendered animation clips. `subtitles` applied LAST.

## Editor sub-agent brief (multi-take selection)

When the task is "pick the best take of each beat across many clips," spawn a dedicated sub-agent. The structure is load-bearing; the values are examples.
- Inputs: the packed transcript, 2 sentences of product/narrative context, speaker notes, expected structure, the slip list from the pre-scan, target runtime.
- Structural archetypes (pick, adapt, or invent): tech-launch (HOOK -> PROBLEM -> SOLUTION -> BENEFIT -> EXAMPLE -> CTA); tutorial (INTRO -> SETUP -> STEPS -> GOTCHAS -> RECAP); interview (QUESTION -> ANSWER -> FOLLOWUP repeat); travel/event (ARRIVAL -> HIGHLIGHTS -> QUIET -> DEPARTURE); documentary (THESIS -> EVIDENCE -> COUNTERPOINT -> CONCLUSION); music (INTRO -> VERSE -> CHORUS -> BRIDGE -> OUTRO).
- Rules into the brief: cut edges on word boundaries; pad 30-200ms; prefer silences >= 400ms as cut targets; keep unavoidable slips only if no better take exists and note them; if over budget, drop a beat or trim tails and self-correct.
- Output: a JSON EDL array, no prose, plus a one-line runtime check.
- Assemble chronologically BY BEAT, not by source-clip order.

## Cut craft (editorial, net-new specifics)

- **Audio-first.** Cut candidates come from word boundaries and silence gaps; never reason audio and video independently - every cut must work on both tracks.
- **Silence-gap tiers:** >= 400ms silences are the cleanest cut targets; 150-400ms phrase boundaries are usable with a visual check; < 150ms is unsafe (mid-phrase).
- **Preserve peaks.** Laughs, punchlines, emphasis beats. Extend PAST a punchline to include the reaction - the laugh IS the beat.
- **Audio events as signals.** `(laughs)`, `(sighs)`, `(applause)` mark beats; extend past them.
- **Speaker handoffs** want air between utterances - commonly 400-600ms; less for fast-paced, more for cinematic.
- **Animation payoff sync (for sync-to-narration overlays):** get the payoff word's timestamp, start the overlay `reveal_duration` seconds earlier so the landing frame coincides with the spoken payoff word.

## Session memory - project.md

Append one section per session at `<edit>/project.md`: Strategy (one paragraph), Decisions (take choices, cuts, grades, animations + why), Reasoning log (one-liners for non-obvious calls), Outstanding (deferred). On startup, read it if present and summarize the last session in one sentence before asking whether to continue.

## Anti-patterns (consistently fail regardless of style)

- Hierarchical pre-computed shot/codec/tone classifications - over-engineering; derive from the transcript at decision time.
- Hand-tuned moment-scoring heuristics - the LLM picks better than any scoring function.
- Whisper SRT / phrase-level output - loses sub-second gap data; always word-level verbatim.
- Single-pass filtergraph when overlays exist - double re-encode; use per-segment extract -> concat.
- Linear animation easing - robotic; use cubic (ease_out_cubic for single reveals, ease_in_out_cubic for continuous draws).
- Hard audio cuts at boundaries - audible pops (Rule 3).
- Editing before confirming the strategy.
- Re-transcribing cached sources.
- Assuming what kind of video it is - look first, ask second, edit last.

## CONNECT notes - local generative video + restoration (commercial-safe additions)

These are host installs / model downloads, methodology + license flags only. They extend the b-roll and finishing toolset for client/commercial work.

- **faster-whisper** (SYSTRAN/faster-whisper, MIT, ~23k+ stars, active). SKIPPED as a distinct technique: WhisperX (auto-edit-and-vision.md) already uses faster-whisper as its backend and adds word-level alignment + diarization on top, so transcription is covered. Use plain faster-whisper ONLY as a lighter standalone STT pass when you need fast captions and do NOT need forced alignment or diarization (e.g. quick burn-in on a single talking head). Not a net-new editing capability; no separate methodology added.
- **Real-ESRGAN** (xinntao/Real-ESRGAN, BSD-3-Clause, ~28k stars). Practical super-resolution for image AND video restoration. CONNECT: host installs the realesrgan-ncnn-vulkan binary (cross-platform, GPU) for upscaling low-res source or b-roll, denoising, and 2x/4x enlargement before a finish. Commercial-safe (BSD). Pairs with the existing Topaz Video AI note in rules.md as the free/OSS upscaling alternative. Flag: the BSD code is clean; some bundled pretrained weights derive from datasets with their own terms - prefer the official general models for commercial output.
- **Wan 2.2** (Wan-Video/Wan2.2, Apache-2.0). Local text-to-video and image-to-video (the TI2V-5B variant fuses both); 720p @ 24fps achievable on a single high-end consumer GPU (e.g. RTX 4090). CONNECT for generating short synthetic b-roll / inserts when no footage exists. License flag: code AND released weights are Apache-2.0 = commercial use, modification, and redistribution permitted - clean for client work. Still apply normal content/likeness/IP diligence on generated material.
- **LTX-Video** (Lightricks/LTX-Video, Apache-2.0). Real-time DiT video generation (24fps at 768x512 faster than playback); strong for fast iterative text/image-to-video b-roll. CONNECT. License flag: the repository CODE is Apache-2.0; VERIFY the specific model-weights license per release before commercial use - some Lightricks model checkpoints ship under a separate community/open-weights license rather than Apache, so confirm the weight file's LICENSE for any client deliverable.

Generation routing: text-to-image and ComfyUI pipelines stay owned by image-generator; this employee CONNECTS to Wan 2.2 / LTX-Video only for the video-generation step of b-roll, then brings the output back into the ffmpeg/Resolve finish. No duplicate image-gen install here.
