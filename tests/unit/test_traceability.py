"""CR-01 — the traceability gate itself is tested (on a synthetic repo in tmp_path)."""

from pathlib import Path

import check_traceability as ct


def make_repo(tmp: Path, *, with_log=True, cite_system=True, extra_cite=""):
    s = tmp / "stories" / "US-01-x"
    s.mkdir(parents=True)
    (s / "story.md").write_text("# US-01\n## Acceptance tests\n- **AT-01.1** Given … — Levels: unit, integration, system\n")
    if with_log:
        (s / "logbook.md").write_text("# log\n## 2026-01-01 — created\n")
    (tmp / "stories" / "README.md").write_text("| [US-01](US-01-x/story.md) |")
    for d, name, body in [("tests/unit", "test_a.py", "AT-01.1" + extra_cite), ("tests/integration", "test_b.py", "AT-01.1"),
                          ("tests/system/specs", "a.spec.js", "AT-01.1" if cite_system else "")]:
        (tmp / d).mkdir(parents=True, exist_ok=True)
        (tmp / d / name).write_text(body)
    return tmp


def test_gate_passes_on_consistent_repo(tmp_path):
    """AT-C01.1"""
    assert ct.check(make_repo(tmp_path)) == []


def test_gate_fails_on_uncovered_level(tmp_path):
    """AT-C01.1 — declared 'system' but no system test cites the AT."""
    errs = ct.check(make_repo(tmp_path, cite_system=False))
    assert any("no system test cites it" in e for e in errs)


def test_gate_fails_on_unknown_at(tmp_path):
    """AT-C01.1 — a test cites an AT that no story defines."""
    unknown = "AT-" + "99.1"  # built at runtime so this file doesn't itself cite an unknown AT
    errs = ct.check(make_repo(tmp_path, extra_cite=" " + unknown))
    assert any(unknown in e for e in errs)


def test_gate_fails_without_logbook(tmp_path):
    """AT-C01.1"""
    errs = ct.check(make_repo(tmp_path, with_log=False))
    assert any("logbook" in e for e in errs)


def test_staged_code_requires_logbook():
    """AT-C01.3"""
    assert ct.staged_errors(["backend/app/main.py"])
    assert ct.staged_errors(["backend/app/main.py", "stories/US-01-x/logbook.md"]) == []
    assert ct.staged_errors(["docs/requirements.md"]) == []
