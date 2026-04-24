#!/usr/bin/env python3
"""Validation gate — ask Gemini to judge a generated clip against a list of criteria.

Returns structured JSON so callers (gen_video_clips.py, asset-director, etc.) can
branch: overall_pass → accept; overall_pass=false → retry with seed/prompt adjustment.

This is the core of the iterative refinement loop described in AGENT_GUIDE.md
"Generation + Validation Gate" section. Default model is gemini-3.1-flash-lite-preview
(cheapest verified Gemini with native video input, April 2026).

Usage (CLI):
    python validate_clip.py clip.mp4 \
        --criterion "The camera performs a continuous forward push" \
        --criterion "No hard cuts or scene changes" \
        --criterion "Dusk lighting palette with alien ship visible"

Usage (library):
    from validate_clip import validate
    result = validate(
        clip_path="shot04.mp4",
        criteria=[
            "The camera gently pushes forward toward the subject's face.",
            "The clip is one continuous shot — no cuts.",
            "A candle flickers in the scene.",
        ],
    )
    if not result["overall_pass"]:
        print(result["summary"])
        for fix in result["fix_suggestions"]:
            print(f"  fix: {fix}")
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path


MODEL_ALIASES = {
    "flash-lite": "gemini-3.1-flash-lite-preview",
    "lite":       "gemini-3.1-flash-lite-preview",
    "flash":      "gemini-3-flash-preview",
    "pro":        "gemini-3.1-pro-preview",
}


def _load_env():
    try:
        from dotenv import load_dotenv
        here = Path(__file__).resolve()
        for candidate in [here.parent, *here.parents]:
            env = candidate / ".env"
            if env.exists():
                load_dotenv(env)
                break
    except ImportError:
        pass


def validate(
    clip_path: str | Path,
    criteria: list[str],
    model_alias: str = "flash-lite",
    verbose: bool = False,
) -> dict:
    """Ask Gemini to judge a clip against ordered criteria, return structured JSON verdict.

    Return shape:
        {
            "overall_pass": bool,
            "summary": str,                 # 1-2 sentence plain-English verdict
            "criteria_results": [
                {"criterion": str, "pass": bool, "finding": str},
                ...
            ],
            "fix_suggestions": [str, ...],  # concrete changes to try next gen
            "model": str,
            "clip": str,
        }
    """
    _load_env()
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Set GOOGLE_API_KEY or GEMINI_API_KEY in .env")

    from google import genai
    from google.genai import types

    clip = Path(clip_path).resolve()
    if not clip.exists():
        raise FileNotFoundError(clip)

    model_id = MODEL_ALIASES.get(model_alias, model_alias)
    client = genai.Client(api_key=api_key)

    if verbose:
        print(f"[validate] uploading {clip.name} ...", file=sys.stderr)

    file_ref = client.files.upload(file=str(clip))
    for _ in range(60):
        state = str(file_ref.state).split(".")[-1]
        if state == "ACTIVE":
            break
        if state == "FAILED":
            raise RuntimeError(f"File upload FAILED")
        time.sleep(1)
        file_ref = client.files.get(name=file_ref.name)

    numbered = "\n".join(f"  {i+1}. {c}" for i, c in enumerate(criteria))
    prompt = (
        "You are a strict video-production validator. Watch the attached clip as "
        "motion, not as stills. Evaluate it against each of the following criteria "
        "independently. Be literal and honest — a marginal pass is a FAIL. "
        "If a camera move is described but you don't see one, that's a fail. If the "
        "clip contains a cut and the criterion says no cuts, that's a fail.\n\n"
        f"CRITERIA:\n{numbered}\n\n"
        "Respond with JSON ONLY, matching this exact schema:\n"
        "{\n"
        '  "overall_pass": true|false,\n'
        '  "summary": "1-2 sentence plain-English verdict",\n'
        '  "criteria_results": [\n'
        '    {"criterion": "<verbatim criterion text>", "pass": true|false, "finding": "<what you observed>"}\n'
        "  ],\n"
        '  "fix_suggestions": ["<concrete change to prompt/seed/params to fix each failed criterion>"]\n'
        "}\n\n"
        "overall_pass must be true ONLY if every criterion passes. No markdown, no prose outside JSON."
    )

    if verbose:
        print(f"[validate] asking {model_id!r} ...", file=sys.stderr)

    resp = client.models.generate_content(
        model=model_id,
        contents=[file_ref, prompt],
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )

    # Cleanup
    try:
        client.files.delete(name=file_ref.name)
    except Exception:
        pass

    raw = resp.text or ""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # Fallback: attempt to extract JSON block
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            data = json.loads(raw[start:end+1])
        else:
            raise RuntimeError(f"Gemini returned non-JSON: {raw[:500]}")

    data.setdefault("model", model_id)
    data.setdefault("clip", str(clip))
    return data


def main():
    ap = argparse.ArgumentParser(description="Validate a generated clip against criteria using Gemini.")
    ap.add_argument("clip", help="Path to video file")
    ap.add_argument("--criterion", "-c", action="append", required=True,
                    help="A criterion to evaluate. Pass multiple times for multiple criteria.")
    ap.add_argument("--model", default="flash-lite",
                    help="flash-lite (default) | flash | pro | <full model id>")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    result = validate(args.clip, args.criterion, model_alias=args.model, verbose=args.verbose)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result.get("overall_pass") else 1)


if __name__ == "__main__":
    main()
