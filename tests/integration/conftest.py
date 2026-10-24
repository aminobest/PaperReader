"""Integration fixtures: real app (FastAPI + SQLite + PyMuPDF) in a temp DATA_DIR; LLM = scripted stub."""

import json
import shutil
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.infrastructure.config import Config
from app.main import create_app

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
PDF = (FIXTURES / "tiny_paper.pdf").read_bytes()
Q_ABSTRACT = "Short texts such as tweets and search queries carry little context, which makes them hard to classify."
Q_GATE = "The gate is a sigmoid unit computed from the current query and the memory summary."
Q_RESULT = ("GMN reaches 88.4 percent accuracy on the TREC question dataset, compared with 86.1 percent "
           "for the best recurrent baseline.")


class ScriptedLLM:
    """Returns queued replies in order and records every call (model, temperature, messages)."""

    def __init__(self):
        self.replies: list = []
        self.calls: list[dict] = []

    async def complete(self, messages, *, model, temperature):
        self.calls.append({"model": model, "temperature": temperature, "messages": messages})
        if not self.replies:
            raise RuntimeError("ScriptedLLM: no reply queued")
        r = self.replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return r(messages) if callable(r) else r


def node(id_, parent, title, quotes=(), kind="detail", explanation="plain words"):
    return {"id": id_, "parent": parent, "title": title, "kind": kind, "explanation": explanation,
            "quotes": [{"paper": "P1", "page": p, "text": t} for p, t in quotes]}


def map_reply(nodes, links=(), title="GMN map"):
    return json.dumps({"title": title, "nodes": nodes, "links": list(links)})


GOOD_MAP = map_reply([
    node("n1", None, "Gated Memory Networks", [(1, Q_ABSTRACT)], kind="topic"),
    node("n2", "n1", "Method: the gate", [(2, Q_GATE)], kind="method"),
    node("n3", "n1", "Results", [(2, Q_RESULT)], kind="result"),
], links=[{"from": "n3", "to": "n2", "label": "is evidence for"}])


@pytest.fixture
def env(tmp_path):
    shutil.copy(FIXTURES / "users.json", tmp_path / "users.json")
    llm = ScriptedLLM()
    cfg = Config(data_dir=str(tmp_path), openrouter_api_key="", openrouter_base_url="http://unused",
                 default_model="test/model", cookie_secure=False, llm_timeout=5)
    app = create_app(cfg, llm_client=llm)
    app.state.repo.set_settings({"min_map_depth": 0})  # fixture maps are shallow; AT-05.5 tests opt back in
    with TestClient(app) as client:
        yield client, llm, tmp_path


def login(client, username="test", password="test123456789"):
    r = client.post("/api/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture
def api(env):
    client, llm, data = env
    login(client)
    return client, llm, data


def wait_job(client, job_id, timeout=10):
    end = time.time() + timeout
    while time.time() < end:
        j = client.get(f"/api/jobs/{job_id}").json()
        if j["status"] in ("done", "failed"):
            return j
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} did not finish")


def new_session_with_paper(client, name="S"):
    sid = client.post("/api/sessions", json={"name": name}).json()["id"]
    paper = client.post(f"/api/sessions/{sid}/papers", files=[("files", ("gmn.pdf", PDF, "application/pdf"))]).json()[0]
    return sid, paper


def generated_map(client, llm, reply=GOOD_MAP):
    sid, paper = new_session_with_paper(client)
    llm.replies.append(reply)
    r = client.post(f"/api/sessions/{sid}/maps", json={"paper_ids": [paper["id"]]}).json()
    job = wait_job(client, r["job"]["id"])
    return sid, paper, r["map"]["id"], job
