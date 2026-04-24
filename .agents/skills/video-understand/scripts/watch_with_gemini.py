#!/usr/bin/env python3
"""Native video understanding via Google Gemini 3.x (Flash-Lite / Flash / Pro).

Unlike understand_video.py (which samples frames + transcribes), this script
sends the actual MP4 to Gemini's File API and asks a targeted question. The
model watches the clip as motion, not as stills, so it can answer:

  - "Does this clip contain a mid-shot cut?"
  - "Does the camera push in as prompted?"
  - "Is the lip-sync believable?"
  - "How many cuts happen in this 10-second clip?"

Model pricing on OpenRouter (April 2026, verified):
  gemini-3.1-flash-lite-preview   $0.25 / $1.50  per M tokens  DEFAULT
  gemini-3-flash-preview          $0.50 / $3.00  per M tokens
  gemini-3.1-pro-preview          $2.00 / $12.00 per M tokens

Usage:
  python watch_with_gemini.py CLIP.mp4 "What happens in this video?"
  python watch_with_gemini.py CLIP.mp4 "Is there a cut?" --model flash
  python watch_with_gemini.py CLIP.mp4 -q "Describe the camera move" --model pro
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path


MODEL_ALIASES = {
    "flash-lite": "gemini-3.1-flash-lite-preview",  # cheapest, default
    "lite":       "gemini-3.1-flash-lite-preview",
    "flash":      "gemini-3-flash-preview",
    "pro":        "gemini-3.1-pro-preview",
}


def _load_env():
    """Load OPENROUTER or GOOGLE_API_KEY from .env; prefer GOOGLE_API_KEY for native access."""
    try:
        from dotenv import load_dotenv
        # Try project-local .env first, then walk upward
        here = Path(__file__).resolve()
        for candidate in [here.parent, *here.parents]:
            env = candidate / ".env"
            if env.exists():
                load_dotenv(env)
                break
    except ImportError:
        pass


def watch(video_path: str, question: str, model_alias: str = "flash-lite",
          verbose: bool = True) -> str:
    """Send video + question to Gemini, return the model's text response."""
    _load_env()

    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "No API key found. Set GOOGLE_API_KEY or GEMINI_API_KEY.\n"
            "(Alternatively, use OpenRouter — see README. This script uses native Google API for simplicity.)"
        )

    from google import genai
    from google.genai import types

    model_id = MODEL_ALIASES.get(model_alias, model_alias)
    client = genai.Client(api_key=api_key)

    video = Path(video_path).resolve()
    if not video.exists():
        raise FileNotFoundError(video)

    size_mb = video.stat().st_size / (1024 * 1024)
    if verbose:
        print(f"[watch] uploading {video.name} ({size_mb:.1f} MB) to Gemini File API...", file=sys.stderr)

    # Upload via File API (required for video over ~20MB anyway, and recommended across the board)
    file_ref = client.files.upload(file=str(video))

    # Poll for ACTIVE (File API processes the upload async — video analysis is blocked until then)
    for _ in range(60):
        state = str(file_ref.state).split(".")[-1]
        if state == "ACTIVE":
            break
        if state == "FAILED":
            raise RuntimeError(f"File upload failed state={file_ref.state}")
        time.sleep(1)
        file_ref = client.files.get(name=file_ref.name)

    if verbose:
        print(f"[watch] file ready. asking {model_id!r}...", file=sys.stderr)

    resp = client.models.generate_content(
        model=model_id,
        contents=[file_ref, question],
    )

    # Cleanup — delete uploaded file (we're done with it)
    try:
        client.files.delete(name=file_ref.name)
    except Exception:
        pass

    return resp.text or ""


def main():
    ap = argparse.ArgumentParser(description="Ask Gemini to watch a video and answer a targeted question.")
    ap.add_argument("video", help="Path to video file (mp4/mov/webm/etc.)")
    ap.add_argument("question", help="What to ask Gemini about the video")
    ap.add_argument("--model", default="flash-lite",
                    help="flash-lite (default, cheapest) | flash | pro | <full model id>")
    ap.add_argument("-q", "--quiet", action="store_true", help="Suppress progress messages")
    args = ap.parse_args()

    answer = watch(args.video, args.question, model_alias=args.model, verbose=not args.quiet)
    print(answer)


if __name__ == "__main__":
    main()
