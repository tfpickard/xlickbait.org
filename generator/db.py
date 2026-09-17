"""Database access for the generator: the only writer in the system.

psycopg 3, one transaction per paper-plus-headline. DML only -- the schema is
owned by Drizzle migrations on the TypeScript side, and this asserts at startup
that what it expects is actually there rather than attempting to create it.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime

import psycopg
from psycopg.rows import dict_row

from generator.arxiv.atom import Paper
from generator.image import RenderedImage
from generator.llm import Headline

# What the generator writes. If any of this is missing, the schema and this code
# have diverged and continuing would either fail per-row or, worse, silently
# write something the site cannot read.
REQUIRED_COLUMNS: dict[str, set[str]] = {
    "papers": {
        "arxiv_id",
        "title",
        "abstract",
        "authors",
        "primary_category",
        "categories",
        "published_at",
        "abs_url",
    },
    "headlines": {
        "id",
        "arxiv_id",
        "headline",
        "dek",
        "anchor",
        "actual_point",
        "kind",
        "model",
        "status",
        "created_at",
        "publish_at",
    },
    "generator_runs": {
        "id",
        "started_at",
        "finished_at",
        "fresh_count",
        "vintage_count",
        "rejected_count",
        "error",
    },
}

# Asserted only when the run is actually going to write an image. The table
# arrived in a later migration than the rest, and "publish headlines" must not
# acquire a dependency on "can store pictures" -- a generator pointed at a
# database from before that migration still has a job to do. Checked up front
# rather than per row so an enabled-but-unmigrated setup fails before it spends
# money on an image it cannot store.
REQUIRED_IMAGE_COLUMNS: dict[str, set[str]] = {
    "headline_images": {
        "headline_id",
        "mime",
        "width",
        "height",
        "byte_size",
        "bytes",
        "model",
        "prompt",
        "created_at",
    },
}

REQUIRED_ENUMS: dict[str, set[str]] = {
    "headline_kind": {"fresh", "vintage"},
    "headline_status": {"published", "hidden"},
}


class SchemaMismatch(RuntimeError):
    """The database does not look the way this generator expects."""


@contextmanager
def connect(database_url: str) -> Iterator[psycopg.Connection]:
    """Open a connection whose `transaction()` blocks really are transactions.

    `autocommit=True` is load-bearing, not a tuning knob. psycopg defaults to
    autocommit=False, so the first SELECT -- assert_schema(), before anything is
    written -- opens an implicit transaction. Every later `conn.transaction()`
    then nests INSIDE it as a mere savepoint, committing nothing, and the
    connection context manager rolls the entire run back when an exception
    leaves the block: the published headlines, the run row, and the error
    written to explain the failure.

    That is the exact opposite of the two guarantees this module claims -- one
    committed transaction per headline, and a ledger that records failures. With
    autocommit on, each `transaction()` block is a real top-level transaction
    that commits at its own exit.
    """
    with psycopg.connect(database_url, row_factory=dict_row, autocommit=True) as conn:
        yield conn


def assert_schema(conn: psycopg.Connection, *, images: bool = False) -> None:
    """Fail fast and loudly if the schema has moved underneath us.

    Deliberately a read-only check. The generator never runs DDL: migrations are
    generated from the Drizzle schema, reviewed, and applied deliberately by a
    human. A generator that could "fix" the schema itself is a generator that can
    corrupt it at three in the morning.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT table_name, column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
            """
        )
        actual: dict[str, set[str]] = {}
        for row in cur.fetchall():
            actual.setdefault(row["table_name"], set()).add(row["column_name"])

        problems: list[str] = []
        required = dict(REQUIRED_COLUMNS)
        if images:
            required.update(REQUIRED_IMAGE_COLUMNS)
        for table, columns in required.items():
            if table not in actual:
                problems.append(f"missing table {table!r}")
                continue
            missing = columns - actual[table]
            if missing:
                problems.append(f"table {table!r} is missing columns: {', '.join(sorted(missing))}")

        cur.execute(
            """
            SELECT t.typname AS name, e.enumlabel AS label
            FROM pg_type t JOIN pg_enum e ON e.enumtypid = t.oid
            """
        )
        enums: dict[str, set[str]] = {}
        for row in cur.fetchall():
            enums.setdefault(row["name"], set()).add(row["label"])

        for enum, labels in REQUIRED_ENUMS.items():
            if enum not in enums:
                problems.append(f"missing enum type {enum!r}")
            elif not labels <= enums[enum]:
                problems.append(
                    f"enum {enum!r} is missing values: {', '.join(sorted(labels - enums[enum]))}"
                )

    if problems:
        raise SchemaMismatch(
            "The database schema does not match what the generator expects:\n  - "
            + "\n  - ".join(problems)
            + "\n\nApply the migrations from the web app before running the generator."
        )


def published_arxiv_ids(conn: psycopg.Connection) -> set[str]:
    """Papers that already carry a published headline, so they are not reused."""
    with conn.cursor() as cur:
        cur.execute("SELECT arxiv_id FROM headlines WHERE status = 'published'")
        return {row["arxiv_id"] for row in cur.fetchall()}


@dataclass(frozen=True)
class PendingHeadline:
    paper: Paper
    headline: Headline
    kind: str
    publish_at: datetime


def upsert(conn: psycopg.Connection, pending: PendingHeadline, *, model: str) -> int:
    """Write one paper and its headline in a single transaction.

    Returns the new headline id. The paper upsert refreshes metadata -- titles
    and abstracts do get revised between versions -- while the headline is a
    plain insert, because the partial unique index is what enforces one published
    headline per paper and a conflict there should be an error, not a silent
    overwrite of a headline someone may have already read.
    """
    paper = pending.paper
    with conn.transaction(), conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO papers (arxiv_id, title, abstract, authors, primary_category,
                                categories, published_at, abs_url)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (arxiv_id) DO UPDATE SET
                title = EXCLUDED.title,
                abstract = EXCLUDED.abstract,
                authors = EXCLUDED.authors,
                primary_category = EXCLUDED.primary_category,
                categories = EXCLUDED.categories,
                published_at = EXCLUDED.published_at,
                abs_url = EXCLUDED.abs_url
            """,
            (
                paper.arxiv_id,
                paper.title,
                paper.abstract,
                paper.authors,
                paper.primary_category,
                paper.categories,
                paper.published_at,
                paper.abs_url,
            ),
        )
        cur.execute(
            """
            INSERT INTO headlines (arxiv_id, headline, dek, anchor, actual_point,
                                   kind, model, status, publish_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'published', %s)
            RETURNING id
            """,
            (
                paper.arxiv_id,
                pending.headline.headline,
                pending.headline.dek,
                pending.headline.anchor,
                pending.headline.actual_point,
                pending.kind,
                model,
                pending.publish_at,
            ),
        )
        row = cur.fetchone()
        assert row is not None
        return int(row["id"])


