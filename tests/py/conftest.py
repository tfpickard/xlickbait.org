"""Shared fixtures. No network, no database, no API key."""

from __future__ import annotations

import pytest

ATOM_NS = (
    'xmlns="http://www.w3.org/2005/Atom" '
    'xmlns:arxiv="http://arxiv.org/schemas/atom" '
    'xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/"'
)


def entry(
    arxiv_id: str = "2401.01234",
    version: int = 1,
    title: str = "A Refined Upper Bound on Neutrino Mass",
    summary: str = "We report a bound using a bolometer array operated at 10 mK.",
    comment: str | None = None,
    primary: str = "hep-ex",
    categories: tuple[str, ...] = ("hep-ex", "physics.ins-det"),
) -> str:
    comment_xml = f"<arxiv:comment>{comment}</arxiv:comment>" if comment else ""
    cats = "".join(
        f'<category term="{c}" scheme="http://arxiv.org/schemas/atom"/>' for c in categories
    )
    return f"""
  <entry>
    <id>http://arxiv.org/abs/{arxiv_id}v{version}</id>
    <title>{title}</title>
    <summary>{summary}</summary>
    <published>2024-01-15T17:55:28Z</published>
    <updated>2024-01-20T10:00:00Z</updated>
    <author><name>R. Alvarez</name></author>
    <author><name>M. Okonkwo</name></author>
    <arxiv:primary_category term="{primary}"/>
    {cats}
    {comment_xml}
    <link href="https://arxiv.org/abs/{arxiv_id}v{version}" rel="alternate" type="text/html"/>
  </entry>"""


def feed(*entries: str, total: int | None = None) -> str:
    count = len(entries) if total is None else total
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<feed {ATOM_NS}>
  <title>arXiv Search Results</title>
  <id>https://arxiv.org/</id>
  <updated>2026-09-17T00:00:00Z</updated>
  <opensearch:totalResults>{count}</opensearch:totalResults>
  {"".join(entries)}
</feed>"""


@pytest.fixture
def make_entry():
    return entry


@pytest.fixture
def make_feed():
    return feed
