"""US-05 AT-05.4 — OpenRouter client against a mocked HTTP transport (no network, no tokens)."""

import asyncio

import httpx
import pytest

from app.infrastructure.llm import LLMError, OpenRouterClient

OK = {"choices": [{"message": {"content": "hello"}}]}


def run(responses):
    calls, sleeps = [], []

    def handler(request):
        calls.append(request)
        status, body, headers = responses.pop(0)
        return httpx.Response(status, json=body, headers=headers)

    async def sleep(s):
        sleeps.append(s)

    client = OpenRouterClient("key", "https://openrouter.test/api/v1", transport=httpx.MockTransport(handler), sleep=sleep)
    out = asyncio.run(client.complete([{"role": "user", "content": "hi"}], model="m/x", temperature=0.2))
    return out, calls, sleeps


def test_in_flight_402_then_success():
    """AT-05.4 — retried after Retry-After, request carries model + bearer key."""
    out, calls, sleeps = run([(402, {"error": {"metadata": {"reason": "in_flight_budget_exhausted"}}}, {"Retry-After": "5"}),
                              (200, OK, {})])
    assert out == "hello" and sleeps == [5.0] and len(calls) == 2
    assert calls[0].headers["authorization"] == "Bearer key"
    assert b'"model":"m/x"' in calls[0].content.replace(b" ", b"")


def test_out_of_credits_fails_immediately():
    """AT-05.4"""
    with pytest.raises(LLMError, match="402"):
        run([(402, {"error": {"message": "Insufficient credits"}}, {})])


def test_gives_up_after_max_retries():
    """AT-05.4"""
    with pytest.raises(LLMError, match="503"):
        run([(503, {}, {})] * 4)
