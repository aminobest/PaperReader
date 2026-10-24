"""Integration: US-04 grounding retries, US-05 generation, US-06 map CRUD + AI, US-07 payloads."""

import json

from tests.integration.conftest import (GOOD_MAP, Q_ABSTRACT, Q_GATE, Q_RESULT, generated_map, map_reply,
                                        new_session_with_paper, node, wait_job)


def test_generation_job_builds_grounded_map(api):
    """AT-05.3/AT-14.2/AT-14.3 — map is built and the prompt requires direct, unbounded evidence selection."""
    client, llm, _ = api
    sid, paper, mid, job = generated_map(client, llm)
    assert job["status"] == "done" and job["report"]["quotes_verified"] == 3
    m = client.get(f"/api/maps/{mid}").json()
    assert m["status"] == "ready" and m["title"] == "GMN map"
    root = next(n for n in m["nodes"] if n["parent_id"] is None)
    assert {n["title"] for n in m["nodes"] if n["parent_id"] == root["id"]} == {"Method: the gate", "Results"}
    assert len(m["links"]) == 1 and m["links"][0]["label"] == "is evidence for"
    prompt = llm.calls[0]["messages"][1]["content"]
    assert "[P1 p.1]" in prompt and "[P1 p.2]" in prompt  # AT-05.1 at the wire
    assert "not keyword matching" in prompt.lower() and "directly" in prompt
    assert "no fixed target or maximum" in prompt


def test_quote_payload_shape(api):
    """AT-07.5/AT-14.1 — quote linkage, contextual passage, normalized rects."""
    client, llm, _ = api
    _, paper, mid, _ = generated_map(client, llm)
    quotes = client.get(f"/api/maps/{mid}").json()["quotes"]
    assert quotes
    for q in quotes:
        assert q["node_id"] and q["paper_id"] == paper["id"] and q["page"] in (1, 2)
        assert q["rects"] and all(0 <= v <= 1 for r in q["rects"] for v in r)
    abstract = next(q for q in quotes if q["text"].startswith("Short texts"))
    assert abstract["page"] == 1 and len(abstract["rects"]) == 2  # wraps over two lines


def test_bad_quote_is_fixed_by_retry(api):
    """AT-04.3/AT-14.4 — an unsuitable quote is corrected without changing it into a fragment."""
    client, llm, _ = api
    bad = map_reply([node("n1", None, "Root", [(1, "GMN is a brand new solution for every text classification challenge in science and industry today.")], kind="topic")])
    fix = json.dumps({"fixes": [{"ref": "n1#0", "paper": "P1", "page": 1, "text": Q_ABSTRACT}]})
    sid, paper = new_session_with_paper(client)
    llm.replies += [bad, fix]
    r = client.post(f"/api/sessions/{sid}/maps", json={"paper_ids": [paper["id"]]}).json()
    job = wait_job(client, r["job"]["id"])
    assert job["report"]["fix_rounds"] == 1 and job["report"]["quotes_verified"] == 1
    assert "not found verbatim" in llm.calls[1]["messages"][-1]["content"]
    assert client.get(f"/api/maps/{r['map']['id']}").json()["quotes"][0]["text"].startswith("Short texts")


def test_unfixable_quote_is_dropped_and_reported(api):
    """AT-04.4 — after grounding_retries rounds the quote is dropped, counted and never stored."""
    client, llm, _ = api
    client.put("/api/admin/settings", json={"grounding_retries": 1})
    bad = map_reply([node("n1", None, "Root", [(1, "an invented sentence that is nowhere in the paper")], kind="topic")])
    nofix = json.dumps({"fixes": [{"ref": "n1#0", "text": "still invented text that is nowhere in it"}]})
    sid, paper = new_session_with_paper(client)
    llm.replies += [bad, nofix]
    r = client.post(f"/api/sessions/{sid}/maps", json={"paper_ids": [paper["id"]]}).json()
    job = wait_job(client, r["job"]["id"])
    assert job["report"]["quotes_dropped"] == 1 and job["report"]["quotes_verified"] == 0
    assert len(llm.calls) == 2
    assert client.get(f"/api/maps/{r['map']['id']}").json()["quotes"] == []


