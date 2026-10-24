"""US-05/US-10 — OpenRouter chat-completions client (the only place that talks to the LLM API)."""

from __future__ import annotations

import asyncio

import httpx

RETRY_STATUSES = {408, 429, 500, 502, 503, 504}
MAX_RETRIES = 3
MAX_DELAY = 120.0


class LLMError(RuntimeError):
    pass


def retry_delay(status: int, headers, body: str, attempt: int) -> float | None:
    """AT-05.4 — seconds to wait before retrying a transient failure, or None if it must not be retried.

    Transient: timeouts, rate limits, 5xx, and the 402 "in-flight budget" limit (credits are
    temporarily reserved by running requests). A plain 402 "out of credits" is not retried.
    """
    if attempt >= MAX_RETRIES:
        return None
    transient = status in RETRY_STATUSES or (status == 402 and "in_flight" in body)
    if not transient:
        return None
    try:
        hinted = float(headers.get("retry-after", ""))
    except ValueError:
        hinted = 0.0
    return min(MAX_DELAY, max(hinted, 2.0 * 2 ** attempt))


class OpenRouterClient:
    def __init__(self, api_key: str, base_url: str, timeout: float = 600, transport=None, sleep=asyncio.sleep) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._transport = transport
        self._sleep = sleep

    async def complete(self, messages: list[dict], *, model: str, temperature: float) -> str:
        if not self.api_key:
            raise LLMError("OPENROUTER_API_KEY is not configured")
        async with httpx.AsyncClient(timeout=self.timeout, transport=self._transport) as client:
            attempt = 0
            while True:
                resp = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}", "X-Title": "PaperReader"},
                    json={"model": model, "messages": messages, "temperature": temperature},
                )
                if resp.status_code < 400:
                    break
                delay = retry_delay(resp.status_code, resp.headers, resp.text, attempt)
                if delay is None:
                    raise LLMError(f"OpenRouter {resp.status_code}: {resp.text[:500]}")
                attempt += 1
                await self._sleep(delay)
        data = resp.json()
        try:
            return data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"unexpected OpenRouter reply: {str(data)[:500]}") from exc
