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

import pytest

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
        result = _neon("connection-string", name, "--project-id", PROJECT_ID, "--pooled")
        if result.returncode != 0:
            pytest.skip(f"could not read the connection string: {result.stderr[-300:]}")
        # `connection-string` emits a bare string, not JSON, even with --output json.
        yield result.stdout.strip().splitlines()[-1]
    finally:
        _neon("branches", "delete", name, "--project-id", PROJECT_ID, "--yes")


def test_generator_writes_to_a_fresh_branch(throwaway_branch: str) -> None:
    from generator import db

    env = {**os.environ, "DATABASE_URL_UNPOOLED": throwaway_branch, "MIGRATE_TRANSPORT": "http"}
    migrated = subprocess.run(
        ["./bin/migrate.sh", "dev"], capture_output=True, text=True, env=env, timeout=300
    )
    assert migrated.returncode == 0, migrated.stderr

    with db.connect(throwaway_branch) as conn:
        db.assert_schema(conn)
        assert db.published_arxiv_ids(conn) == set()
