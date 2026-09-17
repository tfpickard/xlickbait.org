"""End-to-end against a real Postgres, with arXiv and Anthropic mocked.

Skips unless XLICKBAIT_TEST_DB_URL points at a throwaway database that already
has the migrations applied. Never point this at anything you care about: it
truncates between tests.
"""

from __future__ import annotations

import os
import random
from datetime import UTC, datetime, timedelta

import pytest

from generator import db
from generator.arxiv.atom import Paper
from generator.db import PendingHeadline, SchemaMismatch
from generator.llm import Headline
from generator.run import tags_for

TEST_DB = os.environ.get("XLICKBAIT_TEST_DB_URL", "").strip()
pytestmark = pytest.mark.skipif(not TEST_DB, reason="XLICKBAIT_TEST_DB_URL is not set")

NOW = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)


@pytest.fixture
def conn():
    with db.connect(TEST_DB) as connection:
        with connection.cursor() as cur:
            cur.execute("TRUNCATE headlines, papers, generator_runs RESTART IDENTITY CASCADE")
        connection.commit()
        yield connection


def make_paper(arxiv_id: str, categories: list[str] | None = None) -> Paper:
    return Paper(
        arxiv_id=arxiv_id,
        version=1,
        title=f"A Study of {arxiv_id}",
        abstract="We operated a bolometer array at 10 mK for three years.",
        authors=["R. Alvarez", "M. Okonkwo"],
        primary_category=(categories or ["hep-ex"])[0],
        categories=categories or ["hep-ex", "physics.ins-det"],
        published_at=NOW - timedelta(days=3),
        abs_url=f"https://arxiv.org/abs/{arxiv_id}",
        comment=None,
    )


def make_pending(arxiv_id: str, kind: str = "fresh", when: datetime | None = None):
    return PendingHeadline(
        paper=make_paper(arxiv_id),
        headline=Headline(
            headline=f"Scientists Baffled By {arxiv_id}",
            dek="They cannot explain it.",
            anchor="a bolometer array at 10 mK",
            actual_point="It is a neutrino mass bound.",
        ),
        kind=kind,
        publish_at=when or NOW,
    )


class TestSchemaAssertion:
    def test_passes_against_the_migrated_schema(self, conn):
        db.assert_schema(conn)  # must not raise

    def test_fails_loudly_when_the_schema_has_moved(self, conn):
        # The generator never runs DDL, so a drifted schema must stop the run
        # rather than produce half-written rows at three in the morning.
        with conn.cursor() as cur:
            cur.execute("ALTER TABLE headlines RENAME COLUMN anchor TO anchor_renamed")
        with pytest.raises(SchemaMismatch, match="anchor"):
            db.assert_schema(conn)
        conn.rollback()


class TestWriting:
    def test_writes_a_paper_and_its_headline(self, conn):
        headline_id = db.upsert(conn, make_pending("2401.00001"), model="test-model")
        assert headline_id > 0

        with conn.cursor() as cur:
            cur.execute("SELECT * FROM papers WHERE arxiv_id = '2401.00001'")
            paper = cur.fetchone()
            cur.execute("SELECT * FROM headlines WHERE id = %s", (headline_id,))
            headline = cur.fetchone()

        assert paper is not None and headline is not None
        assert paper["authors"] == ["R. Alvarez", "M. Okonkwo"]
        assert paper["categories"] == ["hep-ex", "physics.ins-det"]
        assert headline["status"] == "published"
        assert headline["kind"] == "fresh"
        assert headline["model"] == "test-model"

    def test_the_partial_index_allows_only_one_published_headline_per_paper(self, conn):
        db.upsert(conn, make_pending("2401.00002"), model="m")
        # The database, not the generator, is what enforces this -- and it should
        # be an error rather than a silent overwrite of something already read.
        import psycopg

        with pytest.raises(psycopg.errors.UniqueViolation):
            db.upsert(conn, make_pending("2401.00002"), model="m")
        conn.rollback()

    def test_a_hidden_headline_frees_the_paper_for_a_new_one(self, conn):
        first = db.upsert(conn, make_pending("2401.00003"), model="m")
        assert db.hide(conn, first)
        # The index is partial on status='published', so hiding one makes room.
        second = db.upsert(conn, make_pending("2401.00003"), model="m")
        assert second != first

    def test_upserting_a_paper_refreshes_its_metadata(self, conn):
        db.upsert(conn, make_pending("2401.00004"), model="m")
        updated = make_pending("2401.00004")
        revised = Paper(**{**updated.paper.__dict__, "title": "A Revised Title"})
        db.hide(conn, 1)
        db.upsert(
            conn,
            PendingHeadline(
                paper=revised, headline=updated.headline, kind="vintage", publish_at=NOW
            ),
            model="m",
        )
        with conn.cursor() as cur:
            cur.execute("SELECT title FROM papers WHERE arxiv_id = '2401.00004'")
            assert cur.fetchone()["title"] == "A Revised Title"


class TestDedupe:
    def test_published_ids_are_reported_for_exclusion(self, conn):
        db.upsert(conn, make_pending("2401.00010"), model="m")
        db.upsert(conn, make_pending("2401.00011"), model="m")
        assert db.published_arxiv_ids(conn) == {"2401.00010", "2401.00011"}

    def test_hidden_headlines_do_not_block_reuse(self, conn):
        headline_id = db.upsert(conn, make_pending("2401.00012"), model="m")
        db.hide(conn, headline_id)
        assert db.published_arxiv_ids(conn) == set()


class TestRunRecords:
    def test_a_run_is_opened_and_closed(self, conn):
        run_id = db.start_run(conn)
        db.finish_run(conn, run_id, fresh=3, vintage=4, rejected=2)
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM generator_runs WHERE id = %s", (run_id,))
            row = cur.fetchone()
        assert row["fresh_count"] == 3
        assert row["vintage_count"] == 4
        assert row["rejected_count"] == 2
        assert row["finished_at"] is not None
        assert row["error"] is None

    def test_a_failure_is_recorded_rather_than_lost(self, conn):
        run_id = db.start_run(conn)
        db.finish_run(conn, run_id, fresh=0, vintage=0, rejected=0, error="arXiv unreachable")
        with conn.cursor() as cur:
            cur.execute("SELECT error FROM generator_runs WHERE id = %s", (run_id,))
            assert cur.fetchone()["error"] == "arXiv unreachable"


class TestScheduling:
    def test_future_dated_headlines_are_stored_but_not_yet_live(self, conn):
        scheduled = datetime.now(UTC) + timedelta(hours=5)
        db.upsert(conn, make_pending("2401.00020", when=scheduled), model="m")
        with conn.cursor() as cur:
            # The exact predicate the website uses.
            cur.execute(
                "SELECT count(*) AS n FROM headlines "
                "WHERE status = 'published' AND publish_at <= now()"
            )
            assert cur.fetchone()["n"] == 0
            cur.execute("SELECT count(*) AS n FROM headlines")
            assert cur.fetchone()["n"] == 1


class TestPurgeTagsFromRealRows:
    def test_tags_reflect_what_was_actually_written(self, conn):
        pending = [make_pending("2401.00030", when=NOW)]
        ids = [db.upsert(conn, item, model="m") for item in pending]
        tags = tags_for(pending, ids)
        assert "list" in tags and "feed" in tags
        assert "day:2026-09-17" in tags
        assert "cat:hep-ex" in tags


def test_rng_seeded_runs_are_reproducible():
    from generator.run import stagger_times

    a = stagger_times(10, 4, random.Random(1), NOW)
    b = stagger_times(10, 4, random.Random(1), NOW)
    assert a == b