def test_malformed_json_gets_one_corrective_retry(api):
    """AT-05.2 — invalid JSON → json_fix message → success."""
    client, llm, _ = api
    sid, paper = new_session_with_paper(client)
    llm.replies += ["Sorry, here is a mind map: nodes...", GOOD_MAP]
    r = client.post(f"/api/sessions/{sid}/maps", json={"paper_ids": [paper["id"]]}).json()
    assert wait_job(client, r["job"]["id"])["status"] == "done"
    assert "could not be used" in llm.calls[1]["messages"][-1]["content"]


def test_failed_generation_marks_map_failed(api):
    """AT-05.3 — an LLM error marks the map failed with the error message."""
    client, llm, _ = api
    sid, paper = new_session_with_paper(client)
    llm.replies.append(RuntimeError("OpenRouter 401: key expired"))
    r = client.post(f"/api/sessions/{sid}/maps", json={"paper_ids": [paper["id"]]}).json()
    assert wait_job(client, r["job"]["id"])["status"] == "failed"
    m = client.get(f"/api/maps/{r['map']['id']}").json()
    assert m["status"] == "failed" and "key expired" in m["error"]


def test_map_for_a_set_of_papers(api):
    """AT-05.3 — one map over two papers labels them P1/P2."""
    client, llm, _ = api
    sid, p1 = new_session_with_paper(client)
    from tests.integration.conftest import PDF
    p2 = client.post(f"/api/sessions/{sid}/papers", files=[("files", ("b.pdf", PDF, "application/pdf"))]).json()[0]
    llm.replies.append(GOOD_MAP)
    r = client.post(f"/api/sessions/{sid}/maps", json={"paper_ids": [p1["id"], p2["id"]]}).json()
    wait_job(client, r["job"]["id"])
    prompt = llm.calls[0]["messages"][1]["content"]
    assert "=== P1:" in prompt and "=== P2:" in prompt


def test_node_crud_and_move(api):
    """AT-06.1 — add, edit, move (cycle rejected), delete subtree."""
    client, llm, _ = api
    _, _, mid, _ = generated_map(client, llm)
    m = client.get(f"/api/maps/{mid}").json()
    root = next(n for n in m["nodes"] if n["parent_id"] is None)
    method = next(n for n in m["nodes"] if n["title"].startswith("Method"))
    child = client.post(f"/api/maps/{mid}/nodes", json={"parent_id": method["id"], "title": "Sigmoid", "kind": "definition", "ground": False}).json()
    assert client.post(f"/api/maps/{mid}/nodes", json={"parent_id": method["id"], "title": " "}).status_code == 422
    assert client.post(f"/api/maps/{mid}/nodes", json={"parent_id": method["id"], "title": "x", "kind": "bad"}).status_code == 422
    edited = client.patch(f"/api/nodes/{child['id']}", json={"title": "Sigmoid gate", "explanation": "0..1 squash",
                                                             "reground": False}).json()
    assert edited["title"] == "Sigmoid gate" and edited["explanation"] == "0..1 squash"
    assert client.patch(f"/api/nodes/{method['id']}", json={"parent_id": child["id"]}).status_code == 422  # cycle
    assert client.patch(f"/api/nodes/{child['id']}", json={"parent_id": root["id"]}).json()["parent_id"] == root["id"]
    assert client.delete(f"/api/nodes/{root['id']}").status_code == 422
    assert client.delete(f"/api/nodes/{method['id']}").status_code == 204
    titles = {n["title"] for n in client.get(f"/api/maps/{mid}").json()["nodes"]}
    assert "Method: the gate" not in titles and "Sigmoid gate" in titles


def test_link_crud(api):
    """AT-06.2"""
    client, llm, _ = api
    _, _, mid, _ = generated_map(client, llm)
    nodes = client.get(f"/api/maps/{mid}").json()["nodes"]
    a, b = nodes[0]["id"], nodes[1]["id"]
    assert client.post(f"/api/maps/{mid}/links", json={"source_id": a, "target_id": a}).status_code == 422
    link = client.post(f"/api/maps/{mid}/links", json={"source_id": a, "target_id": b, "label": "uses"}).json()
    assert client.patch(f"/api/links/{link['id']}", json={"label": "depends on"}).json()["label"] == "depends on"
    assert client.delete(f"/api/links/{link['id']}").status_code == 204
    assert all(lk["id"] != link["id"] for lk in client.get(f"/api/maps/{mid}").json()["links"])


