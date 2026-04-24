"""LTX-2.3 video generation via the Wan2GP API Bridge.

Calls the localhost FastAPI bridge (see machine-manager
`services/apps/wan2gp/scripts/api_bridge.py`) which wraps Wan2GP's in-process
`shared.api`. The bridge runs inside the wan2gp_cu13 conda env and holds a
single WanGPSession warm across calls.

OpenMontage never imports shared.api directly — it only speaks HTTP.
"""

from __future__ import annotations

import os
import time
from typing import Any

import requests

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    RetryPolicy,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)


_DEFAULT_MODEL = "ltx2_22B_distilled"  # 1.0 — stronger audio/lipsync than 1.1 per community
_DEFAULT_FPS = "24"
_DEFAULT_NUM_FRAMES = 97
_BRIDGE_URL = os.environ.get("WAN2GP_BRIDGE_URL", "http://127.0.0.1:8877").rstrip("/")
_HEALTH_TIMEOUT = 2.0
_JOB_TIMEOUT = float(os.environ.get("WAN2GP_BRIDGE_JOB_TIMEOUT", "1800"))  # 30 min default


def _build_settings(inputs: dict[str, Any]) -> dict[str, Any]:
    """Map OpenMontage inputs → Wan2GP settings dict."""
    width = int(inputs.get("width") or 768)
    height = int(inputs.get("height") or 512)
    model_type = str(inputs.get("model_variant") or _DEFAULT_MODEL)
    # Distilled requires dims divisible by 64; dev by 32.
    modulus = 64 if "distilled" in model_type else 32
    width -= width % modulus
    height -= height % modulus

    num_frames = int(inputs.get("num_frames") or _DEFAULT_NUM_FRAMES)
    if num_frames < 17:
        num_frames = 17
    if (num_frames - 1) % 8 != 0:
        num_frames = 17 + 8 * ((num_frames - 17 + 7) // 8)

    settings: dict[str, Any] = {
        "model_type": model_type,
        "prompt": str(inputs.get("prompt") or ""),
        "resolution": f"{width}x{height}",
        "video_length": num_frames,
        "force_fps": _DEFAULT_FPS,
        "seed": int(inputs.get("seed", -1)),
    }
    if "distilled" not in model_type:
        settings["num_inference_steps"] = int(inputs.get("num_inference_steps") or 30)
        settings["guidance_scale"] = float(inputs.get("guidance_scale") or 3.0)

    start_image = inputs.get("reference_image_path") or inputs.get("image_start")
    end_image = inputs.get("image_end")
    if start_image:
        settings["image_start"] = str(start_image)
    if end_image:
        settings["image_end"] = str(end_image)

    # Wan2GP requires image_prompt_type to tell the pipeline HOW the input image(s)
    # should condition generation. Without this, `image_start` is silently ignored
    # and the model falls back to T2V on the prompt alone. Values:
    #   "S"  = start frame only
    #   "E"  = end frame only
    #   "SE" = both start and end frames (keyframed I2V)
    # Caller may override via inputs["image_prompt_type"].
    explicit_type = inputs.get("image_prompt_type")
    if explicit_type:
        settings["image_prompt_type"] = str(explicit_type)
    elif start_image and end_image:
        settings["image_prompt_type"] = "SE"
    elif start_image:
        settings["image_prompt_type"] = "S"
    elif end_image:
        settings["image_prompt_type"] = "E"

    loras = inputs.get("activated_loras")
    if loras:
        settings["activated_loras"] = list(loras) if isinstance(loras, (list, tuple)) else [str(loras)]
        mults = inputs.get("loras_multipliers")
        if mults is not None:
            settings["loras_multipliers"] = str(mults)

    # Pass-through for any Wan2GP settings the tool doesn't model explicitly.
    # Common uses: audio_guidance_scale, alt_guidance_scale, alt_scale,
    # perturbation_switch, perturbation_layers, audio_prompt_path for audio
    # conditioning; sliding_window_size / sliding_window_overlap tuning. Caller
    # is responsible for valid keys — these go straight into Wan2GP.
    extras = inputs.get("extra_settings")
    if isinstance(extras, dict):
        for k, v in extras.items():
            if v is not None:
                settings[k] = v
    return settings


def _bridge_up() -> bool:
    try:
        r = requests.get(f"{_BRIDGE_URL}/health", timeout=_HEALTH_TIMEOUT)
        return r.status_code == 200
    except Exception:
        return False


class LTXVideoWan2GP(BaseTool):
    name = "ltx_video_wan2gp"
    version = "0.2.0"
    tier = ToolTier.GENERATE
    capability = "video_generation"
    provider = "wan2gp-bridge"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.LOCAL_GPU

    install_instructions = (
        "Start the Wan2GP bridge: "
        "services/apps/wan2gp/scripts/start_bridge.cmd "
        "(activates wan2gp_cu13 conda env, serves on http://127.0.0.1:8877). "
        "Override with WAN2GP_BRIDGE_URL env var."
    )
    fallback = "ltx_video_local"
    fallback_tools = ["ltx_video_local", "ltx_video_modal", "wan_video", "image_selector"]
    agent_skills = ["ltx2", "ltx2-wan2gp", "wan2gp"]

    capabilities = ["text_to_video", "image_to_video"]
    supports = {
        "reference_image": True,
        "offline": True,
        "native_audio": True,  # LTX-2.3 generates synchronized audio
        "local_gpu": True,
    }
    best_for = [
        "LTX-2.3 generation through Wan2GP with a warm session across OpenMontage calls",
        "native video+audio generation in a single pass",
        "IC-LoRA / VACE workflows already tuned in Wan2GP",
    ]
    not_good_for = ["CPU-only machines", "setups without the wan2gp_cu13 conda env"]
    provider_matrix = {
        "ltx2_22B_distilled": {"tool": "ltx_video_wan2gp", "name": "LTX-2.3 Distilled 1.0", "mode": "wan2gp-bridge"},
        "ltx2_22B_distilled_1_1": {"tool": "ltx_video_wan2gp", "name": "LTX-2.3 Distilled 1.1", "mode": "wan2gp-bridge"},
        "ltx2_22B": {"tool": "ltx_video_wan2gp", "name": "LTX-2.3 Dev", "mode": "wan2gp-bridge"},
    }

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string"},
            "operation": {"type": "string", "enum": ["text_to_video", "image_to_video"], "default": "text_to_video"},
            "model_variant": {
                "type": "string",
                "enum": ["ltx2_22B_distilled", "ltx2_22B_distilled_1_1", "ltx2_22B"],
                "default": "ltx2_22B_distilled",
            },
            "reference_image_path": {"type": "string"},
            "image_start": {"type": "string"},
            "image_end": {"type": "string"},
            "image_prompt_type": {
                "type": "string",
                "enum": ["S", "E", "SE"],
                "description": "Wan2GP image-conditioning mode. Auto-derived from image_start/image_end if omitted.",
            },
            "width": {"type": "integer", "default": 768},
            "height": {"type": "integer", "default": 512},
            "num_frames": {"type": "integer", "default": 97},
            "num_inference_steps": {"type": "integer"},
            "guidance_scale": {"type": "number"},
            "seed": {"type": "integer", "default": -1},
            "activated_loras": {"type": "array", "items": {"type": "string"}},
            "loras_multipliers": {"type": "string"},
            "extra_settings": {
                "type": "object",
                "description": "Wan2GP settings pass-through for fields not explicitly modeled here (audio_guidance_scale, alt_guidance_scale, audio_prompt_path, perturbation_*, etc.). Keys merge directly into the Wan2GP settings dict.",
                "additionalProperties": True,
            },
        },
    }

    resource_profile = ResourceProfile(cpu_cores=2, ram_mb=2000, vram_mb=0, disk_mb=4000, network_required=True)
    retry_policy = RetryPolicy(max_retries=1)
    idempotency_key_fields = ["prompt", "model_variant", "operation", "seed", "image_start", "image_end"]
    side_effects = ["writes video file into Wan2GP's outputs/ folder"]
    user_visible_verification = ["Watch generated clip for motion coherence and artifacts"]

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE if _bridge_up() else ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, object]) -> float:
        return 0.0

    def estimate_runtime(self, inputs: dict[str, object]) -> float:
        num_frames = int(inputs.get("num_frames") or _DEFAULT_NUM_FRAMES) if isinstance(inputs, dict) else _DEFAULT_NUM_FRAMES
        return max(48.0, num_frames * 0.9)

    def execute(self, inputs: dict[str, object]) -> ToolResult:
        if not _bridge_up():
            return ToolResult(
                success=False,
                error=f"Wan2GP bridge not reachable at {_BRIDGE_URL}. {self.install_instructions}",
            )

        settings = _build_settings(dict(inputs))
        start = time.time()
        try:
            r = requests.post(
                f"{_BRIDGE_URL}/submit_task",
                json={"settings": settings},
                timeout=_JOB_TIMEOUT,
            )
        except Exception as exc:
            return ToolResult(success=False, error=f"Bridge request failed: {exc}")

        duration = round(time.time() - start, 2)
        if r.status_code != 200:
            return ToolResult(
                success=False,
                error=f"Bridge returned {r.status_code}: {r.text[:500]}",
                duration_seconds=duration,
            )

        try:
            body = r.json()
        except Exception as exc:
            return ToolResult(success=False, error=f"Bridge response not JSON: {exc}", duration_seconds=duration)

        if not body.get("success"):
            errs = "; ".join(body.get("errors") or []) or "unknown failure"
            return ToolResult(success=False, error=f"Wan2GP gen failed: {errs}", duration_seconds=duration)

        return ToolResult(
            success=True,
            artifacts=list(body.get("artifacts") or []),
            data={"settings": settings, "bridge_url": _BRIDGE_URL, "total_tasks": body.get("total_tasks", 1)},
            duration_seconds=duration,
            seed=settings.get("seed") if isinstance(settings.get("seed"), int) else None,
            model=settings["model_type"],
        )
