"""US-05/US-06 — AI use cases on maps: generate, expand a node, re-ground a node."""

from __future__ import annotations

import logging

from app.application.grounding_service import Candidate, ground, llm_fixer
from app.application.settings import effective_settings, prompt
from app.domain.grounding import PageIndex, PaperIndex, Word
from app.domain.mindmap import (MapFormatError, RawNode, depth_of, extract_json, fold_flags, merge_deeper,
                                parse_children, parse_map, parse_quotes)
from app.domain.prompts import render
from app.domain.rules import node_path, papers_block
from app.domain.ids import now


log = logging.getLogger("paperreader.maps")


def load_papers(repo, paper_ids: list[str]) -> list[PaperIndex]:
    out = []
    for i, pid in enumerate(paper_ids, start=1):
        p = repo.get("papers", pid)
        if not p:
            continue
        pages = [PageIndex(page=pg["page"], words=[Word(*w) for w in pg["words"]]) for pg in repo.pages(pid)]
        out.append(PaperIndex(paper_id=pid, label=f"P{i}", title=p["title"], pages=pages))
    return out


async def ask_json(gateway, repo, kind: str, messages: list[dict], parse):
    """Ask, parse; on a format error send one corrective message (AT-05.2). Returns (parsed, conversation)."""
    reply = await gateway.ask(kind, messages)
    conv = messages + [{"role": "assistant", "content": reply}]
    try:
        return parse(reply), conv
    except MapFormatError as exc:
        fix = {"role": "user", "content": render(prompt(repo, "json_fix"), error=str(exc))}
        reply = await gateway.ask(kind + ":json_fix", conv + [fix])
        conv = conv + [fix, {"role": "assistant", "content": reply}]
        return parse(reply), conv


def _candidates(nodes: list[RawNode]) -> list[Candidate]:
    return [Candidate(ref=f"{n.ref}#{i}", paper=q.paper, page=q.page, text=q.text, context=n.title)
            for n in nodes for i, q in enumerate(n.quotes)]


async def _ground_nodes(repo, gateway, nodes, papers, conv):
    s = effective_settings(repo, gateway.default_model)
    return await ground(_candidates(nodes), {p.label: p for p in papers},
                        llm_fixer(gateway, conv, prompt(repo, "quote_fix")), s["grounding_retries"])


def _persist_nodes(repo, map_id: str, nodes: list[RawNode], result, top_parent_id: str | None,
                   top_parent_ref: str | None = None) -> dict[str, str]:
    ids: dict[str, str] = {}
    positions: dict[str | None, int] = {}
    for n in nodes:
        parent_id = top_parent_id if n.parent in (None, top_parent_ref) else ids.get(n.parent, top_parent_id)
        if parent_id not in positions:
            positions[parent_id] = repo.next_position(map_id, parent_id)
        row = repo.insert("nodes", map_id=map_id, parent_id=parent_id, title=n.title, explanation=n.explanation,
                          kind=n.kind, position=positions[parent_id], created_at=now(), updated_at=now())
        positions[parent_id] += 1
        ids[n.ref] = row["id"]
        located = [result.located[f"{n.ref}#{i}"] for i in range(len(n.quotes)) if f"{n.ref}#{i}" in result.located]
        repo.add_quotes(located, origin="map", node_id=row["id"])
    return ids