def test_expand_appends_grounded_children(api):
    """AT-06.3"""
    client, llm, _ = api
    _, _, mid, _ = generated_map(client, llm)
    method = next(n for n in client.get(f"/api/maps/{mid}").json()["nodes"] if n["title"].startswith("Method"))
    llm.replies.append(json.dumps({"nodes": [
        node("c1", None, "Gate near zero", [(2, "When the gate value is close to zero the model ignores the memory and relies on the recurrent state.")]),
        node("c2", "c1", "Falls back to RNN state", [])]}))
    job = wait_job(client, client.post(f"/api/nodes/{method['id']}/expand").json()["id"])
    assert job["status"] == "done" and job["report"]["nodes"] == 2 and job["report"]["quotes_verified"] == 1
    nodes = client.get(f"/api/maps/{mid}").json()["nodes"]
    c1 = next(n for n in nodes if n["title"] == "Gate near zero")
    assert c1["parent_id"] == method["id"]
    assert next(n for n in nodes if n["title"] == "Falls back to RNN state")["parent_id"] == c1["id"]
    assert "NODE PATH: Gated Memory Networks > Method: the gate" in llm.calls[-1]["messages"][1]["content"]


def test_reground_replaces_quotes(api):
    """AT-06.4"""
    client, llm, _ = api
    _, _, mid, _ = generated_map(client, llm)
    res = next(n for n in client.get(f"/api/maps/{mid}").json()["nodes"] if n["title"] == "Results")
    client.patch(f"/api/nodes/{res['id']}", json={"title": "Ablation", "reground": False})
    llm.replies.append(json.dumps({"quotes": [{"paper": "P1", "page": 2,
                                               "text": "Ablation shows that removing the gate costs 1.7 points, which confirms that selective reading is the key ingredient."}]}))
    wait_job(client, client.post(f"/api/nodes/{res['id']}/reground").json()["id"])
    qs = [q for q in client.get(f"/api/maps/{mid}").json()["quotes"] if q["node_id"] == res["id"]]
    assert [q["text"][:8] for q in qs] == ["Ablation"]
    assert "NODE: Ablation" in llm.calls[-1]["messages"][1]["content"]


def test_fold_to_depth(api):
    """AT-06.5 — the depth control persists fold state server-side."""
    client, llm, _ = api
    _, _, mid, _ = generated_map(client, llm)
    m = client.post(f"/api/maps/{mid}/fold", json={"depth": 0}).json()
    root = next(n for n in m["nodes"] if n["parent_id"] is None)
    assert root["collapsed"] == 1
    m = client.post(f"/api/maps/{mid}/fold", json={"depth": None}).json()
    assert not any(n["collapsed"] for n in m["nodes"])


def test_rename_and_delete_map(api):
    """AT-06.6"""
    client, llm, _ = api
    sid, _, mid, _ = generated_map(client, llm)
    assert client.patch(f"/api/maps/{mid}", json={"title": "Mine"}).json()["title"] == "Mine"
    assert client.delete(f"/api/maps/{mid}").status_code == 204
    assert client.get(f"/api/sessions/{sid}").json()["maps"] == []
    assert client.app.state.repo.query("SELECT COUNT(*) c FROM quotes")[0]["c"] == 0


def test_manual_quote_link_is_verified(api):
    """AT-07.5 — linking a selected passage to a node verifies it like an AI quote."""
    client, llm, _ = api
    _, paper, mid, _ = generated_map(client, llm)
    n = client.get(f"/api/maps/{mid}").json()["nodes"][0]
    ok = client.post(f"/api/nodes/{n['id']}/quotes", json={"paper_id": paper["id"], "page": 2, "text": Q_RESULT})
    assert ok.status_code == 201 and ok.json()["page"] == 2
    bad = client.post(f"/api/nodes/{n['id']}/quotes", json={"paper_id": paper["id"], "text": "not in this paper at all, nope"})
    assert bad.status_code == 422
    assert Q_GATE  # fixture sanity


