"""US-04/US-14 — quote matching, contextual passage checks and retry loop; no I/O or tokens."""

import asyncio

import pytest

from app.application.grounding_service import Candidate, ground
from app.domain.grounding import PageIndex, PaperIndex, QuoteError, Word, locate


def page(no, lines):
    words = []
    for li, line in enumerate(lines):
        x = 0.1
        for w in line.split():
            words.append(Word(x, 0.1 + li * 0.03, x + 0.05, 0.12 + li * 0.03, w, f"0.{li}"))
            x += 0.06
    return PageIndex(page=no, words=words)


PAPER = PaperIndex("pid", "P1", "T", [
    page(1, ["Short texts carry little context which makes them", "hard to classify for recurrent repre-",
             "sentations of the ﬁnal layer."]),
    page(2, ["The gate is a sigmoid unit computed from the current query and the memory summary."]),
])


def test_quote_found_despite_case_whitespace_punctuation():
    """AT-04.1/AT-14.1 — contextual 18-word passage, normalization, page and rects."""
    loc = locate("short TEXTS carry   little context, which makes them hard to classify for recurrent representations of the final layer!", PAPER)
    assert loc.page == 1 and loc.paper_id == "pid"
    assert len(loc.rects) == 3
    assert all(0 <= v <= 1 for r in loc.rects for v in r)


def test_quote_found_across_line_break_hyphenation_and_ligature():
    """AT-04.1 — longer contextual passages still normalize hyphenation and ligatures."""
    loc = locate("Short texts carry little context which makes them hard to classify for recurrent representations of the final layer", PAPER)
    assert loc.page == 1 and len(loc.rects) == 3


def test_page_hint_is_only_a_hint():
    """AT-04.1 — a wrong page number does not prevent locating the quote."""
    assert locate("The gate is a sigmoid unit computed from the current query and the memory summary", PAPER, page_hint=1).page == 2


@pytest.mark.parametrize("bad, reason", [
    ("The gate is a softmax unit computed from the current query and the memory summary here", "not found"),
    ("", "empty quote"),
    ("Short texts carry ... hard to classify", "ellipsis"),
])
def test_invalid_quotes_fail(bad, reason):
    """AT-04.2 — absent, empty, or elided quotes are rejected."""
    with pytest.raises(QuoteError, match=reason):
        locate(bad, PAPER)


def test_short_verbatim_passage_is_not_rejected_by_a_word_count_rule():
    """AT-14.1 — grounding verifies exact source text without imposing a passage-length limit."""
    loc = locate("The gate is a sigmoid", PAPER)
    assert loc.page == 2 and loc.text == "The gate is a sigmoid"


def test_failed_quotes_are_sent_for_fixing_and_accepted_when_corrected():
    """AT-04.3/AT-14.4 — a failed quote is retried without fragmenting the replacement passage."""
    calls = []

    async def fixer(failures):
        calls.append([c.ref for c, _ in failures])
        return {c.ref: Candidate(c.ref, "P1", 2,
                                 "The gate is a sigmoid unit computed from the current query and the memory summary.")
                for c, _ in failures}

    cands = [Candidate("a", "P1", 1, "Short texts carry little context which makes them hard to classify for recurrent representations of the final layer."),
             Candidate("b", "P1", 2, "The gate is a softmax unit computed from the current query and the memory summary here.")]
    res = asyncio.run(ground(cands, {"P1": PAPER}, fixer, retries=2))
    assert calls == [["b"]]
    assert set(res.located) == {"a", "b"} and res.dropped == [] and res.fix_rounds == 1


def test_still_failing_quotes_are_dropped_after_retries():
    """AT-04.4 — after `retries` rounds the quote is dropped and reported."""
    rounds = []

    async def fixer(failures):
        rounds.append(1)
        return {c.ref: Candidate(c.ref, "P1", 1, "an invented sentence that is not in the paper") for c, _ in failures}

    res = asyncio.run(ground([Candidate("x", "P1", 1, "totally made up evidence sentence here")],
                             {"P1": PAPER}, fixer, retries=2))
    assert len(rounds) == 2
    assert res.located == {} and len(res.dropped) == 1 and res.report()["quotes_dropped"] == 1


def test_zero_retries_drops_immediately():
    """AT-04.4 — with grounding_retries = 0 no fix is requested."""
    res = asyncio.run(ground([Candidate("x", "P1", 1, "totally made up evidence sentence here")],
                             {"P1": PAPER}, None, retries=0))
    assert res.fix_rounds == 0 and len(res.dropped) == 1