async def generate_map(repo, gateway, map_id: str) -> dict:
    """AT-05.3 — whole-map generation job."""
    m = repo.get("maps", map_id)
    papers = load_papers(repo, m["paper_ids"])
    if not papers:
        raise ValueError("map has no papers")
    user = render(prompt(repo, "map_generate"), papers=papers_block(papers))
    raw, conv = await ask_json(gateway, repo, "map_generate", [gateway.system_message(),
                                                               {"role": "user", "content": user}], parse_map)
    depth, min_depth = depth_of(raw.nodes), effective_settings(repo, gateway.default_model)["min_map_depth"]
    if depth < min_depth:  # AT-05.5: one request to reach the details; never fatal
        ask = {"role": "user", "content": render(prompt(repo, "map_deepen"), depth=str(depth), min_depth=str(min_depth))}
        try:
            reply = await gateway.ask("map_deepen", conv + [ask])
            raw.nodes += merge_deeper(raw, reply)
            conv = conv + [ask, {"role": "assistant", "content": reply}]
        except Exception:  # noqa: BLE001 — the map is still useful without the extra depth
            log.warning("map %s: deepening failed", map_id, exc_info=True)
    result = await _ground_nodes(repo, gateway, raw.nodes, papers, conv)
    ids = _persist_nodes(repo, map_id, raw.nodes, result, None)
    for link in raw.links:
        repo.insert("links", map_id=map_id, source_id=ids[link.source], target_id=ids[link.target], label=link.label)
    if len(raw.nodes) > 12:
        fold(repo, map_id, 2)  # open on the big picture; the reader drills down
    report = {"nodes": len(raw.nodes), "links": len(raw.links), "depth": depth_of(raw.nodes), **result.report()}
    repo.update("maps", map_id, title=m["title"] or raw.title, status="ready", error=None, report=report,
                updated_at=now())
    return report


def fold(repo, map_id: str, depth: int | None) -> None:
    nodes = repo.query("SELECT id, parent_id FROM nodes WHERE map_id=?", (map_id,))
    for node_id, collapsed in fold_flags(nodes, depth).items():
        repo.update("nodes", node_id, collapsed=int(collapsed))


def _path(repo, node: dict) -> list[dict]:
    chain, cur = [], node
    while cur:
        chain.append(cur)
        cur = repo.get("nodes", cur["parent_id"]) if cur["parent_id"] else None
    return list(reversed(chain))


def describe(node: dict) -> str:
    return f"{node['title']} ({node['kind']}): {node['explanation']}"


async def expand_node(repo, gateway, node_id: str) -> dict:
    """AT-06.3 — append grounded, more detailed children under a node."""
    node = repo.get("nodes", node_id)
    m = repo.get("maps", node["map_id"])
    papers = load_papers(repo, m["paper_ids"])
    children = repo.query("SELECT title FROM nodes WHERE parent_id=?", (node_id,))
    user = render(prompt(repo, "node_expand"), papers=papers_block(papers),
                  node_path=node_path([n["title"] for n in _path(repo, node)]), node=describe(node),
                  existing_children=", ".join(c["title"] for c in children) or "none")
    nodes, conv = await ask_json(gateway, repo, "node_expand",
                                 [gateway.system_message(), {"role": "user", "content": user}],
                                 lambda r: parse_children(r, "__parent__"))
    result = await _ground_nodes(repo, gateway, nodes, papers, conv)
    _persist_nodes(repo, m["id"], nodes, result, node_id, "__parent__")
    repo.update("nodes", node_id, collapsed=0, updated_at=now())
    return {"nodes": len(nodes), **result.report()}


async def reground_node(repo, gateway, node_id: str) -> dict:
    """AT-06.4 — replace a node's quotes with freshly verified ones (kept if none verify)."""
    node = repo.get("nodes", node_id)
    m = repo.get("maps", node["map_id"])
    papers = load_papers(repo, m["paper_ids"])
    user = render(prompt(repo, "node_reground"), papers=papers_block(papers),
                  node_path=node_path([n["title"] for n in _path(repo, node)]), node=describe(node))

    def parse(reply: str):
        return parse_quotes(extract_json(reply).get("quotes"), "P1")

    quotes, conv = await ask_json(gateway, repo, "node_reground",
                                  [gateway.system_message(), {"role": "user", "content": user}], parse)
    raw = RawNode(ref="n", parent=None, title=node["title"], explanation="", kind=node["kind"], quotes=quotes)
    result = await _ground_nodes(repo, gateway, [raw], papers, conv)
    report = result.report()
    if result.located:
        repo.delete_node_quotes(node_id)
        repo.add_quotes(list(result.located.values()), origin="map", node_id=node_id)
    else:
        report["note"] = "no verified quotes found; previous quotes kept"
    return report
