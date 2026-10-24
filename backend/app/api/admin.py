"""US-11 — admin: settings (model…), prompt templates CRUD, AI call log."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException, Request

from app.api.deps import current_user, get_repo, require_admin
from app.application.settings import MODEL_PRESETS, all_prompts, effective_settings, validate_settings
from app.domain import prompts
from app.domain.mindmap import KINDS
from app.domain.rules import PALETTE

router = APIRouter(prefix="/api", tags=["admin"])


@router.get("/config")
def public_config(request: Request, user=Depends(current_user), repo=Depends(get_repo)):
    """Settings the workspace UI needs (colors, palette, model name) — any signed-in user."""
    s = effective_settings(repo, request.app.state.config.default_model)
    return {"palette": list(PALETTE), "chat_color": s["chat_color"], "map_color": s["map_color"],
            "model": s["model"], "kinds": list(KINDS)}


@router.get("/admin/settings")
def get_settings(request: Request, _=Depends(require_admin), repo=Depends(get_repo)):
    return {"values": effective_settings(repo, request.app.state.config.default_model), "presets": MODEL_PRESETS}


@router.put("/admin/settings")
def put_settings(request: Request, values: dict = Body(...), _=Depends(require_admin), repo=Depends(get_repo)):
    """AT-11.2"""
    try:
        repo.set_settings(validate_settings(values))
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, str(exc)) from exc
    return get_settings(request, _, repo)


@router.get("/admin/prompts")
def list_prompts(_=Depends(require_admin), repo=Depends(get_repo)):
    return all_prompts(repo)


@router.put("/admin/prompts/{key}")
def put_prompt(key: str, body: dict = Body(...), _=Depends(require_admin), repo=Depends(get_repo)):
    """AT-11.3 — rejected when a required placeholder is missing."""
    template = str(body.get("template", ""))
    try:
        prompts.validate_template(key, template)
    except prompts.TemplateError as exc:
        raise HTTPException(422, str(exc)) from exc
    repo.set_prompt(key, template)
    return next(p for p in all_prompts(repo) if p["key"] == key)


@router.post("/admin/prompts/{key}/reset")
def reset_prompt(key: str, _=Depends(require_admin), repo=Depends(get_repo)):
    if key not in prompts.DEFAULTS:
        raise HTTPException(404, "unknown prompt")
    repo.set_prompt(key, None)
    return next(p for p in all_prompts(repo) if p["key"] == key)


@router.get("/admin/logs")
def list_logs(limit: int = 100, _=Depends(require_admin), repo=Depends(get_repo)):
    """AT-11.4"""
    return repo.query("SELECT * FROM ai_logs ORDER BY ts DESC, rowid DESC LIMIT ?", (min(limit, 500),))


@router.delete("/admin/logs", status_code=204)
def clear_logs(_=Depends(require_admin), repo=Depends(get_repo)):
    repo.clear_ai_logs()
