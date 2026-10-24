"""US-11 AT-11.4 — every LLM call goes through here: uses current settings, logs prompt+reply."""

from __future__ import annotations

import time

from app.application.settings import effective_settings, prompt


class LLMGateway:
    def __init__(self, repo, client, default_model: str | None = None) -> None:
        self.repo = repo
        self.client = client
        self.default_model = default_model

    def system_message(self) -> dict:
        return {"role": "system", "content": prompt(self.repo, "system")}

    async def ask(self, kind: str, messages: list[dict]) -> str:
        s = effective_settings(self.repo, self.default_model)
        start = time.monotonic()
        reply, error = None, None
        try:
            reply = await self.client.complete(messages, model=s["model"], temperature=s["temperature"])
            return reply
        except Exception as exc:
            error = str(exc)
            raise
        finally:
            self.repo.log_ai(kind=kind, model=s["model"], messages=messages, response=reply,
                             duration_ms=int((time.monotonic() - start) * 1000), error=error)
