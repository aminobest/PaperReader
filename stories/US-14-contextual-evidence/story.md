# US-14 — Contextual evidence

As a reader, I want each map node and chat citation to use complete, context-rich passages
that directly support the idea, so that the evidence helps me understand the paper instead
of merely highlighting a few matching words.

## Acceptance tests
- **AT-14.1** Given an AI-generated evidence quote, then it is one verbatim, contiguous passage from one page with enough context to explain a complete thought; the application imposes no word-count limit — Levels: unit, integration, system
- **AT-14.2** Given a node or answer with substantive claims, the prompt asks for directly supporting, non-redundant passages and rejects keyword-only evidence; if no suitable passage exists, it may return no quote — Levels: unit, system
- **AT-14.3** Given a claim requiring evidence, the model chooses the number of passages needed; the application imposes no quote-count target or cap — Levels: unit, integration, system
- **AT-14.4** Given a quote correction retry, it preserves a complete contextual passage and does not shorten it to a fragment to force a match; passage length remains the model's choice — Levels: unit, integration

## Main files
- `backend/app/domain/prompts.py` — quote-selection rules in generation, expansion, re-grounding, chat and quote-fix prompts
- `backend/app/domain/grounding.py`, `backend/app/application/grounding_service.py` — exact quote verification
