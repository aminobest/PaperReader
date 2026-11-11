[![Listed on AI4Academia](https://ai4academia.tail32bbbc.ts.net/badge.svg)](https://ai4academia.tail32bbbc.ts.net/tools/paperreader)

# PaperReader

Understand research papers fast, even without the background. Upload PDFs into a session; the
AI builds a mind map from the big picture down to the details, **every node backed by verbatim,
machine-verified quotes** that light up in the paper. Annotate in colors, keep notes, and chat
with the AI about any node or passage — answers cite the paper too.

- Use it: https://ubuntu-32gb-hel1-1.tail32bbbc.ts.net/ (tailnet only) — Mac, iPad, iPhone.
- Requirements: [docs/requirements.md](docs/requirements.md) · Stories: [stories/README.md](stories/README.md)
- Architecture: [docs/architecture.md](docs/architecture.md) · Deployment: [docs/deployment.md](docs/deployment.md)
- Development workflow (mandatory): [.github/skills/paperreader-dev/SKILL.md](.github/skills/paperreader-dev/SKILL.md)

## Develop

```bash
python3 -m venv .venv && .venv/bin/pip install -r backend/requirements-dev.txt
(cd tests/system && npm ci)          # Playwright + pdf.js (vendored copy in frontend/vendor)
scripts/install-hooks.sh             # pre-commit: fast gate · pre-push: full gate
scripts/ci.sh --fast                 # lint, traceability, arch, unit (py+js), integration — no tokens
scripts/ci.sh                        # + system tests (Playwright, real LLM on a 2-page fixture)
```

## Using the app
- **Map:** tap a node → its evidence is highlighted in the paper. *Depth* buttons go from big
  picture to details; `+N` unfolds a branch. Desktop keys: Tab child · Enter sibling · F2 edit ·
  Del delete · Space fold · arrows navigate · `f` fit.
- **Paper:** select text → highlight color, *Ask AI*, *Note*, *Link to node*, or jump to the
  related nodes. Tap a highlight to edit it or select its nodes. Layers: Map · AI · Mine.
- **Side panel:** Node (details, edit, *Go deeper*, *Re-find evidence*, relations) · Notes · Chat.
