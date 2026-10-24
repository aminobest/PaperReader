"""CR-01 AT-C01.2 — architecture guard: dependency rule enforced by tests, not by review."""

import re
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[2] / "backend" / "app"
IMPORT = re.compile(r"^\s*(?:from|import)\s+([\w.]+)", re.M)


def imports(path: Path) -> list[str]:
    return IMPORT.findall(path.read_text())


DOMAIN = sorted((APP / "domain").glob("*.py"))
APPLICATION = sorted((APP / "application").glob("*.py"))
API = sorted((APP / "api").glob("*.py"))


@pytest.mark.parametrize("path", DOMAIN, ids=lambda p: p.name)
def test_domain_is_pure(path):
    """AT-C01.2 — domain imports only stdlib and other domain modules."""
    bad = [m for m in imports(path) if m.startswith(("app.", "fastapi", "httpx", "sqlite3", "fitz", "pydantic"))
           and not m.startswith("app.domain")]
    assert not bad, f"{path.name} must stay pure: {bad}"


@pytest.mark.parametrize("path", APPLICATION, ids=lambda p: p.name)
def test_application_does_no_io_and_ignores_the_web_layer(path):
    """AT-C01.2 — use cases never import the API layer, infrastructure, or I/O libraries."""
    bad = [m for m in imports(path) if m.startswith(("app.api", "app.infrastructure", "fastapi", "httpx", "sqlite3", "fitz"))]
    assert not bad, f"{path.name}: {bad}"


@pytest.mark.parametrize("path", API, ids=lambda p: p.name)
def test_api_never_calls_the_llm_directly(path):
    """AT-C01.2 — all LLM calls go through application.llm_gateway (so they are logged, US-11)."""
    bad = [m for m in imports(path) if m.startswith(("app.infrastructure.llm", "httpx"))]
    assert not bad, f"{path.name}: {bad}"


def test_prompts_live_only_in_domain_prompts():
    """AT-C01.2 — no hard-coded prompt text outside domain/prompts.py (Admin must be able to edit it)."""
    offenders = [p.name for p in APP.rglob("*.py") if p.name != "prompts.py" and "QUOTE RULES" in p.read_text()]
    assert not offenders
