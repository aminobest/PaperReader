"""US-05/US-10 — OpenRouter chat-completions client (the only place that talks to the LLM API)."""

from __future__ import annotations

import httpx


class LLMError(RuntimeError):
    pass


class OpenRouterClient:
    def __init__(self, api_key: str, base_url: str, timeout: float = 600) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def complete(self, messages: list[dict], *, model: str, temperature: float) -> str:
        if not self.api_key:
            raise LLMError("OPENROUTER_API_KEY is not configured")
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "X-Title": "PaperReader",
                },
                json={"model": model, "messages": messages, "temperature": temperature},
            )
        if resp.status_code >= 400:
            raise LLMError(f"OpenRouter {resp.status_code}: {resp.text[:500]}")
        data = resp.json()
        try:
            return data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"unexpected OpenRouter reply: {str(data)[:500]}") from exc
