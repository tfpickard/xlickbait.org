"""Parsing arXiv's Atom, including the things it will not tell you."""

from __future__ import annotations

import pytest

from generator.arxiv.atom import AtomError, Paper, looks_withdrawn, parse_feed, reconcile


class TestParsing:
    def test_extracts_the_fields_the_site_stores(self, make_entry, make_feed):
        (paper,) = parse_feed(make_feed(make_entry()))
        assert paper.arxiv_id == "2401.01234"
        assert paper.version == 1
        assert paper.title.startswith("A Refined Upper Bound")
        assert "10 mK" in paper.abstract
        assert paper.authors == ["R. Alvarez", "M. Okonkwo"]
        assert paper.primary_category == "hep-ex"
        assert paper.categories == ["hep-ex", "physics.ins-det"]
        assert paper.abs_url == "https://arxiv.org/abs/2401.01234v1"

    def test_reads_the_version_from_the_entry_id(self, make_entry, make_feed):
        (paper,) = parse_feed(make_feed(make_entry(version=4)))
        assert paper.version == 4

    def test_handles_primary_category_without_a_scheme_attribute(self, make_entry, make_feed):
        # Live responses emit only term=, contrary to the documentation. Requiring
        # scheme= would silently blank every primary category.
        (paper,) = parse_feed(make_feed(make_entry(primary="cs.LG")))
        assert paper.primary_category == "cs.LG"

    def test_collapses_whitespace_in_titles_and_abstracts(self, make_feed, make_entry):
        (paper,) = parse_feed(make_feed(make_entry(title="A  Title\n   With   Breaks")))
        assert paper.title == "A Title With Breaks"

    def test_parses_the_z_timestamp_form(self, make_entry, make_feed):
        # Live uses 2026-09-15T17:55:28Z; the docs show an offset form.
        (paper,) = parse_feed(make_feed(make_entry()))
        assert paper.published_at.year == 2024
        assert paper.published_at.tzinfo is not None

    def test_raises_on_an_arxiv_error_entry(self):
        # Errors arrive as an ordinary-looking entry; HTTP status alone does not
        # distinguish them, and over-limit failures come back as 500 anyway.
        xml = """<?xml version="1.0"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
          <entry>
            <id>https://arxiv.org/api/errors#start_must_be_non-negative</id>
            <title>Error</title>
            <summary>start must be non-negative</summary>
          </entry>
        </feed>"""
        with pytest.raises(AtomError, match="non-negative"):
            parse_feed(xml)

    def test_an_empty_feed_is_not_an_error(self, make_feed):
        # A nonexistent id returns HTTP 200 and zero entries. That is a miss, not
        # a failure, and must not raise.
        assert parse_feed(make_feed(total=0)) == []


class TestReconcile:
    def _paper(self, arxiv_id: str) -> Paper:
        from datetime import UTC, datetime

        return Paper(
            arxiv_id=arxiv_id,
            version=1,
            title="t",
            abstract="a",
            authors=[],
            primary_category="cs.LG",
            categories=["cs.LG"],
            published_at=datetime(2024, 1, 1, tzinfo=UTC),
            abs_url=f"https://arxiv.org/abs/{arxiv_id}",
            comment=None,
        )

    def test_detects_a_silent_partial_miss(self):
        # THE trap in batched id_list: absent identifiers are not mentioned
        # anywhere in the response -- totalResults simply drops. Without
        # reconciling, a run cannot tell 49 hits from 50.
        requested = ["2401.00001", "2401.00002", "2401.00003"]
        returned = [self._paper("2401.00001"), self._paper("2401.00003")]
        hits, misses = reconcile(requested, returned)
        assert [p.arxiv_id for p in hits] == ["2401.00001", "2401.00003"]
        assert misses == ["2401.00002"]

    def test_all_hit(self):
        requested = ["2401.00001"]
        hits, misses = reconcile(requested, [self._paper("2401.00001")])
        assert len(hits) == 1 and misses == []

    def test_all_miss(self):
        hits, misses = reconcile(["2401.00001", "2401.00002"], [])
        assert hits == [] and len(misses) == 2

    def test_preserves_requested_order(self):
        requested = ["2401.00003", "2401.00001", "2401.00002"]
        returned = [self._paper(i) for i in ["2401.00001", "2401.00002", "2401.00003"]]
        hits, _ = reconcile(requested, returned)
        assert [p.arxiv_id for p in hits] == requested


class TestWithdrawal:
    @pytest.mark.parametrize(
        "comment",
        [
            "This paper has been withdrawn by the authors for administrative reasons",
            "The paper has been withdrawn due to a conflict of interest",
            "This paper has been withdrawn by the author due to organizational policy",
            "Withdrawn by the authors.",
            "This submission has been withdrawn.",
        ],
    )
    def test_detects_real_withdrawals(self, comment):
        assert looks_withdrawn(comment, 2)

    def test_ignores_a_paper_that_merely_mentions_one(self):
        # A real false positive from the corpus. A substring search would discard
        # a perfectly live paper because it cites a withdrawn one.
        assert not looks_withdrawn(
            "This manuscript supersedes arXiv:2510.26642, which has been withdrawn "
            "with the agreement of all its authors.",
            2,
        )

    def test_a_v1_cannot_be_withdrawn(self):
        # Withdrawal is always a new version, so v1 plus the phrase is someone
        # talking about something else.
        assert not looks_withdrawn("This paper has been withdrawn by the authors", 1)

    @pytest.mark.parametrize("comment", ["12 pages, 4 figures", "", None])
    def test_ordinary_comments_are_not_withdrawals(self, comment):
        assert not looks_withdrawn(comment, 3)

    def test_the_paper_property_agrees(self, make_entry, make_feed):
        (live,) = parse_feed(make_feed(make_entry(version=2, comment="12 pages")))
        (dead,) = parse_feed(
            make_feed(make_entry(version=2, comment="This paper has been withdrawn"))
        )
        assert not live.is_withdrawn
        assert dead.is_withdrawn
