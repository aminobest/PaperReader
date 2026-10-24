"""US-10 — chat about nodes or a passage; answers cite grounded quotes (origin='chat')."""

from __future__ import annotations

import re

from app.application.grounding_service import Candidate, ground, llm_fixer
from app.application.map_service import _path, ask_json, load_papers
from app.application.settings import effective_settings, prompt
from app.domain.ids import now
from app.domain.mindmap import MapFormatError, extract_json, parse_quotes
from app.domain.prompts import render
from app.domain.rules import chat_context, link_citations, node_path, papers_block


_LINKED = re.compile(r"\[\[q:\w+\|(\d+)\]\]")


def chat_nodes(repo, chat: dict) -> list[dict]:
    out = []
    for nid in chat["node_ids"]:
        n = repo.get("nodes", nid)
        if n:
            out.append({**n, "path": node_path([p["title"] for p in _path(repo, n)])})
    return out


def build_messages(repo, gateway, chat: dict, papers) -> list[dict]:
    """AT-10.4 — system persona + framed focus/papers, then the whole history."""
    frame = render(prompt(repo, "chat"), papers=papers_block(papers),
                   context=chat_context(None, chat_nodes(repo, chat), chat.get("passage")))
    msgs = [gateway.system_message(), {"role": "user", "content": frame},
            {"role": "assistant", "content": "{\"answer\": \"Understood. What would you like to know?\", \"quotes\": []}"}]
    for m in repo.query("SELECT role, content FROM messages WHERE chat_id=? ORDER BY created_at, rowid", (chat["id"],)):
        msgs.append({"role": m["role"], "content": _LINKED.sub(r"[\1]", m["content"])})
    return msgs


def parse_answer(reply: str) -> tuple[str, list]:
    data = extract_json(reply)
    answer = str(data.get("answer") or "").strip()
    if not answer:
        raise MapFormatError("`answer` is missing")
    items = data.get("quotes") or []
    quotes = []
    for i, item in enumerate(items, start=1):
        q = parse_quotes([item], "P1")
        if q:
            n = item.get("n", i) if isinstance(item, dict) else i
            quotes.append((int(n) if str(n).isdigit() else i, q[0]))
    return answer, quotes


async def send_message(repo, gateway, chat_id: str, content: str) -> dict:
    """AT-10.2 — store the question, ask, ground the quotes, store the linked answer."""
    chat = repo.get("chats", chat_id)
    papers = load_papers(repo, chat["paper_ids"])
    msgs = build_messages(repo, gateway, chat, papers)
    repo.insert("messages", chat_id=chat_id, role="user", content=content, created_at=now())
    msgs.append({"role": "user", "content": content})
    try:
        (answer, quotes), conv = await ask_json(gateway, repo, "chat", msgs, parse_answer)
    except MapFormatError:
        answer, quotes, conv = "Sorry — the model's reply could not be read. Please ask again.", [], msgs
    cands = [Candidate(ref=str(n), paper=q.paper, page=q.page, text=q.text, context=f"citation [{n}]")
             for n, q in quotes]
    s = effective_settings(repo, gateway.default_model)
    result = await ground(cands, {p.label: p for p in papers},
                          llm_fixer(gateway, conv, prompt(repo, "quote_fix")), s["grounding_retries"])
    msg = repo.insert("messages", chat_id=chat_id, role="assistant", content=answer, report=result.report(),
                      created_at=now())
    kept: dict[int, str] = {}
    for ref, loc in result.located.items():
        kept[int(ref)] = repo.add_quotes([loc], origin="chat", message_id=msg["id"])[0]["id"]
    repo.update("messages", msg["id"], content=link_citations(answer, kept))
    repo.update("chats", chat_id, updated_at=now())
    return {"message_id": msg["id"], **result.report()}
