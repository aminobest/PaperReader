"""Integration: US-08 annotations, US-09 notes, US-10 chat, US-11 admin."""

import json

from tests.integration.conftest import Q_GATE, generated_map, login, new_session_with_paper, wait_job

RECT = [[0.1, 0.2, 0.5, 0.22]]


def test_annotation_create_and_list(api):
    """AT-08.1"""
    client, _, _ = api
    _, paper = new_session_with_paper(client)
    a = client.post(f"/api/papers/{paper['id']}/annotations",
                    json={"page": 1, "rects": RECT, "color": "green", "text": "Short texts"}).json()
    assert a["color"] == "green" and a["rects"] == RECT
    assert [x["id"] for x in client.get(f"/api/papers/{paper['id']}/annotations").json()] == [a["id"]]


def test_annotation_edit_and_delete(api):
    """AT-08.2"""
    client, _, _ = api
    _, paper = new_session_with_paper(client)
    a = client.post(f"/api/papers/{paper['id']}/annotations", json={"page": 1, "rects": RECT, "color": "green"}).json()
    b = client.patch(f"/api/annotations/{a['id']}", json={"color": "pink", "comment": "key claim"}).json()
    assert b["color"] == "pink" and b["comment"] == "key claim"
    assert client.delete(f"/api/annotations/{a['id']}").status_code == 204
    assert client.get(f"/api/papers/{paper['id']}/annotations").json() == []


def test_annotation_validation(api):
    """AT-08.3"""
    client, _, _ = api
    _, paper = new_session_with_paper(client)
    url = f"/api/papers/{paper['id']}/annotations"
    assert client.post(url, json={"page": 1, "rects": RECT, "color": "purple"}).status_code == 422
    assert client.post(url, json={"page": 1, "rects": [[0, 0, 2, 2]], "color": "green"}).status_code == 422


def test_notes_crud_persist(api):
    """AT-09.1"""
    client, _, _ = api
    sid, _ = new_session_with_paper(client)
    n = client.post(f"/api/sessions/{sid}/notes", json={"body": "# Gate intuition\nIt filters noise."}).json()
    assert n["title"] == "Gate intuition"
    n2 = client.patch(f"/api/notes/{n['id']}", json={"body": "Second thought\nmore"}).json()
    assert n2["title"] == "Second thought"
    assert client.get(f"/api/sessions/{sid}/notes").json()[0]["body"] == "Second thought\nmore"
    assert client.delete(f"/api/notes/{n['id']}").status_code == 204
    assert client.get(f"/api/sessions/{sid}/notes").json() == []


def test_note_linked_to_node(api):
    """AT-09.2 — link, filter by node; deleting the node keeps the note but unlinks it."""
    client, llm, _ = api
    sid, _, mid, _ = generated_map(client, llm)
    method = next(n for n in client.get(f"/api/maps/{mid}").json()["nodes"] if n["title"].startswith("Method"))
    linked = client.post(f"/api/sessions/{sid}/notes", json={"body": "about the gate", "node_id": method["id"]}).json()
    client.post(f"/api/sessions/{sid}/notes", json={"body": "general"})
    only = client.get(f"/api/sessions/{sid}/notes", params={"node_id": method["id"]}).json()
    assert [x["id"] for x in only] == [linked["id"]]
    client.delete(f"/api/nodes/{method['id']}")
    notes = client.get(f"/api/sessions/{sid}/notes").json()
    assert len(notes) == 2 and all(x["node_id"] is None for x in notes)


def test_chat_thread_crud(api):
    """AT-10.1 — start about nodes or a passage; list, rename, delete."""
    client, llm, _ = api
    sid, _, mid, _ = generated_map(client, llm)
    method = next(n for n in client.get(f"/api/maps/{mid}").json()["nodes"] if n["title"].startswith("Method"))
    c1 = client.post(f"/api/sessions/{sid}/chats", json={"map_id": mid, "node_ids": [method["id"]]}).json()
    c2 = client.post(f"/api/sessions/{sid}/chats", json={"passage": "sigmoid unit"}).json()
    assert c1["title"] == "Method: the gate" and c2["title"] == "sigmoid unit"
    assert len(client.get(f"/api/sessions/{sid}/chats").json()) == 2
    assert client.patch(f"/api/chats/{c1['id']}", json={"title": "Gate Q&A"}).json()["title"] == "Gate Q&A"
    assert client.delete(f"/api/chats/{c2['id']}").status_code == 204
    assert [c["id"] for c in client.get(f"/api/sessions/{sid}/chats").json()] == [c1["id"]]


