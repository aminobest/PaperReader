# US-05 — Mind-map generation

As a reader, I want the AI to build a mind map for one paper or a set of papers, from the big picture down to tiny details, so that I understand the paper quickly even without background.

## Acceptance tests
- **AT-05.1** Given papers, when the prompt is rendered then it uses the editable template and contains every page labelled `[P<n> p.<page>]`; the default template asks for high→low levels, a "background you need" branch and plain-language explanations — Levels: unit
- **AT-05.2** Given LLM JSON, then it becomes a tree (root, branches, details) with kinds, quotes and cross-links resolved by node id; malformed JSON triggers one corrective retry — Levels: unit, integration
- **AT-05.4** Given a transient OpenRouter failure (timeout, 429, 5xx, 402 "in-flight budget"), the call is retried with backoff honouring Retry-After (max 3 retries, ≤ 120 s); a real "out of credits" 402 or a 4xx fails at once with the provider message — Levels: unit, integration
- **AT-05.5** Given a generated map shallower than the minimum depth (Admin, default 3 levels below the centre), the app sends the editable `map_deepen` prompt once and merges the deeper nodes (grounded like all others); a failure there never fails the map — Levels: unit, integration, system
- **AT-05.3** Given a session with papers, when I generate a map for one paper or a selection, then a job runs and the map becomes `ready` (or `failed` with the error) — Levels: integration, system

## Main files
- `backend/app/domain/mindmap.py`
- `backend/app/application/map_service.py`
- `backend/app/domain/prompts.py`
