"""US-05 AT-05.4 — which OpenRouter failures are retried, and how long to wait."""

from app.infrastructure.llm import MAX_DELAY, retry_delay


def test_transient_failures_are_retried_with_backoff():
    """AT-05.4"""
    assert retry_delay(429, {}, "", 0) == 2.0
    assert retry_delay(503, {}, "", 1) == 4.0
    assert retry_delay(402, {"retry-after": "30"}, '{"reason":"in_flight_budget_exhausted"}', 0) == 30.0
    assert retry_delay(429, {"retry-after": "9999"}, "", 0) == MAX_DELAY


def test_permanent_failures_and_exhausted_retries_are_not_retried():
    """AT-05.4"""
    assert retry_delay(402, {}, '{"message":"Insufficient credits"}', 0) is None
    assert retry_delay(401, {}, "expired", 0) is None
    assert retry_delay(400, {}, "bad model", 0) is None
    assert retry_delay(429, {}, "", 3) is None
