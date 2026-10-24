"""US-05/06/10 — long AI operations run as background jobs the UI polls (works on flaky mobile links)."""

from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable

from app.domain.ids import now

log = logging.getLogger("paperreader.jobs")


class JobRunner:
    def __init__(self, repo) -> None:
        self.repo = repo
        self._tasks: set[asyncio.Task] = set()

    def recover(self) -> None:
        """Jobs interrupted by a restart can never finish: mark them failed."""
        for j in self.repo.query("SELECT id, kind, target_id FROM jobs WHERE status IN ('queued','running')"):
            self.repo.update("jobs", j["id"], status="failed", error="interrupted by a server restart", updated_at=now())
            if j["kind"] == "map_generate":
                self.repo.update("maps", j["target_id"], status="failed", error="interrupted by a server restart")

    def start(self, *, user_id: str, session_id: str, kind: str, target_id: str,
              work: Callable[[], Awaitable[dict]], on_fail: Callable[[str], None] | None = None) -> dict:
        job = self.repo.insert("jobs", user_id=user_id, session_id=session_id, kind=kind, target_id=target_id,
                               status="queued", created_at=now(), updated_at=now())
        task = asyncio.get_running_loop().create_task(self._run(job["id"], work, on_fail))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return job

    async def _run(self, job_id: str, work, on_fail) -> None:
        self.repo.update("jobs", job_id, status="running", updated_at=now())
        try:
            report = await work()
        except Exception as exc:  # noqa: BLE001 — any failure is reported to the user
            log.exception("job %s failed", job_id)
            self.repo.update("jobs", job_id, status="failed", error=str(exc)[:1000], updated_at=now())
            if on_fail:
                on_fail(str(exc)[:1000])
        else:
            self.repo.update("jobs", job_id, status="done", report=report, updated_at=now())

    async def drain(self) -> None:
        """Test helper: wait for all running jobs."""
        while self._tasks:
            await asyncio.gather(*list(self._tasks), return_exceptions=True)
