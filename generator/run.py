"""One generator run: pick papers, write headlines, gate them, store them, purge."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from generator import tags as tag_names
from generator.arxiv.atom import Paper
from generator.arxiv.client import ArxivClient
from generator.arxiv.select import pick_fresh, pick_vintage
from generator.config import Config
from generator.db import PendingHeadline
from generator.llm import RETRY_NOTE, Headline, HeadlineWriter
from generator.truth import anchor_is_supported, source_span


@dataclass
class RunResult:
    pending: list[PendingHeadline] = field(default_factory=list)
    rejected: int = 0
    notes: list[str] = field(default_factory=list)

    @property
    def fresh_count(self) -> int:
        return sum(1 for p in self.pending if p.kind == "fresh")

    @property
    def vintage_count(self) -> int:
        return sum(1 for p in self.pending if p.kind == "vintage")


def stagger_times(count: int, hours: float, rng: random.Random, now: datetime) -> list[datetime]:
    """Spread publish times randomly across the next `hours`.

    With `hours == 0` everything publishes immediately, which is the default: a
    run that publishes now is the simple case and should not depend on the
    scheduler working.
    """
    if hours <= 0:
        return [now] * count
    span = timedelta(hours=hours).total_seconds()
    return sorted(now + timedelta(seconds=rng.uniform(0, span)) for _ in range(count))


def write_with_truth_gate(
    writer: HeadlineWriter,
    paper: Paper,
    *,
    retries: int,
) -> tuple[Headline | None, int]:
    """Generate a headline whose anchor survives the truth gate.

    Returns the headline and how many attempts were rejected. A headline that
    cannot produce a verbatim anchor within the retry budget is abandoned and the
    caller picks a different paper -- the gate is never relaxed to let one
    through.
    """
    rejected = 0
    note: str | None = None
    for _ in range(retries + 1):
        headline = writer.write(
            title=paper.title,
            abstract=paper.abstract,
            categories=paper.categories,
            retry_note=note,
        )
        if anchor_is_supported(headline.anchor, paper.title, paper.abstract):
            # Store the paper's spelling, not the model's. The gate permits case
            # and whitespace drift, so without this the anchor shown to readers
            # under "Fact check" could differ from the source -- while the footer
            # promises it is quoted verbatim.
            exact = source_span(headline.anchor, paper.title, paper.abstract)
            if exact is not None and exact != headline.anchor:
                headline = headline.model_copy(update={"anchor": exact})
            return headline, rejected
        rejected += 1
        note = RETRY_NOTE.format(anchor=headline.anchor)
    return None, rejected


def generate(
    *,
    config: Config,
    client: ArxivClient,
    writer: HeadlineWriter,
    already_published: set[str],
    stagger_hours: float,
    rng: random.Random,
    now: datetime | None = None,
) -> RunResult:
    """Produce the headlines for one run, without touching the database."""
    moment = now or datetime.now(UTC)
    result = RunResult()

    # Over-fetch so a paper dropped by the truth gate can be replaced without
    # another round trip to arXiv.
    wanted = {
        "fresh": config.fresh_count,
        "vintage": config.vintage_count,
    }
    candidates: dict[str, list[Paper]] = {
        "fresh": pick_fresh(
            client,
            count=config.fresh_count * 2,
            categories=config.category_pool,
            already_published=already_published,
            rng=rng,
        )
        if wanted["fresh"]
        else [],
        "vintage": pick_vintage(
            client,
            count=config.vintage_count * 2,
            already_published=already_published,
            rng=rng,
            batch_size=config.id_batch_size,
            max_attempts=config.max_vintage_attempts,
            now=moment,
        )
        if wanted["vintage"]
        else [],
    }

    used: set[str] = set(already_published)
    accepted: list[tuple[str, Paper, Headline]] = []

    for kind, target in wanted.items():
        taken = 0
        for paper in candidates[kind]:
            if taken >= target:
                break
            if paper.arxiv_id in used:
                continue
            headline, rejected = write_with_truth_gate(
                writer, paper, retries=config.truth_gate_retries
            )
            result.rejected += rejected
            if headline is None:
                result.notes.append(
                    f"dropped {paper.arxiv_id}: no verbatim anchor after "
                    f"{config.truth_gate_retries + 1} attempts"
                )
                continue
            used.add(paper.arxiv_id)
            accepted.append((kind, paper, headline))
            taken += 1

        if taken < target:
            result.notes.append(
                f"only produced {taken} of {target} {kind} headlines "
                "(candidates exhausted after truth-gate rejections)"
            )

    times = stagger_times(len(accepted), stagger_hours, rng, moment)
    for (kind, paper, headline), publish_at in zip(accepted, times, strict=True):
        result.pending.append(
            PendingHeadline(paper=paper, headline=headline, kind=kind, publish_at=publish_at)
        )
    return result


def tags_for(pending: list[PendingHeadline], headline_ids: list[int]) -> list[str]:
    """Cache tags to purge after publishing these headlines.

    Deliberately does NOT include `h:<id>` for new headlines: nothing has ever
    been cached at a permalink that did not exist until a second ago, so purging
    it is a wasted request against a rate limit measured per tag.
    """
    if not pending:
        return []
    out = {tag_names.LIST, tag_names.FEED, tag_names.ARCHIVE}
    for item in pending:
        out.add(tag_names.day(item.publish_at.astimezone(UTC).strftime("%Y-%m-%d")))
        for category in item.paper.categories:
            out.add(tag_names.category(category))
    del headline_ids
    return sorted(out)
