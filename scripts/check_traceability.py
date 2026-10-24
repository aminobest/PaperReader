#!/usr/bin/env python3
"""CR-01 — token-free traceability gate.

Checks (AT-C01.1):
  * every story folder has story.md + logbook.md and is listed in stories/README.md;
  * every acceptance test (AT-xx.k) is cited by at least one test at EVERY level it declares;
  * every user story (US-) is covered by unit, integration and system tests overall;
  * tests never cite an AT that doesn't exist.
With --staged (AT-C01.3): staged code changes must come with a staged story logbook entry.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AT_DEF = re.compile(r"^- \*\*AT-(C?\d+\.\d+)\*\*.*?Levels:\s*([a-z, ]+)\s*$", re.M)
AT_REF = re.compile(r"AT-(C?\d+\.\d+)")
LEVEL_GLOBS = {
    "unit": ["tests/unit/**/*.py", "tests/unit/**/*.mjs", "tests/arch/**/*.py"],
    "integration": ["tests/integration/**/*.py"],
    "system": ["tests/system/specs/**/*.js"],
}
CODE_PREFIXES = ("backend/", "frontend/js/", "frontend/css/", "frontend/index.html", "Dockerfile",
                 "docker-compose.yml", "scripts/")


def load_stories(root: Path) -> tuple[dict[str, dict], list[str]]:
    errors, stories = [], {}
    index = (root / "stories" / "README.md").read_text() if (root / "stories" / "README.md").exists() else ""
    for d in sorted((root / "stories").glob("*-*/")):
        if d.name.startswith("_"):
            continue
        sid = "-".join(d.name.split("-")[:2])
        story, log = d / "story.md", d / "logbook.md"
        if not story.exists():
            errors.append(f"{d.name}: missing story.md")
            continue
        if not log.exists() or "## " not in log.read_text():
            errors.append(f"{d.name}: missing logbook.md or it has no entry")
        if f"[{sid}]" not in index:
            errors.append(f"{sid}: not listed in stories/README.md")
        ats = {m.group(1): {lv.strip() for lv in m.group(2).split(",") if lv.strip()}
               for m in AT_DEF.finditer(story.read_text())}
        if not ats:
            errors.append(f"{sid}: story.md declares no acceptance tests (`- **AT-NN.k** … — Levels: …`)")
        for at, levels in ats.items():
            bad = levels - set(LEVEL_GLOBS)
            if bad:
                errors.append(f"AT-{at}: unknown level(s) {sorted(bad)}")
        stories[sid] = {"ats": ats, "dir": d}
    return stories, errors


def load_citations(root: Path) -> dict[str, dict[str, set[str]]]:
    cites: dict[str, dict[str, set[str]]] = {lv: {} for lv in LEVEL_GLOBS}
    for lv, globs in LEVEL_GLOBS.items():
        for g in globs:
            for f in root.glob(g):
                if "node_modules" in f.parts:
                    continue
                for at in AT_REF.findall(f.read_text()):
                    cites[lv].setdefault(at, set()).add(str(f.relative_to(root)))
    return cites


def check(root: Path = ROOT) -> list[str]:
    stories, errors = load_stories(root)
    cites = load_citations(root)
    known = {at for s in stories.values() for at in s["ats"]}
    for sid, s in stories.items():
        story_levels: set[str] = set()
        for at, levels in s["ats"].items():
            for lv in levels:
                if at in cites[lv]:
                    story_levels.add(lv)
                else:
                    errors.append(f"AT-{at} ({sid}): declared level '{lv}' but no {lv} test cites it")
        if sid.startswith("US-"):
            for lv in LEVEL_GLOBS:
                if not any(at in cites[lv] for at in s["ats"]):
                    errors.append(f"{sid}: has no {lv} test")
    for lv, ats in cites.items():
        for at, files in ats.items():
            if at not in known:
                errors.append(f"AT-{at}: cited by {sorted(files)} but not defined in any story")
    return errors


def staged_errors(files: list[str]) -> list[str]:
    """AT-C01.3 — code changes need a story logbook change in the same commit."""
    code = [f for f in files if f.startswith(CODE_PREFIXES)]
    logs = [f for f in files if re.match(r"stories/[^/]+/logbook\.md$", f)]
    if code and not logs:
        return ["staged code changes without a story logbook entry: update stories/<ID>-*/logbook.md "
                f"(changed: {', '.join(code[:5])}{' …' if len(code) > 5 else ''})"]
    return []


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--staged", action="store_true", help="also require a logbook entry for staged code")
    args = ap.parse_args()
    errors = check()
    if args.staged:
        out = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=ROOT, capture_output=True, text=True)
        errors += staged_errors(out.stdout.split())
    if errors:
        print("TRACEABILITY GATE FAILED:\n  - " + "\n  - ".join(errors))
        return 1
    stories, _ = load_stories(ROOT)
    print(f"traceability ok: {len(stories)} stories, {sum(len(s['ats']) for s in stories.values())} acceptance tests")
    return 0


if __name__ == "__main__":
    sys.exit(main())
