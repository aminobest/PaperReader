# Architecture

```
frontend/ (static PWA, no build step)        backend/app/
  js/app.js        router, login, sessions     api/             FastAPI routers (thin) ── deps.py: auth + ownership
  js/workspace.js  map ↔ paper traceability    application/     use cases: map_service, chat_service,
  js/mindmap.js    SVG/HTML mind map                            grounding_service, llm_gateway, jobs, settings
  js/pdfview.js    pdf.js viewer + overlays    domain/          PURE: grounding, mindmap, prompts, rules
  js/panels.js     node / notes / chat         infrastructure/  repo (SQLite), pdf (PyMuPDF), llm (OpenRouter),
  js/*.mjs         pure, unit-tested                            security, config
```

Dependency rule (enforced by `tests/arch`): `domain` ← `application` ← `api`; `infrastructure` is
injected (repo, LLM client) by `main.create_app`. The application layer never does I/O itself.

## Key flows
- **Generate map (US-05):** `POST /sessions/{id}/maps` → job → `map_service.generate_map`:
  render `map_generate` prompt with `[P<n> p.<page>]`-tagged text → parse JSON (`domain.mindmap`,
  one corrective retry) → **ground quotes** → persist nodes/links/quotes → fold to depth 2.
- **Grounding (US-04):** `domain.grounding.locate` matches a quote on a normalised character
  stream of the page words (from PyMuPDF) and returns per-line rects (0..1). Failures go back to
  the LLM via the `quote_fix` prompt, up to `grounding_retries`; leftovers are dropped & reported.
- **Traceability (US-07):** quotes carry `paper_id, page, rects`; the viewer draws them as overlay
  layers (map / AI chat / my annotations). Node → quotes is a lookup; selection → nodes is
  rect overlap (`geometry.mjs`).
- **Jobs:** AI work runs as asyncio tasks recorded in `jobs`; the UI polls `/api/jobs/{id}`.

## Data (`DATA_DIR`, default `/data`)
`paperreader.db` (SQLite, WAL, FK cascades), `papers/<id>.pdf`, `users.json` (seed, imported once).
