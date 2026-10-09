"""End-to-end against a real Postgres, with arXiv and Anthropic mocked.

Skips unless XLICKBAIT_TEST_DB_URL points at a throwaway database that already
has the migrations applied. Never point this at anything you care about: it
truncates between tests.
"""

from __future__ import annotations

import base64
import os
import random
from datetime import UTC, datetime, timedelta

import pytest

from generator import db
from generator.arxiv.atom import Paper
from generator.db import PendingHeadline, SchemaMismatch
from generator.image import RenderedImage
from generator.llm import Headline
from generator.run import illustrate, tags_for

TEST_DB = os.environ.get("XLICKBAIT_TEST_DB_URL", "").strip()
pytestmark = pytest.mark.skipif(not TEST_DB, reason="XLICKBAIT_TEST_DB_URL is not set")

NOW = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)


@pytest.fixture
def conn():
    with db.connect(TEST_DB) as connection:
        with connection.cursor() as cur:
            cur.execute(
                "TRUNCATE headline_images, headlines, papers, generator_runs "
                "RESTART IDENTITY CASCADE"
            )
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
        #
        # Renamed back in a `finally`, NOT by rolling back. `db.connect` opens
        # the connection with autocommit=True -- which is load-bearing, because
        # without it every `conn.transaction()` degrades to a savepoint and a
        # failed run rolls back its own ledger. The cost is that there is no
        # open transaction here to roll back: the ALTER commits the instant it
        # runs, and a `conn.rollback()` is a silent no-op that leaves the column
        # renamed for every test after this one in the file.
        with conn.cursor() as cur:
            cur.execute("ALTER TABLE headlines RENAME COLUMN anchor TO anchor_renamed")
        try:
            with pytest.raises(SchemaMismatch, match="anchor"):
                db.assert_schema(conn)
        finally:
            with conn.cursor() as cur:
                cur.execute("ALTER TABLE headlines RENAME COLUMN anchor_renamed TO anchor")


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
        # No rollback: `db.upsert` wraps its own `conn.transaction()`, which the
        # exception already rolled back, and on an autocommit connection there is
        # no outer transaction left for `conn.rollback()` to act on anyway.

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


def webp_bytes(width: int = 320, height: int = 200) -> bytes:
    """A real WebP, encoded the way the generator encodes one."""
    import io

    from PIL import Image

    png = io.BytesIO()
    Image.new("RGB", (width, height), (30, 20, 60)).save(png, format="PNG")
    from generator.image import transcode

    data, _, _ = transcode(png.getvalue(), max_width=width, max_bytes=400_000, quality=82)
    return data


def rendered(data: bytes) -> RenderedImage:
    return RenderedImage(
        data=data,
        mime="image/webp",
        width=320,
        height=200,
        model="microsoft/mai-image-2.6-flash",
        prompt="a prompt",
        cost_usd=0.002,
    )


