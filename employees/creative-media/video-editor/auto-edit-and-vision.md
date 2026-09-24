# Auto-edit, shot detection, word timestamps, video vision

## WhisperX - word-level timestamps + diarization (ABSORB)
m-bain/whisperX (~22k stars, BSD). 70x realtime (large-v2), faster-whisper backend, <8GB GPU. Adds what plain Whisper lacks: accurate WORD-level timestamps (wav2vec2 forced alignment) + speaker diarization (pyannote).
- CLI: `whisperx audio.wav --model large-v2 --diarize --highlight_words True` (set `--min_speakers`/`--max_speakers` if known). CPU/Mac: `--compute_type int8 --device cpu`.
- Diarization needs a HuggingFace token + accepting the pyannote model agreement.
- Use for: content-aware cuts on word boundaries, frame-accurate captions, "cut to where they say X", per-speaker editing.

## Auto-Editor - silence/motion auto-cut (ABSORB)
WyattBlue/auto-editor (~4.4k stars, Public Domain). Cuts "dead space" (silence/motionlessness) automatically - the boring first pass.
- Basic: `auto-editor video.mp4` (defaults to `--edit audio:threshold=4%`).
- Pace: `--margin 0.2s` (pad around kept sections), `--margin 0.3s,1.5s` (asymmetric).
- Methods: `--edit motion:threshold=0.02`, `--edit audio:-19dB`, combine: `--edit "(or audio:0.03 motion:0.06)"`.
- Manual: `--cut-out 0,30sec`, `--add-in 30,40sec`.
- **Exports an editable timeline, doesn't force a render:** `--export premiere | resolve | final-cut-pro | shotcut | kdenlive`. So the rough cut lands IN Resolve/Premiere for finishing. Also reads FCP7 XML to render.

## PySceneDetect - shot/scene detection (ABSORB)
PySceneDetect (~4.8k stars, BSD). Detects shot boundaries - the "watching" primitive.
- `scenedetect -i video.mp4 detect-adaptive split-video` (already in this employee's FFmpeg scene-split section; this is the same tool, also used for analysis/structure).
- Use for: shot lists, structure analysis, choosing cut points, b-roll insertion windows.

## Video vision (METHODOLOGY/CONNECT)
To "understand" a video, combine:
1. **WhisperX** → what's said + word timestamps (audio layer).
2. **PySceneDetect** → shot boundaries (structure layer).
3. **Visual description** → run a vision-LLM on representative frames (one per shot) OR use the **Twelve Labs** video-understanding API for native temporal video search/description.
Output: a shot-by-shot map (timestamp, transcript, visual description) that drives editing decisions and auto-shorts selection.
