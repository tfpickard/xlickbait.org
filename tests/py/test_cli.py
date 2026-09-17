"""The kill switch, which has to work on the worst day rather than the best one.

There is no web admin: `python -m generator hide <id>` is the entire takedown
mechanism, and the footer promises authors it exists.
"""

from __future__ import annotations

import argparse
import contextlib
from collections.abc import Iterator

import pytest

from generator import __main__ as cli
from generator import tags as tag_names


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("XLICKBAIT_DB_URL", "postgresql://user:pw@localhost/db")
    monkeypatch.setenv("NETLIFY_PURGE_TOKEN", "token")
    monkeypatch.setenv("NETLIFY_SITE_ID", "site-id")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


@pytest.fixture
def purges(monkeypatch):
    """Capture purge calls; stub the database out entirely."""
    calls: list[list[str]] = []

    @contextlib.contextmanager
    def fake_connect(url: str) -> Iterator[object]:
        yield object()

    monkeypatch.setattr(cli.db, "connect", fake_connect)
    monkeypatch.setattr(cli.db, "hide", lambda conn, headline_id: True)
    monkeypatch.setattr(
        cli.purge, "purge", lambda tags, *, token, site_id: calls.append(list(tags)) or 1
    )
    return calls


def test_hide_runs_without_an_anthropic_key(env, purges):
    # Regression: `hide` went through the full run config loader, so a missing or
    # freshly-rotated key made the emergency path exit before reaching the
    # database. It must not depend on credentials it never uses.
    assert cli.command_hide(argparse.Namespace(id=42)) == 0


def test_hide_purges_the_whole_site(env, purges):
    # Regression: it purged only h:<id>, list, feed and archive. But a hidden
    # headline also appears in the chumbox of OTHER headlines' permalinks, and
    # those pages carry only their own h:<id> tag -- so the removed item stayed
    # visible there for sMaxAge + swr, which is over an hour.
    cli.command_hide(argparse.Namespace(id=42))
    assert purges == [[tag_names.SITE]]


def test_hide_reports_failure_when_there_is_no_such_headline(env, purges, monkeypatch):
    monkeypatch.setattr(cli.db, "hide", lambda conn, headline_id: False)
    assert cli.command_hide(argparse.Namespace(id=999)) == 1
    # Nothing was purged, because nothing changed.
    assert purges == []


def test_hide_without_purge_credentials_still_hides(monkeypatch, purges):
    monkeypatch.setenv("XLICKBAIT_DB_URL", "postgresql://user:pw@localhost/db")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("NETLIFY_PURGE_TOKEN", raising=False)
    monkeypatch.delenv("NETLIFY_SITE_ID", raising=False)
    assert cli.command_hide(argparse.Namespace(id=42)) == 0
    # No credentials means no request at all -- never an empty tag list, which
    # Netlify treats as "purge nothing" while a missing key purges everything.
    assert purges == []
