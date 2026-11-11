See [.github/copilot-instructions.md](.github/copilot-instructions.md) — load the `paperreader-dev`
skill ([.github/skills/paperreader-dev/SKILL.md](.github/skills/paperreader-dev/SKILL.md)) before any change.

## Development workflow (story-driven)
This repository uses story-driven development (profile: `devflow.yml`). Before ANY change, load the
`story-driven-dev` skill in `.claude/skills/story-driven-dev/` and follow it: pick a US/CR ID first,
write or update the story and its acceptance tests, cite AT IDs in tests, update the logbook, and run
the gate from `devflow.yml` (at least `python3 scripts/check_traceability.py`) before committing.
Never use `--no-verify`.

`ai4academia.yml` describes how AI4Academia builds and runs this tool. Keep `run.port`, `run.health`
and `env` in step with the code: a new environment variable goes into `env` in the same change.
