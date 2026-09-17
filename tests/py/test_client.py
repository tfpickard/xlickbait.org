"""The polite client: spacing, retries, and refusing to hammer arXiv."""

from __future__ import annotations

import httpx
import pytest

from generator.arxiv.client import ArxivClient, ArxivError, RateLimiter


class FakeClock:
    """A monotonic clock that only advances when something sleeps."""

    def __init__(self) -> None:
        self.now = 1000.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds

    def advance(self, seconds: float) -> None:
        self.now += seconds


class TestRateLimiter:
    def test_first_request_does_not_wait(self):
        clock = FakeClock()
        RateLimiter(3.0, clock.monotonic, clock.sleep).wait()
        assert clock.sleeps == []

    def test_spaces_consecutive_requests_by_the_full_interval(self):
        # arXiv: "no more than one request every three seconds". There are no
        # rate-limit headers to react to, so this is the only thing keeping us
        # compliant.
        clock = FakeClock()
        limiter = RateLimiter(3.0, clock.monotonic, clock.sleep)
        limiter.wait()
        limiter.wait()
        limiter.wait()
        assert clock.sleeps == [3.0, 3.0]

    def test_credits_time_already_spent_working(self):
        # If a request took two seconds, only one more is owed -- not three.
        clock = FakeClock()
        limiter = RateLimiter(3.0, clock.monotonic, clock.sleep)
        limiter.wait()
        clock.advance(2.0)
        limiter.wait()
        assert clock.sleeps == [pytest.approx(1.0)]

    def test_does_not_wait_when_enough_time_has_passed(self):
        clock = FakeClock()
        limiter = RateLimiter(3.0, clock.monotonic, clock.sleep)
        limiter.wait()
        clock.advance(10.0)
        limiter.wait()
        assert clock.sleeps == []

    def test_never_sleeps_a_negative_duration(self):
        clock = FakeClock()
        limiter = RateLimiter(3.0, clock.monotonic, clock.sleep)
        limiter.wait()
        clock.advance(100.0)
        limiter.wait()
        assert all(s > 0 for s in clock.sleeps)


def _client(handler, clock: FakeClock, **kwargs) -> ArxivClient:
    transport = httpx.MockTransport(handler)
    return ArxivClient(
        user_agent="test-agent",
        min_interval=3.0,
        client=httpx.Client(transport=transport, headers={"User-Agent": "test-agent"}),
        limiter=RateLimiter(3.0, clock.monotonic, clock.sleep),
        sleep=clock.sleep,
        **kwargs,
    )


class TestArxivClient:
    def test_sends_a_descriptive_user_agent(self):
        seen: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request.headers.get("user-agent", ""))
            return httpx.Response(200, text="<feed/>")

        clock = FakeClock()
        _client(handler, clock).get({"id_list": "2401.01234"})
        assert seen == ["test-agent"]

    def test_batches_identifiers_into_one_request(self):
        # The whole point: fifty candidates cost one request, not fifty. Under
        # the three-second rule that is 3 seconds instead of 150.
        calls: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request)
            return httpx.Response(200, text="<feed/>")

        clock = FakeClock()
        identifiers = [f"2401.{i:05d}" for i in range(1, 51)]
        _client(handler, clock).by_ids(identifiers)

        assert len(calls) == 1
        assert calls[0].url.params["id_list"] == ",".join(identifiers)
        assert clock.sleeps == []  # only one request, so nothing to wait for

    def test_retries_a_500_then_succeeds(self):
        # Over-limit and overload both surface as 500 with a valid Atom body,
        # not as the documented 400.
        attempts = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            attempts["n"] += 1
            if attempts["n"] < 3:
                return httpx.Response(
                    500, text="<feed><entry><id>https://arxiv.org/api/errors</id></entry></feed>"
                )
            return httpx.Response(200, text="<feed/>")

        clock = FakeClock()
        body = _client(handler, clock).get({"id_list": "x"})
        assert body == "<feed/>"
        assert attempts["n"] == 3
        assert 1.0 in clock.sleeps and 2.0 in clock.sleeps  # exponential backoff

    def test_gives_up_after_the_retry_budget(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503, text="overloaded")

        clock = FakeClock()
        with pytest.raises(ArxivError, match="after 3 attempts"):
            _client(handler, clock, max_retries=2).get({"id_list": "x"})

    def test_does_not_retry_a_client_error(self):
        # A 400 means the request is wrong; repeating it just wastes arXiv's time.
        attempts = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            attempts["n"] += 1
            return httpx.Response(400, text="start must be non-negative")

        clock = FakeClock()
        with pytest.raises(ArxivError, match="rejected"):
            _client(handler, clock).get({"start": -1})
        assert attempts["n"] == 1

    def test_refuses_to_page_past_the_real_ceiling(self):
        clock = FakeClock()
        client = _client(lambda r: httpx.Response(200, text="<feed/>"), clock)
        # Documented as 30000; the live ceiling is start + max_results <= 10000,
        # and exceeding it returns 500 rather than a useful error.
        with pytest.raises(ValueError, match="10000"):
            client.search("all:e", max_results=2000, start=9000)
