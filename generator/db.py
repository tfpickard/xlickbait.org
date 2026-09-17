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


def assert_schema(conn: psycopg.Connection) -> None:
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
        for table, columns in REQUIRED_COLUMNS.items():
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