class TestIllustrations:
    def _publish(
        self, conn, arxiv_id: str, *, status: str = "published", offset_hours: int = -1
    ) -> int:
        paper = make_paper(arxiv_id)
        pending = PendingHeadline(
            paper=paper,
            headline=Headline(
                headline=f"Headline for {arxiv_id}",
                dek="d",
                anchor="bolometer array",
                actual_point="p",
            ),
            kind="fresh",
            publish_at=datetime.now(UTC) + timedelta(hours=offset_hours),
        )
        headline_id = db.upsert(conn, pending, model="m")
        if status != "published":
            with conn.cursor() as cur:
                cur.execute("UPDATE headlines SET status = %s WHERE id = %s", (status, headline_id))
        return headline_id

    def test_bytes_survive_the_round_trip_through_base64(self, conn):
        # This is the one thing about storing images in Postgres that would be
        # invisible if it broke: a truncated bytea comes back as a broken image
        # icon with nothing in any log. The site reads the column as
        # `encode(bytes,'base64')` rather than trusting a driver's rendering of
        # a binary column, and this asserts that decision actually round-trips.
        data = webp_bytes()
        headline_id = self._publish(conn, "0000.00001")
        db.upsert_image(conn, headline_id, rendered(data))

        with conn.cursor() as cur:
            cur.execute(
                "SELECT encode(bytes,'base64') AS b64, byte_size, mime "
                "FROM headline_images WHERE headline_id = %s",
                (headline_id,),
            )
            row = cur.fetchone()

        assert row is not None
        decoded = base64.b64decode(row["b64"])
        assert decoded == data
        assert row["byte_size"] == len(data)
        assert row["mime"] == "image/webp"
        assert decoded[:4] == b"RIFF" and decoded[8:12] == b"WEBP"

    def test_re_illustrating_replaces_rather_than_erroring(self, conn):
        headline_id = self._publish(conn, "0000.00001")
        db.upsert_image(conn, headline_id, rendered(webp_bytes(320, 200)))
        replacement = webp_bytes(400, 250)
        db.upsert_image(conn, headline_id, rendered(replacement))

        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) AS n, max(byte_size) AS size FROM headline_images "
                "WHERE headline_id = %s",
                (headline_id,),
            )
            row = cur.fetchone()
        assert row["n"] == 1
        assert row["size"] == len(replacement)

    def test_hiding_a_headline_hides_its_picture(self, conn):
        # The kill switch has to cover the image too, or a takedown only removes
        # the words while the illustration keeps serving from a guessable URL.
        headline_id = self._publish(conn, "0000.00001")
        db.upsert_image(conn, headline_id, rendered(webp_bytes()))
        db.hide(conn, headline_id)

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1 FROM headline_images i JOIN headlines h ON i.headline_id = h.id
                 WHERE h.status = 'published' AND h.publish_at <= now()
                   AND i.headline_id = %s
                """,
                (headline_id,),
            )
            assert cur.fetchone() is None

    def test_deleting_a_headline_takes_its_image_with_it(self, conn):
        headline_id = self._publish(conn, "0000.00001")
        db.upsert_image(conn, headline_id, rendered(webp_bytes()))
        with conn.cursor() as cur:
            cur.execute("DELETE FROM headlines WHERE id = %s", (headline_id,))
            cur.execute(
                "SELECT count(*) AS n FROM headline_images WHERE headline_id = %s", (headline_id,)
            )
            assert cur.fetchone()["n"] == 0

    def test_the_backfill_query_skips_hidden_but_keeps_future_dated(self, conn):
        # A headline scheduled for later today is exactly the one worth
        # illustrating now, before anyone can see it. A hidden one is a takedown,
        # and spending money on it would be absurd.
        live = self._publish(conn, "0000.00001")
        future = self._publish(conn, "0000.00002", offset_hours=24)
        hidden = self._publish(conn, "0000.00003", status="hidden")

        ids = {t.headline_id for t in db.headlines_missing_images(conn, limit=50)}
        assert {live, future} <= ids
        assert hidden not in ids

        db.upsert_image(conn, live, rendered(webp_bytes()))
        ids_after = {t.headline_id for t in db.headlines_missing_images(conn, limit=50)}
        assert live not in ids_after
        assert future in ids_after

    def test_illustrate_writes_through_to_the_database(self, conn):
        class Painter:
            spent_usd = 0.004

            def paint(self, *, headline, dek, category) -> RenderedImage:
                del headline, dek, category
                return rendered(webp_bytes())

        self._publish(conn, "0000.00001")
        self._publish(conn, "0000.00002")
        targets = db.headlines_missing_images(conn, limit=50)

        result = illustrate(
            Painter(), targets, store=lambda hid, img: db.upsert_image(conn, hid, img)
        )

        assert result.made == 2
        assert db.headlines_missing_images(conn, limit=50) == []

    def test_a_schema_without_the_image_table_refuses_only_when_images_are_on(self, conn):
        # The additive-migration rule from CLAUDE.md, made testable: an older
        # database still publishes headlines, and only asking it to store a
        # picture is refused.
        with conn.cursor() as cur:
            cur.execute("ALTER TABLE headline_images RENAME TO headline_images_stashed")
        try:
            db.assert_schema(conn)  # must not raise
            with pytest.raises(SchemaMismatch, match="headline_images"):
                db.assert_schema(conn, images=True)
        finally:
            with conn.cursor() as cur:
                cur.execute("ALTER TABLE headline_images_stashed RENAME TO headline_images")
