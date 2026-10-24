"""US-01/US-02 — request dependencies: repo, current user, admin guard, ownership checks."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request

from app.infrastructure.security import read_token

COOKIE = "paperreader_session"


def get_repo(request: Request):
    return request.app.state.repo


def current_user(request: Request) -> dict:
    """AT-01.2 — 401 without a valid session cookie."""
    repo = request.app.state.repo
    token = request.cookies.get(COOKIE)
    uid = read_token(repo.secret(), token) if token else None
    user = repo.get("users", uid) if uid else None
    if not user or not user["active"]:
        raise HTTPException(401, "Authentication required")
    return user


def require_admin(user: dict = Depends(current_user)) -> dict:
    """AT-11.1"""
    if user["role"] != "admin":
        raise HTTPException(403, "Administrator access required")
    return user


def owned(repo, table: str, id_: str, user: dict) -> str:
    """AT-02.3 — return the owning session id, or 404 if missing or not the user's."""
    sid = repo.session_of(table, id_)
    s = repo.get("sessions", sid) if sid else None
    if not s or s["user_id"] != user["id"]:
        raise HTTPException(404, f"{table[:-1]} not found")
    return sid
