# Audio post recipes + the auto-Shorts pipeline

## Audio post (free baseline → commercial quality)
1. **FFmpeg baseline (free):**
   - Denoise: `-af arnndn=m=model.rnnn` (RNNoise) or `anlmdn` (already in SKILL).
   - Loudness (EBU R128): `-af loudnorm=I=-16:TP=-1.5:LRA=11` (already in SKILL - -14 YouTube, -16 podcast, -23 broadcast).
2. **Resolve Fairlight** for mixing, ducking, EQ in a real timeline.
3. **ElevenLabs Voice Isolator** (CONNECT, shared from voice-audio-producer) - extract clean dialogue from noisy/echoey source. video-editor BORROWS this; it is owned by voice-audio-producer.
4. **Auphonic** (CONNECT, commercial) - automated leveling/loudness/noise/hum for podcast-grade output when it must be hands-off and high quality.

Order: isolate/denoise → EQ → compress → loudness-normalize → mix. Bad audio kills good video.

## Auto-Shorts pipeline (METHODOLOGY - BUILD, OSS is thin)
Turn a long video into vertical short clips automatically:
1. **Transcribe** with WhisperX (word-level timestamps + optional diarization).
2. **Detect shots** with PySceneDetect (structure) and find silence/energy with Auto-Editor.
3. **Pick highlights** with an LLM over the transcript (hook-worthy 15-60s segments; score by self-contained payoff).
4. **Reframe to 9:16** - face/subject-tracked crop (OpenCV face track + crop, or Resolve SmartReframe) so the speaker stays in frame.
5. **Burn captions** - styled word-by-word captions from WhisperX timestamps via MoviePy (or Resolve subtitles).
6. **Export** per platform (1080x1920, H.264, 6-10 Mbps - see SKILL export table).
Commercial alternative: **OpusClip** (hands-off, paid) - use when speed > control.

## Cross-references
- voice-audio-producer owns ElevenLabs (voice-isolator borrowed here, TTS/SFX/music generated there).
- content-marketer (hook/script), social-media-manager (cross-platform repurpose + posting).
