"""US-05 generation · US-06 map/node/link CRUD + AI expand/re-ground · US-07 quote payloads."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.api.deps import current_user, get_repo, owned
from app.application import map_service
from app.application.map_service import load_papers
from app.domain.grounding import QuoteError, locate
from app.domain.ids import now
from app.domain.mindmap import KINDS, meaning_changed, would_create_cycle
from app.domain.rules import ValidationError, clean_name

router = APIRouter(prefix="/api", tags=["maps"])


class MapIn(BaseModel):
    paper_ids: list[str]
    title: str = ""
    generate: bool = True


class MapPatch(BaseModel):
    title: str


class NodeIn(BaseModel):
    parent_id: str
    title: str
    explanation: str = ""
    kind: str = "detail"
    ground: bool = True  # AT-06.7: find evidence with the AI right away (opt-out)


class NodePatch(BaseModel):
    title: Optional[str] = None
    explanation: Optional[str] = None
    kind: Optional[str] = None
    parent_id: Optional[str] = None
    position: Optional[int] = None
    collapsed: Optional[bool] = None
    reground: Optional[bool] = None  # AT-06.7: None = automatic when the meaning changed


class FoldIn(BaseModel):
    depth: Optional[int] = None


class LinkIn(BaseModel):
    source_id: str
    target_id: str
    label: str = ""


class LinkPatch(BaseModel):
    label: str


class QuoteIn(BaseModel):
    paper_id: str
    page: Optional[int] = None
    text: str


def _clean(name: str, what: str) -> str:
    try:
        return clean_name(name, what, 200)
    except ValidationError as exc:
        raise HTTPException(422, str(exc)) from exc


def _kind(kind: str) -> str:
    if kind not in KINDS:
        raise HTTPException(422, f"kind must be one of {', '.join(KINDS)}")
    return kind


def _gateway(request: Request):
    return request.app.state.gateway


def _start(request: Request, user, sid, kind, target, work, on_fail=None):
    return request.app.state.jobs.start(user_id=user["id"], session_id=sid, kind=kind, target_id=target,
                                        work=work, on_fail=on_fail)


@router.post("/sessions/{sid}/maps", status_code=201)
async def create_map(sid: str, body: MapIn, request: Request, user=Depends(current_user), repo=Depends(get_repo)):
    """AT-05.3 — one paper or a set of papers; generation runs as a job."""
    owned(repo, "sessions", sid, user)
    if not body.paper_ids:
        raise HTTPException(422, "select at least one paper")
    for pid in body.paper_ids:
        if repo.session_of("papers", pid) != sid:
            raise HTTPException(422, "papers must belong to this session")
    m = repo.insert("maps", session_id=sid, title=body.title.strip(), paper_ids=body.paper_ids,
                    status="generating" if body.generate else "ready", created_at=now(), updated_at=now())
    if not body.generate:
        repo.insert("nodes", map_id=m["id"], parent_id=None, title=body.title.strip() or "Central topic",
                    kind="topic", position=0, created_at=now(), updated_at=now())
        return {"map": repo.get("maps", m["id"]), "job": None}
    gw = _gateway(request)
    job = _start(request, user, sid, "map_generate", m["id"],
                 lambda: map_service.generate_map(repo, gw, m["id"]),
                 lambda err: repo.update("maps", m["id"], status="failed", error=err))
    return {"map": m, "job": job}


@router.get("/maps/{mid}")
def get_map(mid: str, user=Depends(current_user), repo=Depends(get_repo)):
    """AT-07.5 — nodes, links and quotes (paper, page, normalised rects)."""
    owned(repo, "maps", mid, user)
    return repo.map_full(mid)


@router.patch("/maps/{mid}")
def rename_map(mid: str, body: MapPatch, user=Depends(current_user), repo=Depends(get_repo)):
    owned(repo, "maps", mid, user)
    return repo.update("maps", mid, title=_clean(body.title, "title"), updated_at=now())


@router.delete("/maps/{mid}", status_code=204)
def delete_map(mid: str, user=Depends(current_user), repo=Depends(get_repo)):
    owned(repo, "maps", mid, user)
    repo.delete("maps", mid)


@router.post("/maps/{mid}/fold")
def fold_map(mid: str, body: FoldIn, user=Depends(current_user), repo=Depends(get_repo)):
    """AT-06.5 — show the map down to `depth` levels (None = unfold everything)."""
    owned(repo, "maps", mid, user)
    map_service.fold(repo, mid, body.depth)
    return repo.map_full(mid)


def _reground_job(request: Request, user, sid: str, nid: str, repo) -> dict:
    gw = _gateway(request)
    return _start(request, user, sid, "node_reground", nid, lambda: map_service.reground_node(repo, gw, nid))


@router.post("/maps/{mid}/nodes", status_code=201)
async def add_node(mid: str, body: NodeIn, request: Request, user=Depends(current_user), repo=Depends(get_repo)):
    """AT-06.1 add · AT-06.7 the new node's evidence is derived by the AI unless ground=false."""
    sid = owned(repo, "maps", mid, user)
    parent = repo.get("nodes", body.parent_id)
    if not parent or parent["map_id"] != mid:
        raise HTTPException(422, "parent must be a node of this map")
    node = repo.insert("nodes", map_id=mid, parent_id=body.parent_id, title=_clean(body.title, "title"),
                       explanation=body.explanation.strip(), kind=_kind(body.kind),
                       position=repo.next_position(mid, body.parent_id), created_at=now(), updated_at=now())
    return {**node, "job": _reground_job(request, user, sid, node["id"], repo) if body.ground else None}


