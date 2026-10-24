"""US-13 — per-user UI preferences (e.g. workspace layout per device class)."""

from __future__ import annotations

import json

from fastapi import APIRouter, Body, Depends, HTTPException

from app.api.deps import current_user, get_repo
from app.domain.rules import ValidationError, validate_pref

router = APIRouter(prefix="/api/prefs", tags=["prefs"])


@router.get("")
def get_prefs(user=Depends(current_user), repo=Depends(get_repo)):
    return repo.prefs(user["id"])


@router.put("/{key}")
def put_pref(key: str, value: dict = Body(...), user=Depends(current_user), repo=Depends(get_repo)):
    """AT-13.6"""
    try:
        validate_pref(key, json.dumps(value))
    except ValidationError as exc:
        raise HTTPException(422, str(exc)) from exc
    repo.set_pref(user["id"], key, value)
    return repo.prefs(user["id"])


@router.delete("/{key}", status_code=204)
def delete_pref(key: str, user=Depends(current_user), repo=Depends(get_repo)):
    """AT-13.4 — reset to the default layout."""
    repo.set_pref(user["id"], key, None)
