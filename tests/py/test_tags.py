"""The cache tag vocabulary is a cross-language contract. Prove both sides agree."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from generator import tags

REPO = Path(__file__).resolve().parents[2]


class TestPythonSide:
    def test_structured_tags(self):
        assert tags.headline(42) == "h:42"
        assert tags.day("2026-09-17") == "day:2026-09-17"
        assert tags.category("cs.LG") == "cat:cs.LG"

    def test_bare_tags(self):
        assert (tags.SITE, tags.LIST, tags.FEED, tags.ARCHIVE) == (
            "site",
            "list",
            "feed",
            "archive",
        )


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not available")
def test_python_and_typescript_produce_identical_tags():
    """Execute BOTH implementations and compare.

    This is the only cross-language contract in the project that fails silently.
    If the site tags a page `day:2026-09-17` and the generator purges
    `day-2026-09-17`, the purge matches nothing, the content never updates, and
    Netlify returns 202 Accepted every single time. Asserting against a hardcoded
    list here would only prove Python agrees with itself.
    """
    script = """
    import { TAGS } from './src/lib/cache.ts';
    console.log(JSON.stringify({
      site: TAGS.site, list: TAGS.list, feed: TAGS.feed, archive: TAGS.archive,
      headline: TAGS.headline(42),
      day: TAGS.day('2026-09-17'),
      category: TAGS.category('cs.LG'),
    }));
    """
    try:
        result = subprocess.run(
            ["npx", "tsx", "--eval", script],
            cwd=REPO,
            capture_output=True,
            text=True,
            timeout=180,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        # Skip only when the RUNNER is unavailable -- no npx on PATH, or it hung.
        pytest.skip(f"the TypeScript runner is not usable here: {exc}")

    # A non-zero exit is a FAILURE, not a skip. tsx is a checked-in dev
    # dependency, so the only way this exits non-zero with npx present is that
    # src/lib/cache.ts does not run -- and this is the one contract in the
    # project that otherwise fails silently, with 202 Accepted every time.
    assert result.returncode == 0, (
        f"src/lib/cache.ts did not execute, so the cross-language cache-tag "
        f"contract is unverified:\n{result.stderr[-800:]}"
    )

    ts = json.loads(result.stdout.strip().splitlines()[-1])
    assert ts == {
        "site": tags.SITE,
        "list": tags.LIST,
        "feed": tags.FEED,
        "archive": tags.ARCHIVE,
        "headline": tags.headline(42),
        "day": tags.day("2026-09-17"),
        "category": tags.category("cs.LG"),
    }
