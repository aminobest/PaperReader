"""CR-02 — runtime configuration from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    data_dir: str
    openrouter_api_key: str
    openrouter_base_url: str
    default_model: str
    cookie_secure: bool
    llm_timeout: float


def load_config() -> Config:
    return Config(
        data_dir=os.environ.get("DATA_DIR", "/data"),
        openrouter_api_key=os.environ.get("OPENROUTER_API_KEY", ""),
        openrouter_base_url=os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        default_model=os.environ.get("DEFAULT_MODEL", "anthropic/claude-opus-5.5"),
        cookie_secure=os.environ.get("COOKIE_SECURE", "0") == "1",
        llm_timeout=float(os.environ.get("LLM_TIMEOUT", "600")),
    )
