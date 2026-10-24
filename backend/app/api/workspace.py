"""US-08 annotations · US-09 notes · US-10 chats (CRUD + ask)."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.api.deps import current_user, get_repo, owned
from app.application import chat_service
from app.domain.ids import now
from app.domain.rules import ValidationError, clean_name, note_title, validate_annotation

router = APIRouter(prefix="/api", tags=["annotations", "notes", "chats"])


def _check(fn, *args):
    try:
        return fn(*args)
    except ValidationError as exc:
        raise HTTPException(422, str(exc)) from exc


# ---- US-08 annotations -----------------------------------------------------------
class AnnotationIn(BaseModel):
    page: int
    rects: list[list[float]]
    color: str
    text: str = ""
    comment: str = ""


class AnnotationPatch(BaseModel):
    color: Optional[str] = None
    comment: Optional[str] = None


@router.get("/papers/{pid}/annotations")
def list_annotations(pid: str, user=Depends(current_user), repo=Depends(get_repo)):
    owned(repo, "papers", pid, user)
    return repo.query("SELECT * FROM annotations WHERE paper_id=? ORDER BY page, created_at", (pid,))


@router.post("/papers/{pid}/annotations", status_code=201)
def add_annotation(pid: str, body: AnnotationIn, user=Depends(current_user), repo=Depends(get_repo)):
    """AT-08.1 / AT-08.3"""
    owned(repo, "papers", pid, user)
    _check(validate_annotation, body.color, body.rects)
    return repo.insert("annotations", paper_id=pid, page=body.page, rects=body.rects, color=body.color,
                       text=body.text.strip(), comment=body.comment, created_at=now(), updated_at=now())


@router.patch("/annotations/{aid}")
def edit_annotation(aid: str, body: AnnotationPatch, user=Depends(current_user), repo=Depends(get_repo)):
    """AT-08.2"""
    owned(repo, "annotations", aid, user)
    cols = {"updated_at": now()}
    if body.color is not None:
        _check(validate_annotation, body.color, [[0, 0, 0, 0]])
        cols["color"] = body.color
    if body.comment is not None:
        cols["comment"] = body.comment
    return repo.update("annotations", aid, **cols)


@router.delete("/annotations/{aid}", status_code=204)
def delete_annotation(aid: str, user=Depends(current_user), repo=Depends(get_repo)):
    owned(repo, "annotations", aid, user)
    repo.delete("annotations", aid)


# ---- US-09 notes ---------------------------------------------------------------------
class NoteIn(BaseModel):
    title: str = ""
    body: str = ""
    node_id: Optional[str] = None


class NotePatch(BaseModel):
    title: Optional[str] = None
    body: Optional[str] = None
    node_id: Optional[str] = None
    unlink: bool = False


def _check_node(repo, sid: str, node_id: Optional[str]) -> None:
    if node_id and repo.session_of("nodes", node_id) != sid:
        raise HTTPException(422, "node must belong to this session")


@router.get("/sessions/{sid}/notes")
def list_notes(sid: str, node_id: Optional[str] = None, user=Depends(current_user), repo=Depends(get_repo)):
    """AT-09.2 — optional filter by node."""
    owned(repo, "sessions", sid, user)
    if node_id:
        return repo.query("SELECT * FROM notes WHERE session_id=? AND node_id=? ORDER BY updated_at DESC",
                          (sid, node_id))
    return repo.query("SELECT * FROM notes WHERE session_id=? ORDER BY updated_at DESC", (sid,))


@router.post("/sessions/{sid}/notes", status_code=201)
def add_note(sid: str, body: NoteIn, user=Depends(current_user), repo=Depends(get_repo)):
    owned(repo, "sessions", sid, user)
    _check_node(repo, sid, body.node_id)
    return repo.insert("notes", session_id=sid, node_id=body.node_id, title=note_title(body.title, body.body),
                       body=body.body, created_at=now(), updated_at=now())


@router.patch("/notes/{nid}")
def edit_note(nid: str, body: NotePatch, user=Depends(current_user), repo=Depends(get_repo)):
    """AT-09.1 — autosave target."""
    sid = owned(repo, "notes", nid, user)
    note = repo.get("notes", nid)
    cols = {"updated_at": now()}
    if body.body is not None:
        cols["body"] = body.body
    if body.title is not None or body.body is not None:
        cols["title"] = note_title(body.title, body.body if body.body is not None else note["body"])
    if body.node_id is not None:
        _check_node(repo, sid, body.node_id)
        cols["node_id"] = body.node_id
    if body.unlink:
        cols["node_id"] = None
    return repo.update("notes", nid, **cols)


@router.delete("/notes/{nid}", status_code=204)
def delete_note(nid: str, user=Depends(current_user), repo=Depends(get_repo)):
    owned(repo, "notes", nid, user)
    repo.delete("notes", nid)


# ---- US-10 chats ----------------------------------------------------------------------
class ChatIn(BaseModel):
    map_id: Optional[str] = None
    node_ids: list[str] = []
    paper_ids: list[str] = []
    passage: Optional[str] = None
    title: str = ""


class ChatPatch(BaseModel):
    title: str


class MessageIn(BaseModel):
    content: str


@router.get("/sessions/{sid}/chats")
def list_chats(sid: str, user=Depends(current_user), repo=Depends(get_repo)):
    owned(repo, "sessions", sid, user)
    return repo.query("SELECT * FROM chats WHERE session_id=? ORDER BY updated_at DESC", (sid,))


@router.post("/sessions/{sid}/chats", status_code=201)
def create_chat(sid: str, body: ChatIn, user=Depends(current_user), repo=Depends(get_repo)):
    """AT-10.1 — about selected node(s) and/or a passage; papers default to the map's or the session's."""
    owned(repo, "sessions", sid, user)
    for nid in body.node_ids:
        _check_node(repo, sid, nid)
    paper_ids = body.paper_ids
    if body.map_id:
        if repo.session_of("maps", body.map_id) != sid:
            raise HTTPException(422, "map must belong to this session")
        paper_ids = paper_ids or repo.get("maps", body.map_id)["paper_ids"]
    if not paper_ids:
        paper_ids = [p["id"] for p in repo.query("SELECT id FROM papers WHERE session_id=?", (sid,))]
    for pid in paper_ids:
        if repo.session_of("papers", pid) != sid:
            raise HTTPException(422, "papers must belong to this session")
    title = body.title.strip()
    if not title:
        first = repo.get("nodes", body.node_ids[0]) if body.node_ids else None
        title = first["title"] if first else (body.passage or "Chat about the paper").strip()[:60]
    return repo.insert("chats", session_id=sid, map_id=body.map_id, node_ids=body.node_ids, paper_ids=paper_ids,
                       passage=body.passage, title=title, created_at=now(), updated_at=now())


@router.get("/chats/{cid}")
def get_chat(cid: str, user=Depends(current_user), repo=Depends(get_repo)):
    owned(repo, "chats", cid, user)
    chat = repo.get("chats", cid)
    chat["messages"] = repo.query("SELECT * FROM messages WHERE chat_id=? ORDER BY created_at, rowid", (cid,))
    chat["quotes"] = repo.query(
        "SELECT q.id, q.origin, q.node_id, q.message_id, q.paper_id, q.page, q.text, q.rects, q.created_at "
        "FROM quotes q JOIN messages m ON m.id=q.message_id WHERE m.chat_id=?", (cid,))
    return chat


@router.patch("/chats/{cid}")
def rename_chat(cid: str, body: ChatPatch, user=Depends(current_user), repo=Depends(get_repo)):
    owned(repo, "chats", cid, user)
    return repo.update("chats", cid, title=_check(clean_name, body.title, "title"), updated_at=now())


@router.delete("/chats/{cid}", status_code=204)
def delete_chat(cid: str, user=Depends(current_user), repo=Depends(get_repo)):
    owned(repo, "chats", cid, user)
    repo.delete("chats", cid)


@router.delete("/messages/{mid}", status_code=204)
def delete_message(mid: str, user=Depends(current_user), repo=Depends(get_repo)):
    """AT-10.5 — delete a message (a question also removes the answer that follows it); quotes cascade."""
    msg = repo.get("messages", mid)
    if not msg:
        raise HTTPException(404, "message not found")
    owned(repo, "chats", msg["chat_id"], user)
    ids = [mid]
    if msg["role"] == "user":
        nxt = repo.query("SELECT id, role FROM messages WHERE chat_id=? AND rowid > (SELECT rowid FROM messages WHERE id=?)"
                         " ORDER BY rowid LIMIT 1", (msg["chat_id"], mid))
        if nxt and nxt[0]["role"] == "assistant":
            ids.append(nxt[0]["id"])
    for i in ids:
        repo.delete("messages", i)


@router.post("/chats/{cid}/messages", status_code=202)
async def ask(cid: str, body: MessageIn, request: Request, user=Depends(current_user), repo=Depends(get_repo)):
    """AT-10.2 — answer is produced by a job; the UI polls /jobs/{id} then reloads the chat."""
    sid = owned(repo, "chats", cid, user)
    content = body.content.strip()
    if not content:
        raise HTTPException(422, "message must not be empty")
    gw = request.app.state.gateway
    return request.app.state.jobs.start(user_id=user["id"], session_id=sid, kind="chat", target_id=cid,
                                        work=lambda: chat_service.send_message(repo, gw, cid, content))


@router.get("/sessions/{sid}/quotes")
def session_chat_quotes(sid: str, user=Depends(current_user), repo=Depends(get_repo)):
    """US-07 — all chat quotes of a session (the always-visible AI-trace layer)."""
    owned(repo, "sessions", sid, user)
    return repo.query(
        "SELECT q.id, q.origin, q.node_id, q.message_id, q.paper_id, q.page, q.text, q.rects, q.created_at, m.chat_id "
        "FROM quotes q JOIN messages m ON m.id=q.message_id JOIN chats c ON c.id=m.chat_id "
        "WHERE c.session_id=?", (sid,))
