"""One polite arXiv client.

arXiv's Terms of Use, verbatim: "make no more than one request every three
seconds, and limit requests to a single connection at a time" -- and the limit
"appl[ies] to all of the machines under your control as a whole".

There are no rate-limit response headers to react to, so this self-governs: a
monotonic clock gate on request *starts*, one connection, exponential backoff on
transport errors and 5xx.

Two things that would otherwise bite:

* `https://export.arxiv.org/robots.txt` is `Disallow: /`. The Terms of Use
  explicitly permit programmatic API use -- that file is aimed at crawlers -- but
  an HTTP layer configured to honour robots.txt would refuse to fetch at all.
  Nothing here consults it.
* Over-limit requests return HTTP 500 with a valid Atom error feed, not the
  documented 400, so status alone cannot distinguish "bad request" from
  "transient". Retries are bounded and the body is surfaced on give-up.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

import httpx

from generator.config import ARXIV_API_URL


class ArxivError(RuntimeError):
    """An arXiv request failed in a way retrying did not fix."""


@dataclass
class RateLimiter:
    """Enforces a minimum interval between request starts.

    The clock and sleep are injected so the spacing is directly testable without
    a test suite that actually waits three seconds per request.
    """

    min_interval: float
    monotonic: Callable[[], float] = time.monotonic
    sleep: Callable[[float], None] = time.sleep
    _last_start: float | None = None

    def wait(self) -> None:
        now = self.monotonic()
        if self._last_start is not None:
            elapsed = now - self._last_start
            remaining = self.min_interval - elapsed
            if remaining > 0:
                self.sleep(remaining)
                now = self.monotonic()
        self._last_start = now


class ArxivClient:
    """A single-connection, rate-limited arXiv API client."""

    def __init__(
        self,
        *,
        user_agent: str,
        min_interval: float,
        max_retries: int = 3,
        client: httpx.Client | None = None,
        limiter: RateLimiter | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        # max_connections=1 makes "a single connection at a time" a property of
        # the transport rather than a promise in a comment.
        self._client = client or httpx.Client(
            headers={"User-Agent": user_agent},
            timeout=httpx.Timeout(30.0),
            limits=httpx.Limits(max_connections=1, max_keepalive_connections=1),
            follow_redirects=True,
        )
        self._limiter = limiter or RateLimiter(min_interval=min_interval)
        self._max_retries = max_retries
        self._sleep = sleep

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> ArxivClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def get(self, params: dict[str, str | int]) -> str:
        """Perform one rate-limited query, returning the Atom body."""
        last_error: str = "no attempts made"
        for attempt in range(self._max_retries + 1):
            self._limiter.wait()
            try:
                response = self._client.get(ARXIV_API_URL, params=params)
            except httpx.HTTPError as exc:
                last_error = f"transport error: {exc}"
            else:
                if response.status_code == 200:
                    return response.text
                # 500 is what an over-limit or overloaded request returns, and it
                # carries a valid Atom error feed rather than a transport failure.
                last_error = f"HTTP {response.status_code}: {response.text[:300]}"
                if response.status_code < 500 and response.status_code != 429:
                    raise ArxivError(f"arXiv rejected the request -- {last_error}")

            if attempt < self._max_retries:
                self._sleep(2.0**attempt)

        raise ArxivError(
            f"arXiv request failed after {self._max_retries + 1} attempts: {last_error}"
        )

    def by_ids(self, identifiers: list[str]) -> str:
        """Fetch many identifiers in ONE request.

        `id_list` is comma-delimited, so fifty candidates cost one request rather
        than fifty -- which under the three-second rule is the difference between
        three seconds and two and a half minutes.
        """
        return self.get({"id_list": ",".join(identifiers), "max_results": len(identifiers)})

    def search(self, query: str, *, max_results: int, start: int = 0) -> str:
        # start + max_results must stay <= 10000; past that arXiv returns HTTP
        # 500 (not the documented 400, and not the documented 30000 ceiling).
        if start + max_results > 10_000:
            raise ValueError("arXiv refuses start + max_results beyond 10000")
        return self.get(
            {
                "search_query": query,
                "start": start,
                "max_results": max_results,
                "sortBy": "submittedDate",
                "sortOrder": "descending",
            }
        )
