# Setup and project infrastructure

Read this when: setting up a project (only after the user said yes), or editing Dockerfile,
compose files, `.env.example`, git hooks or the remote CI workflow.

Contents: 1. Bootstrap steps · 2. Docker · 3. Gate, hooks and CI · 4. Agent pointer

## 1. Bootstrap steps

Fill everything from what the repo already uses. Unknown path or command → ask; don't invent.

1. **Profile** — create `devflow.yml` from `assets/devflow.example.yml`.
2. **Stories** — create `stories/README.md` (table `| ID | Title | Status |`, status
   `active` or `dropped`) and `stories/_template/` from `assets/story.md` and `assets/logbook.md`.
3. **Standing stories** — `CR-00-maintenance` (logbook only, for tiny edits) and
   `CR-01-baseline` describing what already exists, so the gate passes from day one.
   Existing tests may stay uncited until a story touches them.
4. **Layers** — create only `logic/`, `models/` and `main` for a new project; add `data/` and
   `presentation/` with the first story that needs them. Set up the arch check
   (`references/architecture.md`). Existing code that breaks the layer rules → record each
   violation in the arch tool's baseline. The baseline only shrinks: one CR at a time
   removes entries, and adding one needs the user's approval. New code follows the rules.
5. **Docker** — add the files in §2, a health check, and `.env` in `.gitignore`. Verify that
   `docker compose up --build` starts the app and the health check passes.
6. **Admin view + issue reporter** — UI project: build them from the standard stories in
   `references/issue-reporter.md` (US-01/US-02 in a new project, next free numbers
   otherwise). No UI: add the `report-issue` command. Create `issues/` and **commit it to
   git** (owner's policy); the reporter tells users not to include sensitive data.
7. **Gate** — copy the bundled `scripts/check_traceability.py`, `scripts/ci.sh` and
   `scripts/install-hooks.sh`; run `install-hooks.sh`; add the remote CI workflow (§3).
8. **Pointer** — add the snippet in §4 to `AGENTS.md` and/or `CLAUDE.md`.
9. **Prove it** — run the full gate once and show the user the result.

## 2. Docker

Every project runs in Docker from its first commit, small tools and CLIs included. — same
environment on every machine; what you test is what you ship.

| File | Purpose |
|---|---|
| `Dockerfile` | Multi-stage: `dev` stage with compilers/test tools (fast gate runs here), small runtime stage (shipped) |
| `.dockerignore` | Excludes `.git`, dependency folders, local data, `.env`, test output |
| `compose.yaml` | App + its services (DB, cache…) for dev and deploy; app uses `image: app:${APP_TAG}`; bind-mounts `./issues:/app/issues` |
| `compose.test.yaml` | Same image with test settings: own DB/volume, own ports, fixture data and test accounts, a throwaway `issues/` |
| `.env.example` | Every config variable with safe dummy values; the real `.env` is git-ignored |

Rules:

1. Config comes from environment variables, read only in `main`. Nothing hard-coded per environment.
2. No secrets in the image, Dockerfile, compose files or git — use `.env` or the platform's secret store.
3. Pin versions: exact base image tags (`python:3.12.7-slim`, never `latest`), dependencies from a lockfile.
4. Run as a non-root user. The `issues/` bind mount must be writable by that user: build the
   image with the host's UID/GID (build args) or set `user:` in `compose.yaml`.
5. Containers are disposable: data that must survive (DB, uploads) lives in named volumes.
6. Every service has a health check (`/health` endpoint, or a check command for CLIs);
   dependants use `depends_on: condition: service_healthy`.
7. Logs go to stdout/stderr, never to files in the container.
8. Build once: the full gate builds `app:<git-sha>` (same SHA format as `deploy`), tests it,
   and deploy uses that tag with `--no-build`.
   Never rebuild differently for production. Deploying to another machine → push the tested
   `app:<git-sha>` to a registry and pull that exact tag there.
9. Docker changes are CR stories with logbook entries, like any change.
10. A new config variable → add it to `.env.example` in the same change.

```bash
docker compose up --build                                  # run locally
docker compose logs -f app                                 # follow logs
docker compose down                                        # stop (volumes kept)
docker compose -f compose.test.yaml up --build -d --wait   # start test env
docker compose -f compose.test.yaml down -v                # stop, delete test data
```

Production on another machine → copy its `issues/` back (e.g. `rsync`) before working on reports.

## 3. Gate, hooks and CI

- `scripts/ci.sh --fast`: lint, architecture, traceability, unit, integration.
  Integration needs a real DB → run the fast gate in a `dev` compose service built from the
  Dockerfile's `dev` stage (`docker compose run --rm dev scripts/ci.sh --fast`), or list
  host prerequisites in the profile's `gate.fast` comment.
- `scripts/ci.sh`: fast + `docker build -t app:<git-sha>` + `compose.test.yaml` up +
  system tests + `live` level when `levels.live.enabled: true`.
- `scripts/install-hooks.sh` installs: pre-commit → fast gate; commit-msg → subject starts
  with an existing story ID and that story's `logbook.md` is staged; pre-push → full gate.
- Remote CI runs the **same** `scripts/ci.sh --no-live` on every push. — local hooks can be
  bypassed; CI is the backstop. Live runs only in the pre-push hook, so tokens are spent once.
- Live tests need real keys: provide them only via the local `.env`, never in git.

## 4. Agent pointer (paste into AGENTS.md / CLAUDE.md)

```markdown
## Development workflow
This repo uses story-driven development (profile: `devflow.yml`). Before ANY change,
load the `story-driven-dev` skill and follow it: pick a US/CR ID first, write or update
the story and its acceptance tests, cite AT IDs in tests, update the logbook, and pass
`scripts/ci.sh --fast` before committing. Never use `--no-verify`.
```
