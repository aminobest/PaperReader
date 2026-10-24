"""US-04 AT-04.3/04.4 — grounding loop: verify quotes, ask the LLM to fix failures, drop the rest."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Awaitable, Callable

from app.domain.grounding import Located, PaperIndex, QuoteError, locate
from app.domain.mindmap import MapFormatError, extract_json, parse_quotes
from app.domain.prompts import render


@dataclass
class Candidate:
    ref: str
    paper: str  # label "P1"
    page: int | None
    text: str
    context: str = ""  # e.g. node title, shown to the LLM when asking for a fix


@dataclass
class GroundResult:
    located: dict[str, Located] = field(default_factory=dict)
    dropped: list[dict] = field(default_factory=list)
    fix_rounds: int = 0

    def report(self) -> dict:
        return {"quotes_verified": len(self.located), "quotes_dropped": len(self.dropped),
                "fix_rounds": self.fix_rounds, "dropped": self.dropped[:30]}


Fixer = Callable[[list[tuple[Candidate, str]]], Awaitable[dict[str, Candidate | None]]]


def _try_locate(c: Candidate, papers: dict[str, PaperIndex]) -> Located:
    paper = papers.get(c.paper)
    order = [paper] if paper else []
    order += [p for p in papers.values() if p is not paper]
    last: QuoteError | None = None
    for p in order:
        try:
            return locate(c.text, p, c.page if p is paper else None)
        except QuoteError as exc:
            last = exc
            if "not found" not in str(exc):
                break  # shape errors (too short, ellipsis) don't depend on the paper
    raise last or QuoteError("no papers")


async def ground(cands: list[Candidate], papers: dict[str, PaperIndex], fixer: Fixer | None,
                 retries: int) -> GroundResult:
    res = GroundResult()
    pending = list(cands)
    attempt = 0
    while pending:
        failures: list[tuple[Candidate, str]] = []
        for c in pending:
            try:
                res.located[c.ref] = _try_locate(c, papers)
            except QuoteError as exc:
                failures.append((c, str(exc)))
        if not failures:
            break
        if attempt >= retries or fixer is None:
            res.dropped += [{"ref": c.ref, "context": c.context, "text": c.text, "reason": r} for c, r in failures]
            break
        attempt += 1
        res.fix_rounds = attempt
        fixes = await fixer(failures)
        pending = []
        for c, reason in failures:
            fixed = fixes.get(c.ref)
            if fixed is None:
                res.dropped.append({"ref": c.ref, "context": c.context, "text": c.text,
                                    "reason": reason + "; no fix offered"})
            else:
                pending.append(fixed)
    return res


def llm_fixer(gateway, conversation: list[dict], quote_fix_template: str) -> Fixer:
    """Continue `conversation` (which contains the paper text) asking for corrected quotes."""
    async def fix(failures: list[tuple[Candidate, str]]) -> dict[str, Candidate | None]:
        listing = "\n".join(
            f'- ref "{c.ref}" (about: {c.context}) [{c.paper} p.{c.page}]: "{c.text}" -> {reason}'
            for c, reason in failures)
        ask = {"role": "user", "content": render(quote_fix_template, failures=listing)}
        reply = await gateway.ask("quote_fix", conversation + [ask])
        conversation.extend([ask, {"role": "assistant", "content": reply}])
        try:
            items = extract_json(reply).get("fixes") or []
        except MapFormatError:
            return {}
        by_ref = {c.ref: c for c, _ in failures}
        out: dict[str, Candidate | None] = {}
        for item in items:
            if not isinstance(item, dict) or str(item.get("ref")) not in by_ref:
                continue
            orig = by_ref[str(item["ref"])]
            q = parse_quotes([item], orig.paper)
            out[orig.ref] = replace(orig, paper=q[0].paper, page=q[0].page, text=q[0].text) if q else None
        return out
    return fix