def hide(conn: psycopg.Connection, headline_id: int) -> bool:
    """The kill switch. Returns False if the id did not exist."""
    with conn.transaction(), conn.cursor() as cur:
        cur.execute(
            "UPDATE headlines SET status = 'hidden' WHERE id = %s RETURNING arxiv_id",
            (headline_id,),
        )
        return cur.fetchone() is not None


def start_run(conn: psycopg.Connection) -> int:
    with conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO generator_runs (started_at) VALUES (now()) RETURNING id")
        row = cur.fetchone()
        assert row is not None
        return int(row["id"])


def finish_run(
    conn: psycopg.Connection,
    run_id: int,
    *,
    fresh: int,
    vintage: int,
    rejected: int,
    error: str | None = None,
) -> None:
    with conn.transaction(), conn.cursor() as cur:
        cur.execute(
            """
            UPDATE generator_runs
               SET finished_at = now(), fresh_count = %s, vintage_count = %s,
                   rejected_count = %s, error = %s
             WHERE id = %s
            """,
            (fresh, vintage, rejected, error, run_id),
        )


@dataclass(frozen=True)
class Illustratable:
    """A published headline that has no picture yet."""

    headline_id: int
    headline: str
    dek: str
    primary_category: str
    categories: list[str]
    publish_at: datetime


def headlines_missing_images(conn: psycopg.Connection, *, limit: int) -> list[Illustratable]:
    """Published headlines with no image, newest first.

    `status = 'published'` rather than the site's full visibility rule: a
    headline scheduled for later today is exactly the one worth illustrating
    NOW, before anybody can see it. Hidden ones are skipped -- a takedown should
    not be spending money.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT h.id, h.headline, h.dek, h.publish_at,
                   p.primary_category, p.categories
              FROM headlines h
              JOIN papers p ON p.arxiv_id = h.arxiv_id
              LEFT JOIN headline_images i ON i.headline_id = h.id
             WHERE h.status = 'published' AND i.headline_id IS NULL
             ORDER BY h.publish_at DESC, h.id DESC
             LIMIT %s
            """,
            (limit,),
        )
        return [
            Illustratable(
                headline_id=int(row["id"]),
                headline=row["headline"],
                dek=row["dek"],
                primary_category=row["primary_category"],
                categories=list(row["categories"]),
                publish_at=row["publish_at"],
            )
            for row in cur.fetchall()
        ]


def upsert_image(conn: psycopg.Connection, headline_id: int, image: RenderedImage) -> None:
    """Store one illustration, in its own transaction.

    `byte_size` is written from Python rather than computed by the database so
    the two can be compared later: a mismatch means the bytes were truncated in
    transit, which is otherwise invisible in a column nothing reads as text.

    ON CONFLICT DO UPDATE so regenerating a bad image is a re-run rather than a
    manual DELETE. The site serves this under the `h:<id>` cache tag, so the
    caller purges that tag after replacing one.
    """
    with conn.transaction(), conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO headline_images (headline_id, mime, width, height, byte_size,
                                         bytes, model, prompt)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (headline_id) DO UPDATE SET
                mime = EXCLUDED.mime,
                width = EXCLUDED.width,
                height = EXCLUDED.height,
                byte_size = EXCLUDED.byte_size,
                bytes = EXCLUDED.bytes,
                model = EXCLUDED.model,
                prompt = EXCLUDED.prompt,
                created_at = now()
            """,
            (
                headline_id,
                image.mime,
                image.width,
                image.height,
                len(image.data),
                image.data,
                image.model,
                image.prompt,
            ),
        )
