"""US-05/US-06/US-14 — parse mind maps and their explanatory, traceable evidence."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

KINDS = (
    "topic", "question", "background", "definition", "method",
    "result", "evidence", "limitation", "insight", "detail",
)
MAX_NODES = 400


class MapFormatError(ValueError):
    pass


@dataclass
class RawQuote:
    paper: str  # label, e.g. "P1"
    page: int | None
    text: str


@dataclass
class RawNode:
    ref: str  # id given by the LLM, e.g. "n3"
    parent: str | None
    title: str
    explanation: str
    kind: str
    quotes: list[RawQuote] = field(default_factory=list)


@dataclass
class RawLink:
    source: str
    target: str
    label: str


@dataclass
class RawMap:
    title: str
    nodes: list[RawNode]  # parents always before children
    links: list[RawLink]


def extract_json(text: str) -> dict:
    """Pull the first JSON object out of an LLM reply (tolerates ``` fences and prose)."""
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    candidate = fenced.group(1) if fenced else text
    start, end = candidate.find("{"), candidate.rfind("}")
    if start < 0 or end <= start:
        raise MapFormatError("no JSON object found in the reply")
    try:
        data = json.loads(candidate[start : end + 1])
    except json.JSONDecodeError as exc:
        raise MapFormatError(f"invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise MapFormatError("top-level JSON must be an object")
    return data


def parse_quotes(items, default_paper: str) -> list[RawQuote]:
    out = []
    for q in items or []:
        if isinstance(q, str):
            q = {"text": q}
        if not isinstance(q, dict) or not isinstance(q.get("text"), str) or not q["text"].strip():
            continue
        page = q.get("page")
        try:
            page = int(page) if page is not None else None
        except (TypeError, ValueError):
            page = None
        out.append(RawQuote(
            paper=str(q.get("paper") or default_paper),
            page=page,
            text=q["text"].strip(),
        ))
    return out


def normalize_kind(kind) -> str:
    kind = str(kind or "").strip().lower()
    return kind if kind in KINDS else "detail"


def parse_nodes(items, default_paper: str, root_parent: str | None = None) -> list[RawNode]:
    """Parse a flat node list (`id`, `parent`, …). Orphans re-attach to the root; output is parent-first."""
    if not isinstance(items, list) or not items:
        raise MapFormatError("`nodes` must be a non-empty list")
    nodes: dict[str, RawNode] = {}
    for i, n in enumerate(items[:MAX_NODES]):
        if not isinstance(n, dict) or not str(n.get("title", "")).strip():
            continue
        ref = str(n.get("id") or f"_n{i}")
        if ref in nodes:
            ref = f"{ref}_{i}"
        parent = n.get("parent")
        nodes[ref] = RawNode(
            ref=ref,
            parent=str(parent) if parent not in (None, "", "null") else None,
            title=str(n["title"]).strip()[:200],
            explanation=str(n.get("explanation") or n.get("summary") or "").strip(),
            kind=normalize_kind(n.get("kind")),
            quotes=parse_quotes(n.get("quotes"), default_paper),
        )
    if not nodes:
        raise MapFormatError("no valid nodes")
    if root_parent is None:
        roots = [n for n in nodes.values() if n.parent is None or n.parent not in nodes]
        root = next((n for n in roots if n.parent is None), roots[0] if roots else next(iter(nodes.values())))
        root.parent = None
        for n in nodes.values():
            if n is not root and (n.parent is None or n.parent not in nodes or n.parent == n.ref):
                n.parent = root.ref
    else:
        for n in nodes.values():
            if n.parent is None or n.parent not in nodes or n.parent == n.ref:
                n.parent = root_parent
    return _parent_first(list(nodes.values()), root_parent)


def _parent_first(nodes: list[RawNode], top_parent: str | None) -> list[RawNode]:
    children: dict[str | None, list[RawNode]] = {}
    for n in nodes:
        children.setdefault(n.parent, []).append(n)
    ordered, stack, seen = [], list(reversed(children.get(top_parent, []))), set()
    while stack:
        n = stack.pop()
        if n.ref in seen:
            continue
        seen.add(n.ref)
        ordered.append(n)
        stack.extend(reversed(children.get(n.ref, [])))
    if len(ordered) != len(nodes):
        # nodes caught in a parent cycle: break it by hanging them off the first top-level node
        anchor = ordered[0].ref if ordered else None
        for n in nodes:
            if n.ref not in seen:
                n.parent = anchor if top_parent is None else top_parent
                ordered.append(n)
    return ordered


def parse_links(items, refs: set[str]) -> list[RawLink]:
    out = []
    for link in items or []:
        if not isinstance(link, dict):
            continue
        s, t = str(link.get("from", "")), str(link.get("to", ""))
        if s in refs and t in refs and s != t:
            out.append(RawLink(source=s, target=t, label=str(link.get("label") or "").strip()[:80]))
    return out


def parse_map(text: str, default_paper: str = "P1") -> RawMap:
    """AT-05.2 — LLM reply → RawMap. Raises MapFormatError on unusable output."""
    data = extract_json(text)
    nodes = parse_nodes(data.get("nodes"), default_paper)
    return RawMap(
        title=str(data.get("title") or nodes[0].title).strip()[:200],
        nodes=nodes,
        links=parse_links(data.get("links"), {n.ref for n in nodes}),
    )


def parse_children(text: str, parent_ref: str, default_paper: str = "P1") -> list[RawNode]:
    """AT-06.3 — expansion reply: nodes whose top-level parent is the expanded node."""
    data = extract_json(text)
    return parse_nodes(data.get("nodes"), default_paper, root_parent=parent_ref)


def would_create_cycle(node_id: str, new_parent_id: str, parent_of: dict[str, str | None]) -> bool:
    """AT-06.1 — moving node under new_parent is illegal if new_parent is the node or its descendant."""
    cur: str | None = new_parent_id
    while cur is not None:
        if cur == node_id:
            return True
        cur = parent_of.get(cur)
    return False


def fold_flags(nodes: list[dict], depth: int | None) -> dict[str, bool]:
    """AT-06.5 — collapsed flag per node so that exactly `depth` levels below the root are visible."""
    kids: dict[str | None, list[str]] = {}
    for n in nodes:
        kids.setdefault(n["parent_id"], []).append(n["id"])
    out: dict[str, bool] = {}
    stack = [(r, 0) for r in kids.get(None, [])]
    while stack:
        nid, d = stack.pop()
        out[nid] = depth is not None and d >= depth and bool(kids.get(nid))
        stack.extend((c, d + 1) for c in kids.get(nid, []))
    return out


def meaning_changed(before: dict, changes: dict) -> bool:
    """AT-06.7 — a node's evidence must be re-derived when what it says changes (title/explanation)."""
    norm = lambda v: " ".join(str(v or "").split()).lower()  # noqa: E731
    return any(k in changes and norm(changes[k]) != norm(before.get(k)) for k in ("title", "explanation"))


def depth_of(nodes: list[RawNode]) -> int:
    """AT-05.5 — number of levels below the root (root alone = 0)."""
    parent = {n.ref: n.parent for n in nodes}
    best = 0
    for n in nodes:
        d, cur = 0, n.parent
        while cur is not None and d <= len(nodes):
            d, cur = d + 1, parent.get(cur)
        best = max(best, d)
    return best


def merge_deeper(raw: RawMap, reply: str, default_paper: str = "P1") -> list[RawNode]:
    """AT-05.5 — new nodes from a "deepen" reply; each must hang under an existing or new node. Parent-first."""
    data = extract_json(reply)
    known = {n.ref for n in raw.nodes}
    items = [n for n in (data.get("nodes") or []) if isinstance(n, dict)]
    for i, n in enumerate(items):  # never let a new node overwrite an existing id
        if str(n.get("id")) in known:
            n["id"] = f"d{i}_{n.get('id')}"
    new_refs = {str(n.get("id")) for n in items}
    added: list[RawNode] = []
    pending = items
    while pending:
        progressed, rest = False, []
        for n in pending:
            parent = str(n.get("parent"))
            if parent in known:
                nodes = parse_nodes([{**n, "parent": parent}], default_paper, root_parent=parent)
                added.extend(nodes)
                known.add(nodes[0].ref)
                progressed = True
            elif parent in new_refs:
                rest.append(n)
        if not progressed:
            break
        pending = rest
    return added