def test_chat_answer_quotes_grounded_and_linked(api):
    """AT-10.2 — verified quotes stored as origin=chat; [n] → [[q:id|n]]; unverifiable citation dropped."""
    client, llm, _ = api
    sid, _, mid, _ = generated_map(client, llm)
    method = next(n for n in client.get(f"/api/maps/{mid}").json()["nodes"] if n["title"].startswith("Method"))
    chat = client.post(f"/api/sessions/{sid}/chats", json={"map_id": mid, "node_ids": [method["id"]]}).json()
    llm.replies += [
        json.dumps({"answer": "The gate decides how much memory to read [1]. It is magic [2].",
                    "quotes": [{"n": 1, "paper": "P1", "page": 2, "text": Q_GATE},
                               {"n": 2, "paper": "P1", "page": 2, "text": "the gate is pure magic and nobody knows why"}]}),
        json.dumps({"fixes": [{"ref": "2", "text": None}]}),
    ]
    job = wait_job(client, client.post(f"/api/chats/{chat['id']}/messages", json={"content": "What does the gate do?"}).json()["id"])
    assert job["report"]["quotes_verified"] == 1 and job["report"]["quotes_dropped"] == 1
    full = client.get(f"/api/chats/{chat['id']}").json()
    q = full["quotes"][0]
    assert q["origin"] == "chat" and q["page"] == 2
    assert full["messages"][1]["content"] == f"The gate decides how much memory to read [[q:{q['id']}|1]]. It is magic ."
    assert [x["id"] for x in client.get(f"/api/sessions/{sid}/quotes").json()] == [q["id"]]
    focus = llm.calls[-2]["messages"][1]["content"]
    assert "Node: Method: the gate" in focus and "[P1 p.2]" in focus


def test_admin_requires_admin_role(env):
    """AT-11.1"""
    client, _, _ = env
    login(client, "reader", "reader123456")
    for method, path in [("get", "/api/admin/settings"), ("put", "/api/admin/settings"), ("get", "/api/admin/prompts"),
                         ("get", "/api/admin/logs"), ("delete", "/api/admin/logs")]:
        kwargs = {"json": {}} if method == "put" else {}
        assert getattr(client, method)(path, **kwargs).status_code == 403, path


def test_settings_used_by_next_llm_call(api):
    """AT-11.2"""
    client, llm, _ = api
    r = client.put("/api/admin/settings", json={"model": "openai/gpt-6-sol", "temperature": 0.9, "chat_color": "#123456"})
    assert r.status_code == 200 and r.json()["values"]["model"] == "openai/gpt-6-sol"
    assert client.put("/api/admin/settings", json={"model": "has space"}).status_code == 422
    assert client.put("/api/admin/settings", json={"temperature": 5}).status_code == 422
    generated_map(client, llm)
    assert llm.calls[-1]["model"] == "openai/gpt-6-sol" and llm.calls[-1]["temperature"] == 0.9
    assert client.get("/api/config").json()["chat_color"] == "#123456"


def test_prompt_templates_edit_reset_validate(api):
    """AT-11.3 — edited template is used; missing placeholder → 422; reset restores the default."""
    client, llm, _ = api
    prompts = client.get("/api/admin/prompts").json()
    assert {p["key"] for p in prompts} >= {"system", "map_generate", "node_expand", "node_reground", "chat", "quote_fix"}
    assert client.put("/api/admin/prompts/map_generate", json={"template": "no placeholder"}).status_code == 422
    r = client.put("/api/admin/prompts/map_generate", json={"template": "CUSTOM MAP PROMPT {{papers}}"})
    assert r.status_code == 200 and r.json()["is_default"] is False
    generated_map(client, llm)
    assert llm.calls[-1]["messages"][1]["content"].startswith("CUSTOM MAP PROMPT")
    assert client.post("/api/admin/prompts/map_generate/reset").json()["is_default"] is True


def test_ai_calls_are_logged(api):
    """AT-11.4"""
    client, llm, _ = api
    generated_map(client, llm)
    logs = client.get("/api/admin/logs").json()
    assert logs[0]["kind"] == "map_generate" and logs[0]["model"] == "test/model"
    assert logs[0]["messages"][0]["role"] == "system" and logs[0]["response"] and logs[0]["error"] is None
    assert logs[0]["duration_ms"] >= 0
    assert client.delete("/api/admin/logs").status_code == 204
    assert client.get("/api/admin/logs").json() == []


def test_delete_chat_message_removes_answer_and_evidence(api):
    """AT-10.5 — deleting a question also deletes its answer; the answer's quotes disappear."""
    client, llm, _ = api
    sid, _, mid, _ = generated_map(client, llm)
    chat = client.post(f"/api/sessions/{sid}/chats", json={"map_id": mid}).json()
    for q in ("first?", "second?"):
        llm.replies.append(json.dumps({"answer": "See [1].", "quotes": [{"n": 1, "paper": "P1", "page": 2,
                                                                          "text": Q_GATE}]}))
        wait_job(client, client.post(f"/api/chats/{chat['id']}/messages", json={"content": q}).json()["id"])
    msgs = client.get(f"/api/chats/{chat['id']}").json()["messages"]
    assert [m["role"] for m in msgs] == ["user", "assistant", "user", "assistant"]
    assert len(client.get(f"/api/sessions/{sid}/quotes").json()) == 2
    assert client.delete(f"/api/messages/{msgs[0]['id']}").status_code == 204
    left = client.get(f"/api/chats/{chat['id']}").json()["messages"]
    assert [m["content"] for m in left if m["role"] == "user"] == ["second?"] and len(left) == 2
    assert len(client.get(f"/api/sessions/{sid}/quotes").json()) == 1
    assert client.delete(f"/api/messages/{left[1]['id']}").status_code == 204
    assert client.get(f"/api/sessions/{sid}/quotes").json() == []
    login(client, "reader", "reader123456")
    assert client.delete(f"/api/messages/{left[0]['id']}").status_code == 404
