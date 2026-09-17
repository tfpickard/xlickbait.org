"""Netlify cache tags.

THIS MUST AGREE EXACTLY WITH `src/lib/cache.ts`.

It is the only cross-language contract in the project that fails silently: if
the site tags a page `day:2026-09-17` and the generator purges `day-2026-09-17`,
the purge matches nothing, the content never updates, and Netlify returns
202 Accepted every single time. There is a test that executes both
implementations and compares their output for the same inputs.
"""

from __future__ import annotations

SITE = "site"
LIST = "list"
FEED = "feed"
ARCHIVE = "archive"


def headline(headline_id: int) -> str:
    return f"h:{headline_id}"


def day(day_key: str) -> str:
    """`day_key` is a UTC date, `YYYY-MM-DD`."""
    return f"day:{day_key}"


def category(name: str) -> str:
    return f"cat:{name}"
