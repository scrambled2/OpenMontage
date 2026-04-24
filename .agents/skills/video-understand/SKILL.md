---
name: video-understand
description: |
  Understand video content two ways: (A) native Gemini video watching via Google GenAI — model watches clip as MOTION and answers targeted questions; (B) local ffmpeg frame extraction + Whisper transcription.
  Use when: (1) Evaluating whether a generated clip has cuts, camera moves, or motion defects — use Gemini; (2) Understanding content of stock/reference video — either; (3) Transcribing audio — use Whisper path; (4) No network / no API key — use Whisper path; (5) Judging lip-sync quality, pacing, shot coherence — use Gemini.
---

# video-understand

Two complementary paths — pick based on what you need to answer.

## Path A: Native video understanding via Gemini (recommended for motion/shot judgement)

Gemini 3.x models natively ingest video. The model watches the clip as actual motion — it can answer "does the camera push in?", "is there a cut mid-shot?", "does the lip-sync land?", "how many people are in frame?" The prior Whisper-based skill could only sample frames and transcribe audio, which misses all of those questions.

### Script

`scripts/watch_with_gemini.py` — send a video file + a targeted question, get the model's natural-language answer.

```bash
# Default: flash-lite (cheapest, $0.25/$1.50 per M tokens, plenty for shot-level checks)
python watch_with_gemini.py clip.mp4 "Does this shot contain a cut or scene change?"

# Same but use regular Flash (4x cheaper than Pro, more nuance than Lite)
python watch_with_gemini.py clip.mp4 "Describe the camera movement from start to end." --model flash

# Heavy reasoning only — Pro is expensive
python watch_with_gemini.py clip.mp4 "Compare motion continuity vs prompt intent." --model pro

# Full model id also accepted
python watch_with_gemini.py clip.mp4 "..." --model gemini-3.1-pro-preview
```

### Model choice (verified 2026-04)

| Alias | Full model ID | $/M in | $/M out | Use |
|---|---|---|---|---|
| `flash-lite` (default) | `gemini-3.1-flash-lite-preview` | 0.25 | 1.50 | **Most shot checks.** Fast, cheap, reliable for "is there a cut / does camera move / is subject framed as expected" |
| `flash` | `gemini-3-flash-preview` | 0.50 | 3.00 | Workhorse — more nuance for subtle motion judgment |
| `pro` | `gemini-3.1-pro-preview` | 2.00 | 12.00 | Multi-clip compare, cinematographic reasoning |

Rough cost per ~7s HD clip: Flash Lite ~$0.01–0.03, Flash ~$0.02–0.05, Pro ~$0.10–0.25. **Default to Flash Lite** unless the question genuinely needs deeper reasoning.

### API key

Uses native Google GenAI (not OpenRouter). Reads `GOOGLE_API_KEY` or `GEMINI_API_KEY` from the nearest `.env`.

### Verified working output (2026-04-24 on THEMACHINE)

Shot ran against `shot04_hero_photo_v2.mp4`:
> *"The video does not feature a camera push-in. Instead, it maintains a static shot throughout the entire 5-second duration. There are no hard cuts or mid-shot scene changes; the visual elements remain consistent from beginning to end."*

Shot ran against `shot07_rooftop_run_v2.mp4`:
> *"The video features a single camera movement: a smooth, horizontal tracking shot that follows the subject from right to left... There is only one person in the shot, and there are no hard cuts."*

Both produced real, actionable motion-level feedback. The shot04 response revealed the generated clip did NOT honor the prompted push-in — the kind of fact invisible in a 3-frame still grid.

### Constraints

- **Max file size**: use File API upload (which this script does). Files > ~100MB or reused across requests should go through File API; small files could go inline but File API is cleaner.
- **Accepted formats**: `mp4, mpeg, mov, webm`, plus YouTube URLs (not implemented in this script — use `understand_video.py` YouTube path + download if needed).
- **Upload latency**: ~2-5s to upload + processing time. Full round trip for a ~15MB 7s clip is ~20-40s.

### Validation primitive — `scripts/validate_clip.py`

Companion to `watch_with_gemini.py`. Same Gemini backend, but returns **structured JSON** for programmatic use: pass/fail per criterion, a one-line verdict, and concrete fix suggestions when something fails. Use this anywhere in any pipeline where a generation step has stated requirements you want verified before proceeding.

```bash
python validate_clip.py clip.mp4 \
    -c "The camera performs a continuous forward push-in" \
    -c "No hard cuts or scene changes" \
    -c "Dusk lighting with an alien ship visible"
```

