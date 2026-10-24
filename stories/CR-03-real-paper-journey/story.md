# CR-03 — Real-paper journey test

As the owner, I want an automated end-to-end run of my whole reading workflow on a real arXiv
paper with the real LLM, so that every release is proven on a realistic paper, not only on fixtures.

Runs on demand (`scripts/ci.sh --journey`, ~5–10 min, one map generation on a 15-page paper ≈ a few
cents) — not on every push. The paper (arXiv 1706.03762) is downloaded once into the git-ignored
`tests/fixtures/arxiv/`.

## Acceptance tests
- **AT-C03.1** Given arXiv 1706.03762, the journey (sign in → session → upload → AI map → depth → node ↔ paper traceability → colored highlight with comment → note linked to a node → chat with grounded citations → go deeper → edit node with automatic re-grounding → relation → layout change → reload persists everything → phone view) completes with every AI quote verified on real text — Levels: system

## Main files
- `tests/system/specs/90-journey.spec.js`, `scripts/ci.sh`
