# DaVinci Resolve MCP - color + Fairlight audio + timeline (CONNECT)

samuelgursky/davinci-resolve-mcp (MIT, ~485 stars). **100% Scripting API coverage** (324/324 methods, 319 live-tested against Resolve 19.1.3 Studio). This is the professional spine for color grading, audio (Fairlight), timeline assembly, and rendering - everything FFmpeg can't do well.

## Requirements (host)
- **DaVinci Resolve Studio 18.5+** (the FREE edition does NOT support external scripting). ~$295 one-time.
- Python 3.10-3.12. Resolve running with Preferences > General > "External scripting using" = **Local**.
- Install: clone the repo, run `python install.py` (universal installer auto-detects platform, finds Resolve, makes a venv, configures the MCP client).

## Two server modes
- **Compound (default)** - ~27 tools that group the 324 API methods by action parameter (lean LLM context). Use this.
- **Full** - 342 granular tools (one per method) for power users.

## What it controls (by API class)
- **Resolve / pages** - switch Edit/Color/Fairlight/Deliver pages, layout presets, render/burn-in presets.
- **ProjectManager / Project** - project CRUD, render pipeline, settings, LUTs, color groups.
- **MediaPool / MediaStorage** - import media, create timelines, append clips, AAF/EDL/XML import.
- **Timeline** - tracks, markers, items, EDL/XML/AAF **export**, generators, titles, stills; `DetectSceneCuts()`, `CreateSubtitlesFromAudio()`.
- **TimelineItem** - transform/crop/composite/retime, keyframes (Linear/Bezier/Ease), CDL, versions, takes, Fusion comps; `Stabilize()`, `SmartReframe()`, Magic Mask.
- **Color: Graph / ColorGroup / Gallery** - node ops, `SetLUT`/`GetLUT`, `ApplyGradeFromDRX`, `ResetAllGrades`, color groups (shared grades), gallery stills (grab + export with companion .drx grade).
- **Fairlight audio** - track ops, audio item volume/pan/sync-offset, insert audio at playhead.

## When to use Resolve MCP vs FFmpeg
- **Resolve:** color grading (node graph + scopes), Fairlight mixing, multi-track timeline assembly, EDL/XML round-trip, stills/grades, scene-cut detection in a real timeline, deliver presets.
- **FFmpeg (existing):** headless/batch encode, lossless trim/concat, format/codec conversion, quick filters, server-side render with no GUI.

## Common tasks (natural language)
- "Create a timeline 'Assembly Cut' and append all media-pool clips."
- "Switch to Color, grab a still, export it with the .drx grade."
- "Set up a ProRes 422 HQ render and start it."
- "Detect scene cuts on the current timeline."
- "Create subtitles from audio."

## Security (README)
- `quit_app`/`restart_app` can terminate Resolve - require user confirmation. Destructive timeline/preset tools should not be blanket auto-approved.

## Shared note
Resolve MCP + FFmpeg are the video-editor's owned audio/video tools (cluster-shared layer). voice-audio-producer hands clean generated/isolated audio to this employee for mix-into-timeline.
