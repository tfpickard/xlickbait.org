"""Choosing which papers to write about."""

from __future__ import annotations

import random
from datetime import UTC, datetime

from generator.arxiv import ids
from generator.arxiv.atom import Paper, parse_feed, reconcile
from generator.arxiv.client import ArxivClient


class SelectionError(RuntimeError):
    """Not enough usable papers could be found."""


def newest_yymm(now: datetime | None = None) -> int:
    """The most recent month that could plausibly have identifiers.

    Steps back one month: arXiv announces on a 24-hour cycle, so the current
    month is thinly populated at its start and sampling it mostly wastes the
    budget on misses.
    """
    moment = now or datetime.now(UTC)
    year, month = moment.year, moment.month - 1
    if month == 0:
        year, month = year - 1, 12
    return (year % 100) * 100 + month


def usable(paper: Paper, already_published: set[str]) -> bool:
    return (
        paper.arxiv_id not in already_published
        and not paper.is_withdrawn
        and bool(paper.title)
        and bool(paper.abstract)
    )


def pick_fresh(
    client: ArxivClient,
    *,
    count: int,
    categories: list[str],
    already_published: set[str],
    rng: random.Random,
) -> list[Paper]:
    """Take recent submissions, randomised across the category pool."""
    # `cat:*` and not `all:e`. `all:` is a fielded term search, so "all:e" asked
    # for papers containing the term "e" -- 503,564 of them against 3,171,655 for
    # `cat:*`, measured against the live API. The default pool was quietly about
    # a sixth of arXiv. (`all:*` is not an alternative: it returns HTTP 500.)
    query = "cat:" + rng.choice(categories) if categories else "cat:*"

    # Over-fetch: some will be withdrawn or already used, and one request costs
    # three seconds whether it returns ten rows or sixty.
    feed = client.search(query, max_results=max(count * 6, 30))
    papers = parse_feed(feed)
    rng.shuffle(papers)

    chosen = [paper for paper in papers if usable(paper, already_published)][:count]
    if not chosen:
        raise SelectionError(f"no usable fresh papers found for query {query!r}")
    return chosen


def pick_vintage(
    client: ArxivClient,
    *,
    count: int,
    already_published: set[str],
    rng: random.Random,
    batch_size: int,
    max_attempts: int,
    now: datetime | None = None,
) -> list[Paper]:
    """Sample random identifiers from arXiv's history and verify them in batches.

    Identifiers are verified through `id_list`, which takes a comma-delimited
    list -- so a batch of fifty candidates costs ONE request instead of fifty.
    Under the three-second rule that is three seconds rather than two and a half
    minutes.

    Two hazards handled here:

    * Candidates are validated locally first. A malformed identifier returns an
      empty feed with HTTP 200, shaped exactly like a real miss, so arXiv cannot
      tell us we made a mistake.
    * A partial miss inside a batch is silent, so hits are reconciled against
      what was actually requested rather than trusting the count.
    """
    ceiling = newest_yymm(now)
    found: list[Paper] = []
    attempts = 0
    seen: set[str] = set()

    while len(found) < count and attempts < max_attempts:
        candidates = [
            candidate
            for candidate in ids.sample_candidates(batch_size, ceiling, rng)
            if candidate not in seen and ids.is_valid_new_style(candidate)
        ]
        # A draw that yields nothing usable still costs an attempt. Counting it
        # before the `continue` is what stops this loop spinning forever: a
        # non-positive batch size makes `sample_candidates` return an empty list
        # every time, and a small identifier space can exhaust into `seen`.
        attempts += max(len(candidates), 1)
        if not candidates:
            continue
        seen.update(candidates)

        papers = parse_feed(client.by_ids(candidates))
        hits, _misses = reconcile(candidates, papers)
        for paper in hits:
            if usable(paper, already_published) and len(found) < count:
                found.append(paper)

    if len(found) < count:
        # Loud, per the brief: a quiet short run hides a broken sampler.
        raise SelectionError(
            f"only found {len(found)} of {count} vintage papers after {attempts} "
            f"sampled identifiers (cap {max_attempts}). The sampling bounds in "
            f"generator/arxiv/ids.py may need revisiting."
        )
    return found
