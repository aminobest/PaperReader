"""US-01 — login / logout / me."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from app.api.deps import COOKIE, current_user, get_repo
from app.infrastructure.security import SESSION_TTL, make_token, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


class Login(BaseModel):
    username: str
    password: str


def public(u: dict) -> dict:
    return {"id": u["id"], "username": u["username"], "role": u["role"]}


@router.post("/login")
def login(body: Login, request: Request, response: Response, repo=Depends(get_repo)):
    user = repo.user_by_name(body.username)
    if not user or not user["active"] or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(401, "Invalid username or password")
    response.set_cookie(COOKIE, make_token(repo.secret(), user["id"]), max_age=SESSION_TTL, httponly=True,
                        samesite="lax", secure=request.app.state.config.cookie_secure, path="/")
    return public(user)


@router.post("/logout", status_code=204)
def logout(response: Response):
    response.delete_cookie(COOKIE, path="/")


@router.get("/me")
def me(user=Depends(current_user)):
    return public(user)
