"""Connection semantics, which the durability guarantees rest on.

These need no server: they check how the connection is opened, which is exactly
where the bug was. The behaviour they protect is only observable against a real
database, and by then a run has already been silently rolled back.
"""

from __future__ import annotations

from typing import Any

import pytest

from generator import db


class TestAutocommit:
    def test_connect_opens_an_autocommit_connection(self, monkeypatch):
        """The whole per-headline durability story depends on this one flag.

        psycopg defaults to autocommit=False. With that default the first SELECT
        -- `assert_schema()`, before anything is written -- opens an implicit
        transaction; every later `conn.transaction()` then nests inside it as a
        savepoint rather than committing; and the connection context manager
        rolls the entire run back when an exception leaves the block. The
        published headlines, the run row, AND the error recorded to explain the
        failure all disappear together.
        """
        captured: dict[str, Any] = {}

        class FakeConn:
            def __enter__(self) -> FakeConn:
                return self

            def __exit__(self, *exc: object) -> None:
                return None

        def fake_connect(url: str, **kwargs: Any) -> FakeConn:
            captured.update(kwargs)
            captured["url"] = url
            return FakeConn()

        monkeypatch.setattr(db.psycopg, "connect", fake_connect)

        with db.connect("postgresql://u:p@host/db"):
            pass

        assert captured.get("autocommit") is True, (
            "connect() must set autocommit=True, or conn.transaction() blocks "
            "degrade to savepoints and a failed run rolls back its own ledger"
        )
        assert captured["url"] == "postgresql://u:p@host/db"

    def test_every_write_helper_opens_its_own_transaction_block(self):
        """Each write must be its own top-level transaction, not a savepoint.

        Paired with autocommit, `conn.transaction()` is what makes that true.
        A helper that wrote without one would ride on whatever transaction
        happened to be open, which is the failure mode above in miniature.
        """
        import inspect

        for name in ("upsert", "start_run", "finish_run", "hide"):
            source = inspect.getsource(getattr(db, name))
            assert "conn.transaction()" in source, f"{name} does not open a transaction"


class TestSchemaAssertionIsReadOnly:
    def test_assert_schema_runs_no_ddl(self):
        """The generator never repairs the schema, at three in the morning or
        otherwise: a process that can 'fix' the database can also corrupt it."""
        import inspect

        source = inspect.getsource(db.assert_schema).lower()
        for forbidden in ("create ", "alter ", "drop ", "truncate "):
            assert forbidden not in source, f"assert_schema appears to run {forbidden.strip()}"

    @pytest.mark.parametrize("name", ["published_arxiv_ids", "assert_schema"])
    def test_read_helpers_do_not_write(self, name):
        import inspect

        source = inspect.getsource(getattr(db, name)).lower()
        for forbidden in ("insert into", "update ", "delete from"):
            assert forbidden not in source, f"{name} appears to write"
