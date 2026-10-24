"""US-11 — effective settings and prompt templates (DB overrides on top of code defaults)."""

from __future__ import annotations

from app.domain import prompts

MODEL_PRESETS = [
    "anthropic/claude-opus-5.5",
    "openai/gpt-6-luna",
    "openai/gpt-6-sol",
    "openai/gpt-6-astra",
]

DEFAULT_SETTINGS = {
    "model": MODEL_PRESETS[0],
    "temperature": 0.3,
    "grounding_retries": 2,
    "chat_color": "#a855f7",  # US-10: the one AI-trace color for chat evidence
    "map_color": "#f97316",   # US-07: highlight color for the selected node's quotes
}


def effective_settings(repo, default_model: str | None = None) -> dict:
    s = dict(DEFAULT_SETTINGS)
    if default_model:
        s["model"] = default_model
    s.update(repo.settings())
    return s


def validate_settings(values: dict) -> dict:
    out = {}
    if "model" in values:
        model = str(values["model"]).strip()
        if not model or " " in model:
            raise ValueError("model must be an OpenRouter model id, e.g. anthropic/claude-opus-5.5")
        out["model"] = model
    if "temperature" in values:
        t = float(values["temperature"])
        if not 0 <= t <= 2:
            raise ValueError("temperature must be within 0..2")
        out["temperature"] = t
    if "grounding_retries" in values:
        r = int(values["grounding_retries"])
        if not 0 <= r <= 5:
            raise ValueError("grounding_retries must be within 0..5")
        out["grounding_retries"] = r
    for key in ("chat_color", "map_color"):
        if key in values:
            v = str(values[key])
            if not (len(v) == 7 and v.startswith("#")):
                raise ValueError(f"{key} must be a #rrggbb color")
            out[key] = v
    return out


def all_prompts(repo) -> list[dict]:
    overrides = repo.prompt_overrides()
    out = []
    for key, d in prompts.DEFAULTS.items():
        o = overrides.get(key)
        out.append({
            "key": key, "name": d["name"], "description": d["description"],
            "required": list(prompts.REQUIRED[key]),
            "template": o["template"] if o else d["template"],
            "is_default": o is None, "updated_at": o["updated_at"] if o else None,
        })
    return out


def prompt(repo, key: str) -> str:
    o = repo.prompt_overrides().get(key)
    return o["template"] if o else prompts.DEFAULTS[key]["template"]
