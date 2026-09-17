"""Command line entry point.

python -m generator run [--fresh N] [--vintage M] [--stagger HOURS] [--dry-run]
python -m generator hide <id>
"""

from __future__ import annotations

import argparse
import random
import sys
from datetime import UTC, datetime

from generator import config as config_module
from generator import db, purge
from generator.arxiv.client import ArxivClient
from generator.db import SchemaMismatch
from generator.llm import HeadlineWriter
from generator.run import generate, tags_for


def _print_pending(result: object) -> None:
    from generator.run import RunResult

    assert isinstance(result, RunResult)
    for item in result.pending:
        print(f"\n  [{item.kind}] {item.paper.arxiv_id}  publish_at={item.publish_at.isoformat()}")
        print(f"    headline : {item.headline.headline}")
        print(f"    dek      : {item.headline.dek}")
        print(f"    anchor   : {item.headline.anchor!r}")
        print(f"    actual   : {item.headline.actual_point}")
        print(f"    paper    : {item.paper.title[:96]}")
    for note in result.notes:
        print(f"  note: {note}")


def command_run(args: argparse.Namespace) -> int:
    cfg = config_module.load(fresh=args.fresh, vintage=args.vintage)
    rng = random.Random()
    now = datetime.now(UTC)

    with db.connect(cfg.database_url) as conn:
        try:
            db.assert_schema(conn)
        except SchemaMismatch as exc:
            print(str(exc), file=sys.stderr)
            return 1

        already = db.published_arxiv_ids(conn)

        # A dry run records nothing at all, including its own generator_runs row.
        # "Every run is recorded" and "touches nothing" would otherwise be in
        # direct conflict, and "touches nothing" is the one people rely on.
        run_id = None if args.dry_run else db.start_run(conn)

        try:
            with ArxivClient(
                user_agent=cfg.user_agent,
                min_interval=cfg.request_interval,
                max_retries=cfg.max_retries,
            ) as client:
                writer = HeadlineWriter(api_key=cfg.anthropic_api_key, model=cfg.model)
                result = generate(
                    config=cfg,
                    client=client,
                    writer=writer,
                    already_published=already,
                    stagger_hours=args.stagger,
                    rng=rng,
                    now=now,
                )
        except Exception as exc:
            if run_id is not None:
                db.finish_run(conn, run_id, fresh=0, vintage=0, rejected=0, error=str(exc))
            raise

        if args.dry_run:
            print(
                f"DRY RUN -- would insert {len(result.pending)} headlines "
                f"({result.fresh_count} fresh, {result.vintage_count} vintage); "
                f"{result.rejected} truth-gate rejections. Nothing was written."
            )
            _print_pending(result)
            return 0

        headline_ids = [db.upsert(conn, item, model=cfg.model) for item in result.pending]
        assert run_id is not None
        db.finish_run(
            conn,
            run_id,
            fresh=result.fresh_count,
            vintage=result.vintage_count,
            rejected=result.rejected,
        )

    print(
        f"published {len(headline_ids)} headlines "
        f"({result.fresh_count} fresh, {result.vintage_count} vintage); "
        f"{result.rejected} truth-gate rejections"
    )
    _print_pending(result)

    if cfg.can_purge:
        tags = tags_for(result.pending, headline_ids)
        assert cfg.netlify_purge_token and cfg.netlify_site_id
        made = purge.purge(tags, token=cfg.netlify_purge_token, site_id=cfg.netlify_site_id)
        print(f"purged {len(tags)} cache tags in {made} request(s)")
    else:
        print("no purge credentials configured; new headlines appear as the CDN TTL lapses")
    return 0


def command_hide(args: argparse.Namespace) -> int:
    cfg = config_module.load()
    with db.connect(cfg.database_url) as conn:
        if not db.hide(conn, args.id):
            print(f"no headline with id {args.id}", file=sys.stderr)
            return 1
    print(f"headline {args.id} is now hidden")

    if cfg.can_purge:
        from generator import tags as tag_names

        assert cfg.netlify_purge_token and cfg.netlify_site_id
        purge.purge(
            [tag_names.headline(args.id), tag_names.LIST, tag_names.FEED, tag_names.ARCHIVE],
            token=cfg.netlify_purge_token,
            site_id=cfg.netlify_site_id,
        )
        print("purged its cache tags")
    else:
        print("no purge credentials configured; it disappears as the CDN TTL lapses")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m generator")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="generate and publish headlines")
    run.add_argument("--fresh", type=int, default=None, help="fresh picks (clamped to 2-5)")
    run.add_argument("--vintage", type=int, default=None, help="vintage picks")
    run.add_argument(
        "--stagger",
        type=float,
        default=0.0,
        help="spread publish_at randomly across the next N hours",
    )
    run.add_argument(
        "--dry-run",
        action="store_true",
        help="print what would be inserted and write nothing at all",
    )
    run.set_defaults(func=command_run)

    hide = sub.add_parser("hide", help="hide a headline (the kill switch)")
    hide.add_argument("id", type=int)
    hide.set_defaults(func=command_hide)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
