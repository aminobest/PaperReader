"""Integration: US-01 sign-in, US-02 sessions, US-03 papers, US-12 manifest, CR-02 health/binding."""

import json
from pathlib import Path

from tests.integration.conftest import PDF, login, new_session_with_paper

ROOT = Path(__file__).resolve().parents[2]


def test_login_with_plans_tracker_format_user(env):
    """AT-01.1 — the seeded pbkdf2 hash verifies through the API; wrong password → 401."""
    client, _, _ = env
    assert client.post("/api/auth/login", json={"username": "test", "password": "nope"}).status_code == 401
    assert login(client)["role"] == "admin"
    assert client.get("/api/auth/me").json()["username"] == "test"


def test_api_requires_auth(env):
    """AT-01.2 — every API route except login/health answers 401 without a cookie."""
    client, _, _ = env
    for path in ["/api/sessions", "/api/auth/me", "/api/config", "/api/admin/settings", "/api/jobs/x"]:
        assert client.get(path).status_code == 401, path
    assert client.get("/api/health").status_code == 200
    login(client)
    client.post("/api/auth/logout")
    assert client.get("/api/sessions").status_code == 401


def test_users_seeded_once(env):
    """AT-01.3 — users.json imported; a second import (restart) adds nothing and keeps changes."""
    client, _, data = env
    repo = client.app.state.repo
    users = json.loads((data / "users.json").read_text())["users"]
    assert repo.user_by_name("test") and repo.user_by_name("reader")
    assert repo.seed_users(users) == 0


def test_create_and_validate_session(api):
    """AT-02.1"""
    client, _, _ = api
    assert client.post("/api/sessions", json={"name": "  "}).status_code == 422
    s = client.post("/api/sessions", json={"name": " Transformers "}).json()
    assert s["name"] == "Transformers"
    assert [x["name"] for x in client.get("/api/sessions").json()] == ["Transformers"]


def test_rename_and_delete_session_cascades(api):
    """AT-02.2 — delete removes papers (and files), maps, notes, chats."""
    client, _, data = api
    sid, paper = new_session_with_paper(client)
    assert client.patch(f"/api/sessions/{sid}", json={"name": "Renamed"}).json()["name"] == "Renamed"
    client.post(f"/api/sessions/{sid}/notes", json={"body": "hello"})
    client.post(f"/api/sessions/{sid}/chats", json={})
    pdf_file = data / "papers" / f"{paper['id']}.pdf"
    assert pdf_file.exists()
    assert client.delete(f"/api/sessions/{sid}").status_code == 204
    assert not pdf_file.exists()
    repo = client.app.state.repo
    for table in ("papers", "notes", "chats", "maps"):
        assert repo.query(f"SELECT COUNT(*) AS c FROM {table}")[0]["c"] == 0


def test_sessions_are_private(env):
    """AT-02.3 — another user can neither list nor open my session or its papers."""
    client, _, _ = env
    login(client)
    sid, paper = new_session_with_paper(client)
    client.post("/api/auth/logout")
    login(client, "reader", "reader123456")
    assert client.get("/api/sessions").json() == []
    assert client.get(f"/api/sessions/{sid}").status_code == 404
    assert client.get(f"/api/papers/{paper['id']}/file").status_code == 404
    assert client.delete(f"/api/sessions/{sid}").status_code == 404


def test_upload_multiple_pdfs(api):
    """AT-03.1 — each PDF becomes a paper with pages + word positions; title from metadata."""
    client, _, _ = api
    sid = client.post("/api/sessions", json={"name": "S"}).json()["id"]
    files = [("files", ("a.pdf", PDF, "application/pdf")), ("files", ("b.pdf", PDF, "application/pdf"))]
    papers = client.post(f"/api/sessions/{sid}/papers", files=files).json()
    assert len(papers) == 2 and papers[0]["page_count"] == 2
    assert papers[0]["title"] == "Gated Memory Networks for Short Text Classification"
    pages = client.app.state.repo.pages(papers[0]["id"])
    assert len(pages) == 2 and pages[0]["words"][0][4] == "Gated"
    r = client.get(f"/api/papers/{papers[0]['id']}/file")
    assert r.status_code == 200 and r.content.startswith(b"%PDF")


def test_non_pdf_rejected(api):
    """AT-03.2"""
    client, _, _ = api
    sid = client.post("/api/sessions", json={"name": "S"}).json()["id"]
    r = client.post(f"/api/sessions/{sid}/papers", files=[("files", ("x.pdf", b"hello", "application/pdf"))])
    assert r.status_code == 400


def test_rename_and_delete_paper(api):
    """AT-03.4 — delete removes the file, annotations and quotes; maps forget the paper."""
    client, _, data = api
    sid, paper = new_session_with_paper(client)
    pid = paper["id"]
    assert client.patch(f"/api/papers/{pid}", json={"title": "New"}).json()["title"] == "New"
    client.post(f"/api/papers/{pid}/annotations", json={"page": 1, "rects": [[0.1, 0.1, 0.2, 0.2]], "color": "yellow"})
    m = client.post(f"/api/sessions/{sid}/maps", json={"paper_ids": [pid], "generate": False, "title": "M"}).json()["map"]
    root = client.get(f"/api/maps/{m['id']}").json()["nodes"][0]
    client.post(f"/api/nodes/{root['id']}/quotes", json={"paper_id": pid, "text": "The gate is a sigmoid unit computed from the current query"})
    assert client.delete(f"/api/papers/{pid}").status_code == 204
    assert not (data / "papers" / f"{pid}.pdf").exists()
    repo = client.app.state.repo
    assert repo.query("SELECT COUNT(*) c FROM annotations")[0]["c"] == 0
    assert repo.query("SELECT COUNT(*) c FROM quotes")[0]["c"] == 0
    assert client.get(f"/api/maps/{m['id']}").json()["paper_ids"] == []


def test_manifest_and_apple_meta(env):
    """AT-12.4"""
    client, _, _ = env
    manifest = client.get("/manifest.webmanifest").json()
    assert manifest["display"] == "standalone" and manifest["icons"]
    html = client.get("/").text
    assert 'rel="manifest"' in html and "apple-mobile-web-app-capable" in html and "apple-touch-icon" in html
    assert client.get("/icons/icon-180.png").status_code == 200


def test_health_and_localhost_binding(env):
    """AT-C02.1 — health ok; compose publishes the port on 127.0.0.1 only (Tailscale Serve fronts it)."""
    client, _, _ = env
    assert client.get("/api/health").json() == {"status": "ok"}
    compose = (ROOT / "docker-compose.yml").read_text()
    ports = [line.strip() for line in compose.splitlines() if line.strip().startswith('- "') and ":" in line]
    assert ports and all(p.startswith('- "127.0.0.1:') for p in ports), ports
