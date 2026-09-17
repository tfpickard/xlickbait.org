"""The kill switch, which has to work on the worst day rather than the best one.

There is no web admin: `python -m generator hide <id>` is the entire takedown
mechanism, and the footer promises authors it exists.
"""

from __future__ import annotations

import argparse
import contextlib
from collections.abc import Iterator
from typing import ClassVar

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


class TestRunWithoutIllustrations:
    """Regression: `command_run` read `images` on a path that never set it.

    `images` was assigned only inside `if illustrating and headline_ids:` and
    read unconditionally afterwards, so every path that skips illustration --
    no OPENROUTER_API_KEY, --no-images, a run that published nothing -- raised
    UnboundLocalError. That happened AFTER the headlines and the run record
    were committed but BEFORE the cache purge: a successful publish reported as
    a crash, with the new headlines stuck behind their old TTL. The common
    path, in other words.
    """

    @pytest.fixture
    def published(self, monkeypatch):
        """A run that publishes two headlines, with everything external stubbed."""
        from datetime import UTC, datetime

        from generator.db import PendingHeadline
        from generator.llm import Headline
        from generator.run import RunResult

        class Paper:
            arxiv_id = "2401.00001"
            title = "A Paper About Something"
            primary_category = "hep-ex"
            categories: ClassVar[list[str]] = ["hep-ex"]

        def make(n: int) -> PendingHeadline:
            return PendingHeadline(
                paper=Paper(),
                headline=Headline(headline=f"H{n}", dek="d", anchor="a", actual_point="p"),
                kind="fresh",
                publish_at=datetime(2026, 9, 17, 12, 0, tzinfo=UTC),
            )

        calls: list[list[str]] = []

        @contextlib.contextmanager
        def fake_connect(url: str) -> Iterator[object]:
            yield object()

        monkeypatch.setattr(cli.db, "connect", fake_connect)
        monkeypatch.setattr(cli.db, "assert_schema", lambda conn, images=False: None)
        monkeypatch.setattr(cli.db, "published_arxiv_ids", lambda conn: set())
        monkeypatch.setattr(cli.db, "start_run", lambda conn: 1)
        monkeypatch.setattr(cli.db, "finish_run", lambda conn, run_id, **kw: None)
        monkeypatch.setattr(cli.db, "upsert", lambda conn, item, *, model: 7)
        monkeypatch.setattr(cli, "ArxivClient", lambda **kw: contextlib.nullcontext(object()))
        monkeypatch.setattr(cli, "HeadlineWriter", lambda **kw: object())
        monkeypatch.setattr(cli, "generate", lambda **kw: RunResult(pending=[make(1), make(2)]))
        monkeypatch.setattr(
            cli.purge, "purge", lambda tags, *, token, site_id: calls.append(list(tags)) or 1
        )
        return calls

    def _args(self, **overrides) -> argparse.Namespace:
        base = dict(fresh=2, vintage=0, stagger=0.0, dry_run=False, no_images=False)
        base.update(overrides)
        return argparse.Namespace(**base)

    def test_a_run_with_no_api_key_still_publishes_and_purges(self, env, published, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

        assert cli.command_run(self._args()) == 0
        assert published, "the run must still purge; it published two headlines"

    def test_no_images_flag_still_publishes_and_purges(self, env, published, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")

        assert cli.command_run(self._args(no_images=True)) == 0
        assert published

    def test_the_purge_covers_the_lists_it_always_did(self, env, published, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

        cli.command_run(self._args())
        tags = published[0]
        assert tag_names.LIST in tags
        assert tag_names.FEED in tags
        # No image pass ran, so no permalink can have gone stale behind one.
        assert not any(t.startswith("h:") for t in tags)

    def test_illustrated_headlines_get_their_permalinks_purged(self, env, published, monkeypatch):
        """Regression: `tags_for` omits `h:<id>` for freshly published headlines.

        That was right when the insert was the last thing a run did -- nothing
        can have cached a permalink that did not exist. The image pass runs
        after the commit and takes the better part of a minute, so a reader or
        a crawler can cache the new permalink with the SVG fallback and the
        default OG card inside that window, and it would then keep it for
        sMaxAge + swr.
        """
        from datetime import UTC, datetime

        from generator.db import Illustratable
        from generator.run import IllustrationResult

        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")

        illustrated = [
            Illustratable(
                headline_id=7,
                headline="H1",
                dek="d",
                primary_category="hep-ex",
                categories=["hep-ex"],
                publish_at=datetime(2026, 9, 17, 12, 0, tzinfo=UTC),
            )
        ]
        monkeypatch.setattr(cli, "_painter", lambda cfg: contextlib.nullcontext(object()))
        monkeypatch.setattr(
            cli,
            "illustrate",
            lambda painter, targets, *, store: IllustrationResult(
                made=1, spent_usd=0.02, illustrated=illustrated
            ),
        )

        assert cli.command_run(self._args()) == 0
        tags = published[0]
        assert "h:7" in tags, "an illustrated permalink may already be cached without its image"
        # And the tags it always sent are still there.
        assert tag_names.LIST in tags
        assert tag_names.FEED in tags