```python
from validate_clip import validate
result = validate("shot04.mp4", criteria=[
    "camera gently pushes forward toward the subject's face",
    "one continuous shot — no cuts",
    "a candle flickers in the scene",
])
if not result["overall_pass"]:
    for fix in result["fix_suggestions"]:
        print(fix)
```

Output shape: `{overall_pass, summary, criteria_results: [{criterion, pass, finding}], fix_suggestions, model, clip}`.

**When to reach for it.** Any pipeline step that produces a video clip with stated intent — post-generation check before accepting, gating an auto-retry loop, or batch audit of a folder of renders. Cost is ~$0.02 per 7s clip at flash-lite, cheap enough to run on every generation.

**Design notes (how to use it well).**
- Write criteria as *observable facts*, not judgments. "The camera moves left-to-right" is observable. "The shot feels tense" is not — Gemini will fabricate.
- 2–4 criteria per clip. More fragments the verdict; fewer misses things.
- The returned `fix_suggestions` are hints, not commands. An agent with project context (script, adjacent shots, creative intent) makes the actual decision to retry/re-scope/accept. Don't burn blind retries.
- Clip-in-isolation validation is the cheapest, weakest scope. Shot-in-sequence and sequence-level checks require assembling material first and asking richer questions via `watch_with_gemini.py`.

---

## Path B: Local frame extraction + Whisper (offline, no API)

Understand video content locally using ffmpeg for frame extraction and Whisper for transcription. Fully offline, no API keys required.

## Prerequisites

- `ffmpeg` + `ffprobe` (required): `brew install ffmpeg`
- `openai-whisper` (optional, for transcription): `pip install openai-whisper`

## Commands

```bash
# Scene detection + transcribe (default)
python3 skills/video-understand/scripts/understand_video.py video.mp4

# Keyframe extraction
python3 skills/video-understand/scripts/understand_video.py video.mp4 -m keyframe

# Regular interval extraction
python3 skills/video-understand/scripts/understand_video.py video.mp4 -m interval

# Limit frames extracted
python3 skills/video-understand/scripts/understand_video.py video.mp4 --max-frames 10

# Use a larger Whisper model
python3 skills/video-understand/scripts/understand_video.py video.mp4 --whisper-model small

# Frames only, skip transcription
python3 skills/video-understand/scripts/understand_video.py video.mp4 --no-transcribe

# Quiet mode (JSON only, no progress)
python3 skills/video-understand/scripts/understand_video.py video.mp4 -q

# Output to file
python3 skills/video-understand/scripts/understand_video.py video.mp4 -o result.json
```

## CLI Options

| Flag | Description |
|------|-------------|
| `video` | Input video file (positional, required) |
| `-m, --mode` | Extraction mode: `scene` (default), `keyframe`, `interval` |
| `--max-frames` | Maximum frames to keep (default: 20) |
| `--whisper-model` | Whisper model size: tiny, base, small, medium, large (default: base) |
| `--no-transcribe` | Skip audio transcription, extract frames only |
| `-o, --output` | Write result JSON to file instead of stdout |
| `-q, --quiet` | Suppress progress messages, output only JSON |

## Extraction Modes

| Mode | How it works | Best for |
|------|-------------|----------|
| `scene` | Detects scene changes via ffmpeg `select='gt(scene,0.3)'` | Most videos, varied content |
| `keyframe` | Extracts I-frames (codec keyframes) | Encoded video with natural keyframe placement |
| `interval` | Evenly spaced frames based on duration and max-frames | Fixed sampling, predictable output |

If `scene` mode detects no scene changes, it automatically falls back to `interval` mode.

## Output

The script outputs JSON to stdout (or file with `-o`). See `references/output-format.md` for the full schema.

```json
{
  "video": "video.mp4",
  "duration": 18.076,
  "resolution": {"width": 1224, "height": 1080},
  "mode": "scene",
  "frames": [
    {"path": "/abs/path/frame_0001.jpg", "timestamp": 0.0, "timestamp_formatted": "00:00"}
  ],
  "frame_count": 12,
  "transcript": [
    {"start": 0.0, "end": 2.5, "text": "Hello and welcome..."}
  ],
  "text": "Full transcript...",
  "note": "Use the Read tool to view frame images for visual understanding."
}
```

Use the Read tool on frame image paths to visually inspect extracted frames.

## References

- `references/output-format.md` -- Full JSON output schema documentation
