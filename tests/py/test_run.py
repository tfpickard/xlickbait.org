"""Run orchestration: the truth-gate loop, stagger bounds, and dedupe."""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta

import pytest

from generator.arxiv.atom import Paper
from generator.db import PendingHeadline
from generator.llm import Headline
from generator.run import RunResult, stagger_times, tags_for, write_with_truth_gate

NOW = datetime(2026, 9, 17, 12, 0, 0, tzinfo=UTC)


def paper(arxiv_id: str = "2401.01234", abstract: str | None = None) -> Paper:
    return Paper(
        arxiv_id=arxiv_id,
        version=1,
        title="A Refined Upper Bound on Neutrino Mass",
        abstract=abstract or "We use a bolometer array operated at 10 mK for three years.",
        authors=["R. Alvarez"],
        primary_category="hep-ex",
        categories=["hep-ex", "physics.ins-det"],
        published_at=NOW,
        abs_url=f"https://arxiv.org/abs/{arxiv_id}",
        comment=None,
    )


class ScriptedWriter:
    """A HeadlineWriter stand-in that returns queued anchors in order."""

    def __init__(self, anchors: list[str]) -> None:
        self.anchors = list(anchors)
        self.calls: list[str | None] = []

    def write(self, *, title, abstract, categories, retry_note=None) -> Headline:
        self.calls.append(retry_note)
        anchor = self.anchors.pop(0)
        return Headline(
            headline="Scientists Baffled",
            dek="They cannot explain it.",
            anchor=anchor,
            actual_point="It is a neutrino mass bound.",
        )


class TestTruthGateLoop:
    def test_accepts_a_verbatim_anchor_on_the_first_try(self):
        writer = ScriptedWriter(["a bolometer array operated at 10 mK"])
        headline, rejected = write_with_truth_gate(writer, paper(), retries=2)
        assert headline is not None
        assert rejected == 0
        assert writer.calls == [None]

    def test_retries_a_bad_anchor_and_tells_the_model_why(self):
        writer = ScriptedWriter(["10 millikelvin", "a bolometer array operated at 10 mK"])
        headline, rejected = write_with_truth_gate(writer, paper(), retries=2)
        assert headline is not None
        assert rejected == 1
        # The retry must carry a note naming the rejected anchor, or it is just
        # asking the same question again and hoping.
        assert writer.calls[0] is None
        assert "10 millikelvin" in (writer.calls[1] or "")

    def test_gives_up_after_the_retry_budget_rather_than_relaxing_the_gate(self):
        writer = ScriptedWriter(["wrong one", "wrong two", "wrong three"])
        headline, rejected = write_with_truth_gate(writer, paper(), retries=2)
        assert headline is None  # dropped, never admitted
        assert rejected == 3

    def test_uses_exactly_retries_plus_one_attempts(self):
        # A span that genuinely does not occur in the paper -- note that a short
        # anchor like "a" would be accepted, correctly, because it really is in
        # the abstract.
        writer = ScriptedWriter(["quantum badger telemetry"] * 10)
        write_with_truth_gate(writer, paper(), retries=2)
        assert len(writer.calls) == 3

    def test_a_short_but_genuine_span_is_accepted(self):
        # Guards against "fixing" the gate with a minimum-length rule: a short
        # anchor that really appears is still true, and truth is the criterion.
        writer = ScriptedWriter(["10 mK"])
        headline, rejected = write_with_truth_gate(writer, paper(), retries=2)
        assert headline is not None and rejected == 0


class TestStagger:
    def test_zero_publishes_everything_immediately(self):
        assert stagger_times(5, 0, random.Random(1), NOW) == [NOW] * 5

    def test_negative_is_treated_as_zero(self):
        assert stagger_times(3, -4, random.Random(1), NOW) == [NOW] * 3

    @pytest.mark.parametrize("hours", [1, 6, 24])
    def test_stays_within_bounds(self, hours):
        times = stagger_times(200, hours, random.Random(9), NOW)
        assert all(NOW <= t <= NOW + timedelta(hours=hours) for t in times)

    def test_is_sorted_so_publication_order_matches_insertion_order(self):
        times = stagger_times(50, 6, random.Random(4), NOW)
        assert times == sorted(times)

    def test_actually_spreads_rather_than_clustering(self):
        times = stagger_times(100, 6, random.Random(11), NOW)
        span = (times[-1] - times[0]).total_seconds() / 3600
        assert span > 3, "a 6-hour stagger that spans under 3 hours is not spreading"

    def test_is_reproducible_for_a_seed(self):
        assert stagger_times(20, 6, random.Random(5), NOW) == stagger_times(
            20, 6, random.Random(5), NOW
        )


class TestPurgeTags:
    def _pending(self, arxiv_id: str, when: datetime, categories: list[str]) -> PendingHeadline:
        p = paper(arxiv_id)
        return PendingHeadline(
            paper=Paper(**{**p.__dict__, "categories": categories}),
            headline=Headline(headline="h", dek="d", anchor="a", actual_point="p"),
            kind="fresh",
            publish_at=when,
        )

    def test_nothing_published_means_no_tags_at_all(self):
        # Feeds straight into the purge guard: an empty tag list must never become
        # a request, because a body without cache_tags purges the whole site.
        assert tags_for([], []) == []

    def test_covers_the_pages_a_new_headline_changes(self):
        result = tags_for([self._pending("2401.1", NOW, ["cs.LG"])], [1])
        assert "list" in result and "feed" in result and "archive" in result
        assert "day:2026-09-17" in result
        assert "cat:cs.LG" in result

    def test_uses_the_utc_day_of_publish_at(self):
        late = datetime(2026, 9, 17, 23, 30, tzinfo=UTC)
        assert "day:2026-09-17" in tags_for([self._pending("2401.1", late, ["cs.LG"])], [1])

    def test_includes_every_category_including_cross_lists(self):
        result = tags_for([self._pending("2401.1", NOW, ["cs.LG", "stat.ML"])], [1])
        assert "cat:cs.LG" in result and "cat:stat.ML" in result

    def test_does_not_purge_permalinks_for_brand_new_headlines(self):
        # Nothing was ever cached at a URL that did not exist a second ago, and
        # the purge rate limit is measured per tag.
        result = tags_for([self._pending("2401.1", NOW, ["cs.LG"])], [7])
        assert not any(t.startswith("h:") for t in result)


class TestRunResult:
    def test_counts_by_kind(self):
        def p(kind: str) -> PendingHeadline:
            return PendingHeadline(
                paper=paper(),
                headline=Headline(headline="h", dek="d", anchor="a", actual_point="p"),
                kind=kind,
                publish_at=NOW,
            )

        result = RunResult(pending=[p("fresh"), p("fresh"), p("vintage")])
        assert result.fresh_count == 2
        assert result.vintage_count == 1
