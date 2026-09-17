"""Paper selection: the query actually sent, and loop termination.

This module had no tests, which is how both bugs below reached review: a default
query that searched a sixth of arXiv, and a sampling loop that could spin forever
without issuing a single request.
"""

from __future__ import annotations

import random

import pytest

from generator.arxiv.select import SelectionError, pick_fresh, pick_vintage


class RecordingClient:
    """Captures what would have been asked of arXiv. Issues no requests."""

    def __init__(self, body: str, empty: str) -> None:
        self.body = body
        self.empty = empty
        self.queries: list[str] = []
        self.id_batches: list[list[str]] = []

    def search(self, query: str, *, max_results: int, start: int = 0) -> str:
        self.queries.append(query)
        return self.body

    def by_ids(self, identifiers: list[str]) -> str:
        self.id_batches.append(list(identifiers))
        return self.empty


@pytest.fixture
def client(make_entry, make_feed):
    return RecordingClient(body=make_feed(make_entry()), empty=make_feed())


class TestFreshQuery:
    def test_an_empty_category_pool_asks_for_everything(self, client):
        # Regression: the default was `all:e`, a fielded search for the TERM "e".
        # Measured against the live API, that is 503,564 results where `cat:*`
        # returns 3,171,655 -- the default pool was about a sixth of arXiv.
        pick_fresh(client, count=1, categories=[], already_published=set(), rng=random.Random(1))
        assert client.queries == ["cat:*"]

    def test_a_configured_pool_restricts_to_one_category(self, client):
        pick_fresh(
            client,
            count=1,
            categories=["hep-ex"],
            already_published=set(),
            rng=random.Random(1),
        )
        assert client.queries == ["cat:hep-ex"]

    def test_already_published_papers_are_skipped(self, client):
        with pytest.raises(SelectionError):
            pick_fresh(
                client,
                count=1,
                categories=[],
                already_published={"2401.01234"},
                rng=random.Random(1),
            )


class TestVintageTermination:
    def test_a_non_positive_batch_size_terminates_instead_of_hanging(self, client):
        # Regression: `sample_candidates(0, ...)` returns an empty list, and the
        # loop used to `continue` BEFORE incrementing `attempts` -- so a cron run
        # span forever at full tilt without ever making a request. It must now
        # exhaust its attempt budget and fail loudly.
        with pytest.raises(SelectionError, match="only found 0 of 2"):
            pick_vintage(
                client,
                count=2,
                already_published=set(),
                rng=random.Random(7),
                batch_size=0,
                max_attempts=5,
            )
        # And it did so without issuing a single pointless request.
        assert client.id_batches == []

    def test_an_exhausted_sample_space_still_terminates(self, client):
        # The same `continue` is reached when every candidate drawn is already in
        # `seen`, which a small identifier space makes likely rather than exotic.
        with pytest.raises(SelectionError):
            pick_vintage(
                client,
                count=99,
                already_published=set(),
                rng=random.Random(7),
                batch_size=1,
                max_attempts=3,
            )