@router.patch("/nodes/{nid}")
async def edit_node(nid: str, body: NodePatch, request: Request, user=Depends(current_user), repo=Depends(get_repo)):
    """AT-06.1 — edit fields, move (no cycles), reorder, collapse.
    AT-06.7 — when title/explanation change, the evidence is re-derived (unless reground=false)."""
    sid = owned(repo, "nodes", nid, user)
    node = repo.get("nodes", nid)
    cols: dict = {}
    if body.title is not None:
        cols["title"] = _clean(body.title, "title")
    if body.explanation is not None:
        cols["explanation"] = body.explanation.strip()
    if body.kind is not None:
        cols["kind"] = _kind(body.kind)
    if body.collapsed is not None:
        cols["collapsed"] = int(body.collapsed)
    if body.parent_id is not None and body.parent_id != node["parent_id"]:
        if node["parent_id"] is None:
            raise HTTPException(422, "the central node cannot be moved")
        target = repo.get("nodes", body.parent_id)
        if not target or target["map_id"] != node["map_id"]:
            raise HTTPException(422, "new parent must be a node of this map")
        parents = {n["id"]: n["parent_id"] for n in repo.query("SELECT id, parent_id FROM nodes WHERE map_id=?",
                                                                (node["map_id"],))}
        if would_create_cycle(nid, body.parent_id, parents):
            raise HTTPException(422, "cannot move a node under itself or its descendants")
        cols["parent_id"] = body.parent_id
        cols["position"] = repo.next_position(node["map_id"], body.parent_id)
    if body.position is not None:
        cols["position"] = body.position
    cols["updated_at"] = now()
    auto = meaning_changed(node, cols) if body.reground is None else body.reground
    updated = repo.update("nodes", nid, **cols)
    return {**updated, "job": _reground_job(request, user, sid, nid, repo) if auto else None}


@router.delete("/nodes/{nid}", status_code=204)
def delete_node(nid: str, user=Depends(current_user), repo=Depends(get_repo)):
    """AT-06.1 — deletes the subtree (FK cascade); linked notes are kept but unlinked (AT-09.2)."""
    owned(repo, "nodes", nid, user)
    if repo.get("nodes", nid)["parent_id"] is None:
        raise HTTPException(422, "the central node cannot be deleted; delete the map instead")
    repo.delete("nodes", nid)


@router.post("/nodes/{nid}/expand", status_code=202)
async def expand(nid: str, request: Request, user=Depends(current_user), repo=Depends(get_repo)):
    sid = owned(repo, "nodes", nid, user)
    gw = _gateway(request)
    return _start(request, user, sid, "node_expand", nid, lambda: map_service.expand_node(repo, gw, nid))


@router.post("/nodes/{nid}/reground", status_code=202)
async def reground(nid: str, request: Request, user=Depends(current_user), repo=Depends(get_repo)):
    sid = owned(repo, "nodes", nid, user)
    gw = _gateway(request)
    return _start(request, user, sid, "node_reground", nid, lambda: map_service.reground_node(repo, gw, nid))


@router.post("/nodes/{nid}/quotes", status_code=201)
def add_quote(nid: str, body: QuoteIn, user=Depends(current_user), repo=Depends(get_repo)):
    """US-07 — link a passage selected in the paper to a node (verified like AI quotes)."""
    sid = owned(repo, "nodes", nid, user)
    if repo.session_of("papers", body.paper_id) != sid:
        raise HTTPException(422, "paper must belong to this session")
    paper = load_papers(repo, [body.paper_id])[0]
    try:
        loc = locate(body.text, paper, body.page)
    except QuoteError as exc:
        raise HTTPException(422, f"quote rejected: {exc}") from exc
    return repo.add_quotes([loc], origin="map", node_id=nid)[0]


@router.delete("/quotes/{qid}", status_code=204)
def delete_quote(qid: str, user=Depends(current_user), repo=Depends(get_repo)):
    owned(repo, "quotes", qid, user)
    repo.delete("quotes", qid)


@router.post("/maps/{mid}/links", status_code=201)
def add_link(mid: str, body: LinkIn, user=Depends(current_user), repo=Depends(get_repo)):
    """AT-06.2"""
    owned(repo, "maps", mid, user)
    for nid in (body.source_id, body.target_id):
        n = repo.get("nodes", nid)
        if not n or n["map_id"] != mid:
            raise HTTPException(422, "both ends must be nodes of this map")
    if body.source_id == body.target_id:
        raise HTTPException(422, "a link needs two different nodes")
    return repo.insert("links", map_id=mid, source_id=body.source_id, target_id=body.target_id,
                       label=body.label.strip()[:80])


@router.patch("/links/{lid}")
def edit_link(lid: str, body: LinkPatch, user=Depends(current_user), repo=Depends(get_repo)):
    owned(repo, "links", lid, user)
    return repo.update("links", lid, label=body.label.strip()[:80])


@router.delete("/links/{lid}", status_code=204)
def delete_link(lid: str, user=Depends(current_user), repo=Depends(get_repo)):
    owned(repo, "links", lid, user)
    repo.delete("links", lid)


@router.get("/jobs/{jid}")
def get_job(jid: str, user=Depends(current_user), repo=Depends(get_repo)):
    job = repo.get("jobs", jid)
    if not job or job["user_id"] != user["id"]:
        raise HTTPException(404, "job not found")
    return job
