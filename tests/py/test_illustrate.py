"""The illustration pass: what it survives, what it does not, and what it purges."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import ClassVar

import pytest

from generator.db import Illustratable
from generator.image import BudgetExhausted, ImageError, RenderedImage
from generator.run import illustrate, tags_for_illustrations, targets_for


def target(headline_id: int, *, categories: tuple[str, ...] = ("hep-ex",)) -> Illustratable:
    return Illustratable(
        headline_id=headline_id,
        headline=f"Headline {headline_id}",
        dek="They cannot explain it.",
        primary_category=categories[0],
        categories=list(categories),
        publish_at=datetime(2026, 9, 17, 12, 0, tzinfo=UTC),
    )


def rendered() -> RenderedImage:
    return RenderedImage(
        data=b"RIFF....WEBP",
        mime="image/webp",
        width=1200,
        height=800,
        model="microsoft/mai-image-2.6-flash",
        prompt="p",
        cost_usd=0.002,
    )


class FakePainter:
    """Stands in for `ImagePainter`, scripted with one outcome per call."""

    def __init__(self, outcomes: list[object], spent: float = 0.0) -> None:
        self._outcomes = list(outcomes)
        self.calls: list[str] = []
        self.spent_usd = spent

    def paint(self, *, headline: str, dek: str, category: str) -> RenderedImage:
        del dek, category
        self.calls.append(headline)
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        assert isinstance(outcome, RenderedImage)
        return outcome


def collector():
    stored: list[int] = []
    return stored, lambda headline_id, _image: stored.append(headline_id)


class TestSurvivingFailures:
    def test_one_bad_image_does_not_cost_the_others(self):
        # The whole point. A headline is already published by the time this runs;
        # an image model having a bad minute must not take the rest of the batch
        # down with it.
        painter = FakePainter([rendered(), ImageError("nope"), rendered()])
        stored, store = collector()

        result = illustrate(painter, [target(1), target(2), target(3)], store=store)

        assert stored == [1, 3]
        assert (result.made, result.failed) == (2, 1)
        assert any("headline 2" in note for note in result.notes)

    def test_an_exhausted_budget_stops_the_loop_rather_than_failing_each_one(self):
        painter = FakePainter([rendered(), BudgetExhausted("spent"), rendered()])
        stored, store = collector()

        result = illustrate(painter, [target(1), target(2), target(3)], store=store)

        # Headline 3 was never even attempted: every remaining call would fail
        # the same way, and one note beats N identical ones.
        assert painter.calls == ["Headline 1", "Headline 2"]
        assert stored == [1]
        assert result.made == 1
        assert result.failed == 0
        assert result.notes == ["spent"]

    def test_a_database_failure_is_not_swallowed(self):
        # ImageError means "the picture didn't work out". A failing write means
        # the database is unwell, and logging that as a missing thumbnail is how
        # a generator reports success forever.
        painter = FakePainter([rendered()])

        def store(_id: int, _image: RenderedImage) -> None:
            raise RuntimeError("connection reset")

        with pytest.raises(RuntimeError, match="connection reset"):
            illustrate(painter, [target(1)], store=store)

    def test_reports_the_spend(self):
        painter = FakePainter([rendered()], spent=0.004)
        _, store = collector()
        assert illustrate(painter, [target(1)], store=store).spent_usd == pytest.approx(0.004)

    def test_no_targets_is_a_no_op(self):
        painter = FakePainter([])
        _, store = collector()
        result = illustrate(painter, [], store=store)
        assert (result.made, result.failed, result.notes) == (0, 0, [])


class TestPurgeTags:
    def test_backfilled_headlines_purge_their_own_permalinks(self):
        # The difference from `tags_for`: these headlines have been sitting on
        # cached pages for hours, rendered with the SVG fallback. Nothing
        # invalidates those pages when the image row appears.
        tags = tags_for_illustrations([target(7, categories=("hep-ex", "astro-ph.CO"))])

        assert "h:7" in tags
        assert "list" in tags
        assert "archive" in tags
        assert "day:2026-09-17" in tags
        assert "cat:hep-ex" in tags
        assert "cat:astro-ph.CO" in tags

    def test_the_day_key_is_utc(self):
        late = Illustratable(
            headline_id=1,
            headline="H",
            dek="D",
            primary_category="hep-ex",
            categories=["hep-ex"],
            # 20:00 in UTC-07:00 is the 18th in UTC, and the day page it lands on
            # is the UTC one.
            publish_at=datetime.fromisoformat("2026-09-17T20:00:00-07:00"),
        )
        assert "day:2026-09-18" in tags_for_illustrations([late])

    def test_nothing_illustrated_purges_nothing(self):
        # Same footgun as `purge.py` guards: an empty tag list must stay empty
        # all the way down, never becoming an absent `cache_tags` key.
        assert tags_for_illustrations([]) == []


class TestTargets:
    def test_pairs_pending_headlines_with_their_new_ids(self):
        class FakePaper:
            arxiv_id = "2401.01234"
            primary_category = "hep-ex"
            categories: ClassVar[list[str]] = ["hep-ex", "physics.ins-det"]

        class FakeHeadline:
            headline = "Baffled"
            dek = "Utterly."

        class FakePending:
            paper = FakePaper()
            headline = FakeHeadline()
            publish_at = datetime(2026, 9, 17, tzinfo=UTC)

        targets = targets_for([FakePending()], [42])

        assert targets[0].headline_id == 42
        assert targets[0].headline == "Baffled"
        assert targets[0].categories == ["hep-ex", "physics.ins-det"]

    def test_a_mismatched_id_count_is_an_error_not_a_silent_truncation(self):
        # strict=True on the zip. Losing the pairing here would attach one
        # headline's picture to another headline's id.
        with pytest.raises(ValueError):
            targets_for([object()], [])
