# OpenMontage - Copilot Agent Instructions

> **Start here:** See [`AGENT_GUIDE.md`](AGENT_GUIDE.md) — the complete operating guide and agent contract.
> **Project context:** See [`PROJECT_CONTEXT.md`](PROJECT_CONTEXT.md) for architecture, key files, and conventions.

> **Host note (THEMACHINE only):** a Wan2GP HTTP bridge at `http://127.0.0.1:8877` exposes LTX-2.3 via the `ltx_video_wan2gp` tool. Prefer it over `ltx_video_local`. See the "Wan2GP LTX-2.3 Bridge" section in `AGENT_GUIDE.md` and "Local-Host Integrations" in `PROJECT_CONTEXT.md`.

## HARD RULE: Artifact Versioning — NEVER OVERWRITE

Every generated artifact gets a version suffix. Format: `<base>_v<N>.<ext>`. Prior versions stay on disk; they are never overwritten or deleted mid-project. Applies to character refs, start frames, video clips, audio, final renders, and pipeline decision JSONs. Excludes only `work/`/`tmp/` scratch and datetime-stamped logs. Full spec in AGENT_GUIDE.md "Artifact Versioning" section.


## HARD RULE: Never Rely on Training Data for Model Names, Versions, or Capabilities

Your training data is stale by months to years. For any claim about an AI model name, version number, pricing, API field, or "which model is current," verify via (1) the tool registry, (2) the relevant Layer 3 skill in `~/.claude/skills/`, (3) a live `WebSearch`, or (4) metadata from a known-good generation on this machine. Do NOT cite specific model versions from memory. If you catch yourself naming a model you havent verified in this session, STOP and search first. Full spec in AGENT_GUIDE.md "Never Rely on Training Data" section.
