"""Unit tests for pure rules, prompts and security (US-01, 02, 03, 05, 08, 09, 10, 11)."""

import pytest

from app.domain import prompts
from app.domain.grounding import PageIndex, PaperIndex, Word
from app.domain.rules import (ValidationError, chat_context, clean_name, default_paper_title, link_citations,
                              note_title, papers_block, validate_annotation)
from app.infrastructure.security import hash_password, make_token, read_token, verify_password




def test_plans_tracker_hash_format_verifies():
    """AT-01.1 — pbkdf2_sha256$iter$salt$digest (urlsafe b64, no padding) as written by plansTracker."""
    h = hash_password("s3cret-pass", iterations=1000)
    assert h.startswith("pbkdf2_sha256$1000$")
    assert verify_password("s3cret-pass", h)
    assert not verify_password("wrong", h)
    assert not verify_password("x", "garbage")


def test_session_token_roundtrip_and_tamper():
    """AT-01.1 — signed cookie tokens."""
    t = make_token("k", "u1")
    assert read_token("k", t) == "u1"
    assert read_token("other", t) is None
    assert read_token("k", t[:-2] + "xx") is None


def test_blank_session_name_rejected():
    """AT-02.1"""
    assert clean_name("  Reading group ") == "Reading group"
    with pytest.raises(ValidationError):
        clean_name("   ")


@pytest.mark.parametrize("meta, fname, expected", [
    ("Attention Is All You Need", "x.pdf", "Attention Is All You Need"),
    ("", "my_paper_2024.pdf", "my paper 2024"),
    ("paper.dvi", "real.pdf", "real"),
    (None, "/tmp/a/b.pdf", "b"),
])
def test_default_paper_title(meta, fname, expected):
    """AT-03.5"""
    assert default_paper_title(meta, fname) == expected


def test_papers_block_labels_every_page():
    """AT-05.1 — every page tagged [P<n> p.<page>]."""
    p = PaperIndex("id", "P2", "Title", [PageIndex(1, [Word(0, 0, 1, 1, "hello", "0.0")]),
                                         PageIndex(2, [Word(0, 0, 1, 1, "world", "0.0")])])
    text = papers_block([p])
    assert "=== P2: Title ===" in text and "[P2 p.1]\nhello" in text and "[P2 p.2]\nworld" in text


def test_map_prompt_renders_from_template():
    """AT-05.1 — the (editable) template is rendered with the papers block."""
    out = prompts.render(prompts.DEFAULTS["map_generate"]["template"], papers="[P1 p.1]\nxyz")
    assert "[P1 p.1]\nxyz" in out and "{{" not in out


@pytest.mark.parametrize("color, rects, ok", [
    ("yellow", [[0.1, 0.1, 0.2, 0.2]], True),
    ("purple", [[0.1, 0.1, 0.2, 0.2]], False),
    ("green", [], False),
    ("green", [[0.1, 0.1, 1.5, 0.2]], False),
    ("green", [[0.3, 0.1, 0.2, 0.2]], False),
])
def test_annotation_validation(color, rects, ok):
    """AT-08.3"""
    if ok:
        validate_annotation(color, rects)
    else:
        with pytest.raises(ValidationError):
            validate_annotation(color, rects)


def test_note_title_from_first_line():
    """AT-09.3"""
    assert note_title("", "\n\n# My idea\nmore") == "My idea"
    assert note_title(" Given ", "body") == "Given"
    assert note_title(None, "") == "Untitled note"


def test_chat_focus_contains_node_path_and_passage():
    """AT-10.4"""
    ctx = chat_context(None, [{"title": "Gate", "kind": "method", "path": "GMN > Method > Gate", "explanation": "decides"}],
                       "selected words")
    assert "Path: GMN > Method > Gate" in ctx and "Explanation: decides" in ctx and '"selected words"' in ctx


def test_citations_link_kept_and_drop_unverified():
    """AT-10.2 — [n] → [[q:id|n]] for kept quotes; markers of dropped quotes vanish."""
    assert link_citations("A [1] and B [2].", {1: "q9"}) == "A [[q:q9|1]] and B ."


def test_template_missing_placeholder_rejected():
    """AT-11.3"""
    prompts.validate_template("chat", "{{papers}} {{context}}")
    with pytest.raises(prompts.TemplateError, match="context"):
        prompts.validate_template("chat", "only {{papers}}")
    with pytest.raises(prompts.TemplateError):
        prompts.validate_template("nope", "x")


def test_every_default_template_is_valid():
    """AT-11.3 — shipped defaults satisfy their own placeholder contract."""
    for key, d in prompts.DEFAULTS.items():
        prompts.validate_template(key, d["template"])
