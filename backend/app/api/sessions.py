"""US-02 sessions CRUD · US-03 papers upload/read/manage."""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.api.deps import current_user, get_repo, owned
from app.domain.ids import now
from app.domain.rules import ValidationError, clean_name, default_paper_title
from app.infrastructure import pdf

router = APIRouter(prefix="/api", tags=["sessions", "papers"])
MAX_PDF_BYTES = 150 * 1024 * 1024


class SessionIn(BaseModel):
    name: str


class PaperPatch(BaseModel):
    title: str


def _name(name: str, what: str) -> str:
    try:
        return clean_name(name, what)
    except ValidationError as exc:
        raise HTTPException(422, str(exc)) from exc


def paper_path(request: Request, paper_id: str) -> str:
    return os.path.join(request.app.state.config.data_dir, "papers", f"{paper_id}.pdf")


@router.get("/sessions")
def list_sessions(user=Depends(current_user), repo=Depends(get_repo)):
    return repo.query(
        "SELECT s.*, (SELECT COUNT(*) FROM papers p WHERE p.session_id=s.id) AS paper_count "
        "FROM sessions s WHERE user_id=? ORDER BY updated_at DESC", (user["id"],))


@router.post("/sessions", status_code=201)
def create_session(body: SessionIn, user=Depends(current_user), repo=Depends(get_repo)):
    return repo.insert("sessions", user_id=user["id"], name=_name(body.name, "session name"),
                       created_at=now(), updated_at=now())


@router.get("/sessions/{sid}")
def get_session(sid: str, user=Depends(current_user), repo=Depends(get_repo)):
    owned(repo, "sessions", sid, user)
    s = repo.get("sessions", sid)
    s["papers"] = repo.query("SELECT * FROM papers WHERE session_id=? ORDER BY created_at", (sid,))
    s["maps"] = repo.query("SELECT id, title, paper_ids, status, error, report, created_at, updated_at "
                           "FROM maps WHERE session_id=? ORDER BY created_at", (sid,))
    return s


@router.patch("/sessions/{sid}")
def rename_session(sid: str, body: SessionIn, user=Depends(current_user), repo=Depends(get_repo)):
    owned(repo, "sessions", sid, user)
    return repo.update("sessions", sid, name=_name(body.name, "session name"), updated_at=now())


@router.delete("/sessions/{sid}", status_code=204)
def delete_session(sid: str, request: Request, user=Depends(current_user), repo=Depends(get_repo)):
    """AT-02.2 — cascades to papers (and their files), maps, notes, chats."""
    owned(repo, "sessions", sid, user)
    for p in repo.query("SELECT id FROM papers WHERE session_id=?", (sid,)):
        _remove_file(paper_path(request, p["id"]))
    repo.delete("sessions", sid)


def _remove_file(path: str) -> None:
    try:
        os.remove(path)
    except FileNotFoundError:
        pass


@router.post("/sessions/{sid}/papers", status_code=201)
def upload_papers(sid: str, request: Request, files: list[UploadFile] = File(...),
                  user=Depends(current_user), repo=Depends(get_repo)):
    """AT-03.1 / AT-03.2"""
    owned(repo, "sessions", sid, user)
    created = []
    os.makedirs(os.path.dirname(paper_path(request, "x")), exist_ok=True)
    for f in files:
        data = f.file.read(MAX_PDF_BYTES + 1)
        if len(data) > MAX_PDF_BYTES:
            raise HTTPException(413, f"{f.filename}: larger than 150 MB")
        try:
            extracted = pdf.extract(data)
        except pdf.NotAPDF as exc:
            raise HTTPException(400, f"{f.filename}: {exc}") from exc
        paper = repo.insert("papers", session_id=sid, filename=f.filename,
                            title=default_paper_title(extracted["meta_title"], f.filename or "paper.pdf",
                                                      extracted.get("heading")),
                            page_count=len(extracted["pages"]), created_at=now())
        with open(paper_path(request, paper["id"]), "wb") as out:
            out.write(data)
        repo.save_pages(paper["id"], extracted["pages"])
        created.append(paper)
    repo.update("sessions", sid, updated_at=now())
    return created


@router.get("/papers/{pid}/file")
def paper_file(pid: str, request: Request, user=Depends(current_user), repo=Depends(get_repo)):
    owned(repo, "papers", pid, user)
    return FileResponse(paper_path(request, pid), media_type="application/pdf",
                        headers={"Cache-Control": "private, max-age=86400"})


@router.patch("/papers/{pid}")
def rename_paper(pid: str, body: PaperPatch, user=Depends(current_user), repo=Depends(get_repo)):
    owned(repo, "papers", pid, user)
    return repo.update("papers", pid, title=_name(body.title, "title"))


@router.delete("/papers/{pid}", status_code=204)
def delete_paper(pid: str, request: Request, user=Depends(current_user), repo=Depends(get_repo)):
    """AT-03.4 — removes file, annotations and quotes (FK cascade); maps forget the paper."""
    sid = owned(repo, "papers", pid, user)
    for m in repo.query("SELECT id, paper_ids FROM maps WHERE session_id=?", (sid,)):
        if pid in m["paper_ids"]:
            repo.update("maps", m["id"], paper_ids=[x for x in m["paper_ids"] if x != pid])
    repo.delete("papers", pid)
    _remove_file(paper_path(request, pid))
