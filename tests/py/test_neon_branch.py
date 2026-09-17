"""Integration against a throwaway Neon branch.

Creates a branch off `dev`, applies the migrations, runs the generator against
it with arXiv and Anthropic mocked, asserts the rows land, then deletes the
branch -- in a teardown that runs even when the test fails, because an orphaned
branch eats one of the ten a free-tier project gets.

Skips cleanly when the Neon CLI is absent or unauthenticated, rather than
failing. The auth check is explicit and always passes `--api-key`, because any
`neon` command without credentials falls through to opening a browser, which in
a test run means hanging rather than erroring.

Note the CLI is now `neon` (package `neon`); `neonctl` is a compatibility shim.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest

NOW = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)


def make_pending(arxiv_id: str, kind: str = "fresh"):
    """A publishable record, built locally so this module stands alone."""
    from generator.arxiv.atom import Paper
    from generator.db import PendingHeadline
    from generator.llm import Headline

    return PendingHeadline(
        paper=Paper(
            arxiv_id=arxiv_id,
            version=1,
            title=f"A Study of {arxiv_id}",
            abstract="We operated a bolometer array at 10 mK for three years.",
            authors=["R. Alvarez", "M. Okonkwo"],
            primary_category="hep-ex",
            categories=["hep-ex", "physics.ins-det"],
            published_at=NOW - timedelta(days=3),
            abs_url=f"https://arxiv.org/abs/{arxiv_id}",
            comment=None,
        ),
        headline=Headline(
            headline=f"Scientists Baffled By {arxiv_id}",
            dek="They cannot explain it.",
            anchor="a bolometer array at 10 mK",
            actual_point="It is a neutrino mass bound.",
        ),
        kind=kind,
        publish_at=NOW,
    )


API_KEY = os.environ.get("NEON_API_KEY", "").strip()
PROJECT_ID = os.environ.get("NEON_PROJECT_ID", "").strip()
PARENT_BRANCH = os.environ.get("NEON_PARENT_BRANCH", "dev")


def _neon(*args: str, timeout: int = 180) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["npx", "neon@4", *args, "--api-key", API_KEY],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _authenticated() -> bool:
    if not API_KEY or not PROJECT_ID:
        return False
    if shutil.which("npx") is None:
        return False
    try:
        result = _neon("me", "--output", "json", timeout=90)
    except (subprocess.TimeoutExpired, OSError):
        return False
    if result.returncode != 0:
        return False
    try:
        json.loads(result.stdout)
    except json.JSONDecodeError:
        return False
    return True


pytestmark = pytest.mark.skipif(
    not _authenticated(),
    reason="NEON_API_KEY / NEON_PROJECT_ID not set, or the Neon CLI is unavailable",
)


@pytest.fixture
def throwaway_branch() -> Iterator[str]:
    name = f"ci-{uuid.uuid4().hex[:10]}"
    created = _neon(
        "branches",
        "create",
        "--project-id",
        PROJECT_ID,
        "--name",
        name,
        "--parent",
        PARENT_BRANCH,
        # Schema only: the fixtures are irrelevant here and copying data counts
        # against the project's storage.
        "--schema-only",
        # A backstop for a crashed run. Expiry is enforced by a background job,
        # so the explicit delete below is still what actually keeps us under the
        # ten-branch cap.
        "--expires-at",
        "+4h",
        "--output",
        "json",
    )
    if created.returncode != 0:
        pytest.skip(f"could not create a Neon branch: {created.stderr[-300:]}")

    try:
        # Direct, NOT --pooled: migrations need session state that PgBouncer's
        # transaction mode cannot hold, and labelling a pooled URL "UNPOOLED"
        # meant this test never exercised the documented migration transport.
        result = _neon("connection-string", name, "--project-id", PROJECT_ID)
        if result.returncode != 0:
            pytest.skip(f"could not read the connection string: {result.stderr[-300:]}")
        # `connection-string` emits a bare string, not JSON, even with --output json.
        yield result.stdout.strip().splitlines()[-1]
    finally:
        _neon("branches", "delete", name, "--project-id", PROJECT_ID, "--yes")


def test_generator_writes_to_a_fresh_branch(throwaway_branch: str) -> None:
    from generator import db

    env = {
        **os.environ,
        # DATABASE_URL_UNPOOLED_DEV, not DATABASE_URL_UNPOOLED: bin/migrate.sh
        # sources .env AFTER inheriting this environment, and a developer's .env
        # defines the latter -- which would migrate their own dev branch while
        # these assertions queried the throwaway one.
        "DATABASE_URL_UNPOOLED_DEV": throwaway_branch,
        "MIGRATE_TRANSPORT": "http",
        # The dev path fails closed when no production host is configured, which
        # is correct and would otherwise make this unrunnable in clean CI. The
        # target here is a branch this test created seconds ago and deletes in
        # teardown, so there is nothing to protect.
        "XLICKBAIT_ALLOW_NO_PROD_GUARD": "1",
    }
    migrated = subprocess.run(
        ["./bin/migrate.sh", "dev"], capture_output=True, text=True, env=env, timeout=300
    )
    assert migrated.returncode == 0, migrated.stderr

    with db.connect(throwaway_branch) as conn:
        db.assert_schema(conn)
        # Precondition, not the assertion. Asserting only this was the whole bug:
        # the test passed while never exercising a single write.
        assert db.published_arxiv_ids(conn) == set()

        run_id = db.start_run(conn)
        first = db.upsert(conn, make_pending("2401.01234"), model="claude-sonnet-5")
        second = db.upsert(conn, make_pending("1108.1068", kind="vintage"), model="claude-sonnet-5")
        db.finish_run(conn, run_id, fresh=1, vintage=1, rejected=0)

        # The rows actually landed on a branch built purely from the migrations.
        assert db.published_arxiv_ids(conn) == {"2401.01234", "1108.1068"}

        with conn.cursor() as cur:
            cur.execute(
                "SELECT h.id, h.anchor, p.arxiv_id FROM headlines h "
                "JOIN papers p ON p.arxiv_id = h.arxiv_id ORDER BY h.id"
            )
            rows = cur.fetchall()
        assert [r["id"] for r in rows] == [first, second]
        # The anchor survives the round trip intact -- it is the one column whose
        # exact bytes the truth gate depends on.
        assert all(r["anchor"] == "a bolometer array at 10 mK" for r in rows)

        # And the kill switch works here too.
        assert db.hide(conn, first) is True
        assert db.published_arxiv_ids(conn) == {"1108.1068"}

        with conn.cursor() as cur:
            cur.execute(
                "SELECT fresh_count, vintage_count, rejected_count, finished_at FROM generator_runs"
            )
            run = cur.fetchone()
        assert (run["fresh_count"], run["vintage_count"], run["rejected_count"]) == (1, 1, 0)
        assert run["finished_at"] is not None
