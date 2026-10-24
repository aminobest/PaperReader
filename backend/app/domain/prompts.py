"""US-11 — default AI prompt templates (editable in Admin; stored in the DB) and their rendering.

Placeholders use `{{name}}`. REQUIRED lists the placeholders a template must keep so the app can
inject its data (AT-11.3).
"""

from __future__ import annotations

import re

_QUOTE_RULES = """QUOTE RULES (strict, they are machine-verified):
- Every quote must be copied VERBATIM from the paper text above: same words, same order.
- One contiguous passage from ONE page, 8 to 40 words. No ellipsis, no paraphrase, no merging of passages.
- Give the paper label and the page number from the [P<n> p.<page>] markers.
- Prefer the sentence that best proves the point; 1-3 quotes per node."""

DEFAULTS: dict[str, dict] = {
    "system": {
        "name": "System persona",
        "description": "Sent as the system message for every AI call.",
        "template": (
            "You are a patient research mentor. You help a smart reader who may lack the background "
            "to understand scientific papers quickly and deeply. You explain in plain language, define "
            "jargon the first time it appears, use concrete intuition, and never invent facts that are "
            "not supported by the paper. You answer with JSON only when asked for JSON."
        ),
    },
    "map_generate": {
        "name": "Generate mind map",
        "description": "Builds the whole mind map for one or more papers.",
        "template": (
            "Build a mind map (a knowledge graph) that lets me understand the paper(s) below.\n\n"
            "MIND-MAP PRINCIPLES\n"
            "- One central node (kind \"topic\"): the core question/contribution in a few words.\n"
            "- 4-7 main branches, from high level to low level, typically: the problem & why it matters, "
            "background you need (prerequisite concepts explained simply), the key idea/method, "
            "results & evidence, limitations & open questions, and (for several papers) how they relate.\n"
            "- Go deeper level by level down to the tiny details (numbers, datasets, equations' meaning, "
            "design choices). Depth 3-5. Each level must be more specific than its parent.\n"
            "- Titles are short keywords (max ~8 words). The explanation (1-3 sentences) is plain language "
            "for a newcomer: what it is and why it matters here.\n"
            "- kind is one of: topic, question, background, definition, method, result, evidence, "
            "limitation, insight, detail.\n"
            "- Add cross-links between related nodes in different branches (e.g. \"addresses\", "
            "\"is evidence for\", \"depends on\", \"contrasts with\").\n\n"
            + _QUOTE_RULES + "\n\n"
            "Reply with JSON only:\n"
            "{\"title\": str, \"nodes\": [{\"id\": \"n1\", \"parent\": null | \"n<k>\", \"title\": str, "
            "\"explanation\": str, \"kind\": str, \"quotes\": [{\"paper\": \"P1\", \"page\": int, \"text\": str}]}], "
            "\"links\": [{\"from\": \"n<a>\", \"to\": \"n<b>\", \"label\": str}]}\n"
            "List parents before their children.\n\n"
            "PAPERS\n{{papers}}"
        ),
    },
    "node_expand": {
        "name": "Expand node deeper",
        "description": "Adds more detailed child nodes under one node.",
        "template": (
            "In the mind map of the paper(s) below, expand this node one or two levels deeper with the "
            "finer details a newcomer needs (mechanisms, definitions, numbers, examples). Do not repeat "
            "existing children.\n\nNODE PATH: {{node_path}}\nNODE: {{node}}\nEXISTING CHILDREN: "
            "{{existing_children}}\n\n" + _QUOTE_RULES + "\n\n"
            "Reply with JSON only: {\"nodes\": [{\"id\": \"c1\", \"parent\": null | \"c<k>\", \"title\": str, "
            "\"explanation\": str, \"kind\": str, \"quotes\": [{\"paper\": \"P1\", \"page\": int, \"text\": str}]}]} "
            "where parent null means a direct child of the node.\n\nPAPERS\n{{papers}}"
        ),
    },
    "node_reground": {
        "name": "Re-ground node",
        "description": "Finds the supporting quotes for a (possibly edited) node.",
        "template": (
            "Find the passages of the paper(s) below that best support or explain this mind-map node.\n\n"
            "NODE PATH: {{node_path}}\nNODE: {{node}}\n\n" + _QUOTE_RULES + "\n\n"
            "Reply with JSON only: {\"quotes\": [{\"paper\": \"P1\", \"page\": int, \"text\": str}]}\n\n"
            "PAPERS\n{{papers}}"
        ),
    },
    "chat": {
        "name": "Chat",
        "description": "Answers questions about selected nodes or a passage.",
        "template": (
            "Help me understand the following part of the paper(s). Explain simply, build intuition, "
            "define jargon, and relate it to the big picture.\n\nFOCUS\n{{context}}\n\n"
            "Ground your answer in the paper: cite evidence with markers [1], [2] … in the text and list "
            "the quotes.\n" + _QUOTE_RULES + "\n\n"
            "Reply with JSON only: {\"answer\": \"markdown with [n] markers\", \"quotes\": [{\"n\": 1, "
            "\"paper\": \"P1\", \"page\": int, \"text\": str}]}\n\nPAPERS\n{{papers}}"
        ),
    },
    "quote_fix": {
        "name": "Fix quotes (grounding retry)",
        "description": "Sent back when quotes were not found verbatim in the paper.",
        "template": (
            "These quotes were NOT found verbatim in the paper text, so they were rejected:\n{{failures}}\n\n"
            "For each ref, copy the correct passage EXACTLY from the paper text (8-40 words, one page, no "
            "ellipsis), or null if none exists. Reply with JSON only: "
            "{\"fixes\": [{\"ref\": str, \"paper\": \"P1\", \"page\": int, \"text\": str | null}]}"
        ),
    },
    "json_fix": {
        "name": "Fix JSON (format retry)",
        "description": "Sent back when the reply was not valid JSON for the expected shape.",
        "template": "Your previous reply could not be used: {{error}}. Reply again with the JSON only, exactly in the requested shape.",
    },
}

REQUIRED: dict[str, tuple[str, ...]] = {
    "system": (),
    "map_generate": ("papers",),
    "node_expand": ("papers", "node_path", "node", "existing_children"),
    "node_reground": ("papers", "node_path", "node"),
    "chat": ("papers", "context"),
    "quote_fix": ("failures",),
    "json_fix": ("error",),
}

_PLACEHOLDER = re.compile(r"\{\{\s*(\w+)\s*\}\}")


class TemplateError(ValueError):
    pass


def validate_template(key: str, template: str) -> None:
    """AT-11.3 — unknown key or a missing required placeholder is rejected."""
    if key not in DEFAULTS:
        raise TemplateError(f"unknown prompt key {key!r}")
    if not template.strip():
        raise TemplateError("template must not be empty")
    present = set(_PLACEHOLDER.findall(template))
    missing = [p for p in REQUIRED[key] if p not in present]
    if missing:
        raise TemplateError("missing placeholder(s): " + ", ".join("{{%s}}" % m for m in missing))


def render(template: str, **values: str) -> str:
    return _PLACEHOLDER.sub(lambda m: str(values.get(m.group(1), m.group(0))), template)