def test_evidence_rederived_on_add_and_meaning_edit(api):
    """AT-06.7 — new node and title/explanation edits start a re-grounding job; fold/move/kind don't."""
    client, llm, _ = api
    _, _, mid, _ = generated_map(client, llm)
    nodes = client.get(f"/api/maps/{mid}").json()["nodes"]
    root = next(n for n in nodes if n["parent_id"] is None)
    method = next(n for n in nodes if n["title"].startswith("Method"))
    llm.replies.append(json.dumps({"quotes": [{"paper": "P1", "page": 2, "text": Q_RESULT}]}))
    new = client.post(f"/api/maps/{mid}/nodes", json={"parent_id": root["id"], "title": "TREC accuracy"}).json()
    assert new["job"] and wait_job(client, new["job"]["id"])["status"] == "done"
    quotes = client.get(f"/api/maps/{mid}").json()["quotes"]
    assert [q["text"][:10] for q in quotes if q["node_id"] == new["id"]] == ["GMN reache"]
    for body in ({"collapsed": True}, {"kind": "insight"}, {"parent_id": new["id"]}, {"title": "method: THE gate "}):
        assert client.patch(f"/api/nodes/{method['id']}", json=body).json()["job"] is None, body
    llm.replies.append(json.dumps({"quotes": [{"paper": "P1", "page": 2, "text": Q_GATE}]}))
    edited = client.patch(f"/api/nodes/{method['id']}", json={"explanation": "a sigmoid decides how much memory to read"}).json()
    assert edited["job"] and wait_job(client, edited["job"]["id"])["status"] == "done"
    assert "a sigmoid decides" in llm.calls[-1]["messages"][1]["content"]
    assert client.patch(f"/api/nodes/{method['id']}", json={"title": "Gate", "reground": False}).json()["job"] is None
    assert client.post(f"/api/maps/{mid}/nodes", json={"parent_id": root["id"], "title": "x", "ground": False}).json()["job"] is None


def test_shallow_map_is_deepened_once(api):
    """AT-05.5 — a 1-level map triggers one map_deepen call; merged nodes are grounded; report has depth."""
    client, llm, _ = api
    client.put("/api/admin/settings", json={"min_map_depth": 3})
    deeper = json.dumps({"nodes": [
        node("d1", "n2", "Sigmoid output", [(2, "When the gate value is close to zero the model ignores the memory and relies on the recurrent state.")]),
        node("d2", "d1", "Falls back to the recurrent state")]})
    sid, paper = new_session_with_paper(client)
    llm.replies += [GOOD_MAP, deeper]
    r = client.post(f"/api/sessions/{sid}/maps", json={"paper_ids": [paper["id"]]}).json()
    job = wait_job(client, r["job"]["id"])
    assert job["report"]["depth"] == 3 and job["report"]["nodes"] == 5 and job["report"]["quotes_verified"] == 4
    assert "only goes 1 level(s)" in llm.calls[1]["messages"][-1]["content"]
    nodes = {n["title"]: n for n in client.get(f"/api/maps/{r['map']['id']}").json()["nodes"]}
    assert nodes["Falls back to the recurrent state"]["parent_id"] == nodes["Sigmoid output"]["id"]
    assert nodes["Sigmoid output"]["parent_id"] == nodes["Method: the gate"]["id"]


def test_deepen_failure_never_fails_the_map(api):
    """AT-05.5"""
    client, llm, _ = api
    client.put("/api/admin/settings", json={"min_map_depth": 3})
    sid, paper = new_session_with_paper(client)
    llm.replies += [GOOD_MAP, RuntimeError("OpenRouter 503")]
    r = client.post(f"/api/sessions/{sid}/maps", json={"paper_ids": [paper["id"]]}).json()
    assert wait_job(client, r["job"]["id"])["report"]["depth"] == 1


def test_model_selected_number_of_passages_is_not_capped(api):
    """AT-14.3 — all distinct passages selected by the model are accepted; the app imposes no quote-count cap."""
    client, llm, _ = api
    sid, paper = new_session_with_paper(client)
    ablation = ("Ablation shows that removing the gate costs 1.7 points, which confirms that selective "
                "reading is the key ingredient.")
    llm.replies += [
        map_reply([node("n1", None, "Gated memory network evidence",
                        [(1, Q_ABSTRACT), (2, Q_GATE), (2, Q_RESULT), (2, ablation)], kind="topic")]),
    ]
    r = client.post(f"/api/sessions/{sid}/maps", json={"paper_ids": [paper["id"]]}).json()
    job = wait_job(client, r["job"]["id"])
    assert job["status"] == "done" and job["report"]["quotes_verified"] == 4
    assert len(client.get(f"/api/maps/{r['map']['id']}").json()["quotes"]) == 4
    assert len(llm.calls) == 1
