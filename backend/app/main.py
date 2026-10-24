"""CR-02 — FastAPI app factory: wires repo, LLM gateway, job runner, routers and the static PWA."""

from __future__ import annotations

import json
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import admin, auth, maps, prefs, sessions, workspace
from app.application.jobs import JobRunner
from app.application.llm_gateway import LLMGateway
from app.infrastructure.config import Config, load_config
from app.infrastructure.llm import OpenRouterClient
from app.infrastructure.repo import Repo

FRONTEND = os.environ.get("FRONTEND_DIR", os.path.join(os.path.dirname(__file__), "..", "..", "frontend"))


def create_app(config: Config | None = None, llm_client=None) -> FastAPI:
    config = config or load_config()
    os.makedirs(os.path.join(config.data_dir, "papers"), exist_ok=True)
    repo = Repo(os.path.join(config.data_dir, "paperreader.db"))
    seed = os.path.join(config.data_dir, "users.json")
    if os.path.exists(seed):  # AT-01.3
        with open(seed) as f:
            repo.seed_users(json.load(f).get("users", []))
    client = llm_client or OpenRouterClient(config.openrouter_api_key, config.openrouter_base_url, config.llm_timeout)
    jobs = JobRunner(repo)

    @asynccontextmanager
    async def lifespan(_app):
        jobs.recover()
        yield

    app = FastAPI(title="PaperReader", lifespan=lifespan)
    app.state.config = config
    app.state.repo = repo
    app.state.gateway = LLMGateway(repo, client, config.default_model)
    app.state.jobs = jobs

    for r in (auth.router, sessions.router, maps.router, workspace.router, admin.router, prefs.router):
        app.include_router(r)

    @app.get("/api/health")
    def health():
        """AT-C02.1"""
        return {"status": "ok"}

    @app.middleware("http")
    async def revalidate_static(request: Request, call_next):
        response = await call_next(request)
        if not request.url.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-cache")
        return response

    index = os.path.join(FRONTEND, "index.html")

    @app.get("/", include_in_schema=False)
    @app.get("/admin", include_in_schema=False)
    def spa():
        return FileResponse(index)

    app.mount("/", StaticFiles(directory=FRONTEND), name="static")
    return app


logging.basicConfig(level=logging.INFO)
# run with: uvicorn app.main:create_app --factory
