"""Command line entry point.

python -m generator run [--fresh N] [--vintage M] [--stagger HOURS] [--dry-run]
python -m generator images [--limit N]
python -m generator hide <id>
"""

from __future__ import annotations

import argparse
import contextlib
import random
import sys
from datetime import UTC, datetime

from generator import config as config_module
from generator import db, purge
from generator.arxiv.client import ArxivClient
from generator.db import SchemaMismatch
from generator.image import ImagePainter
from generator.llm import HeadlineWriter
from generator.run import generate, illustrate, tags_for, tags_for_illustrations, targets_for


def _painter(cfg: config_module.Config) -> ImagePainter:
    assert cfg.openrouter_api_key
    return ImagePainter(
        api_key=cfg.openrouter_api_key,
        model=cfg.image_model,
        style=cfg.image_style,
        aspect_ratio=cfg.image_aspect_ratio,
        quality=cfg.image_quality,
        max_width=cfg.image_max_width,
        max_bytes=cfg.image_max_bytes,
        webp_quality=cfg.image_webp_quality,
        budget_usd=cfg.image_budget_usd,
        assumed_cost_usd=cfg.image_assumed_cost_usd,
        timeout=cfg.image_timeout,
    )


def _report_images(result: object) -> None:
    from generator.run import IllustrationResult

    assert isinstance(result, IllustrationResult)
    print(
        f"illustrated {result.made} headlines with {result.spent_usd:.4f} USD "
        f"of image generation ({result.failed} failed)"
    )
    for note in result.notes:
        print(f"  note: {note}")


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
    # --no-images turns the whole thing off for one invocation, so a run can go
    # out while an image model is misbehaving without editing the cron env file.
    illustrating = cfg.can_illustrate and not args.no_images
    rng = random.Random()
    now = datetime.now(UTC)

    with db.connect(cfg.database_url) as conn:
        try:
            db.assert_schema(conn, images=illustrating)
        except SchemaMismatch as exc:
            print(str(exc), file=sys.stderr)
            return 1

        already = db.published_arxiv_ids(conn)

        # A dry run records nothing at all, including its own generator_runs row.
        # "Every run is recorded" and "touches nothing" would otherwise be in
        # direct conflict, and "touches nothing" is the one people rely on.
        run_id = None if args.dry_run else db.start_run(conn)

        # Persistence lives inside this handler, not after it. Each upsert commits
        # on its own, so a failure partway through leaves headlines published; if
        # the write phase sat outside, that run would keep an unfinished
        # generator_runs row with no error and no counts -- the ledger losing
        # exactly the event it exists to record.
        result = None
        persisted = 0
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

            if args.dry_run:
                print(
                    f"DRY RUN -- would insert {len(result.pending)} headlines "
                    f"({result.fresh_count} fresh, {result.vintage_count} vintage); "
                    f"{result.rejected} truth-gate rejections. Nothing was written."
                )
                _print_pending(result)
                return 0

            headline_ids = []
            for item in result.pending:
                headline_ids.append(db.upsert(conn, item, model=cfg.model))
                persisted += 1

            # After the headlines are committed, never before. An image is
            # decoration on something that is already published; generating one
            # first would mean a slow or failing image model delaying -- or, on
            # an unhandled error, losing -- the thing people actually came for.
            if illustrating and headline_ids:
                with _painter(cfg) as painter:
                    images = illustrate(
                        painter,
                        targets_for(result.pending, headline_ids),
                        store=lambda hid, img: db.upsert_image(conn, hid, img),
                    )

            assert run_id is not None
            db.finish_run(
                conn,
                run_id,
                fresh=result.fresh_count,
                vintage=result.vintage_count,
                rejected=result.rejected,
            )
        except Exception as exc:
            if run_id is not None:
                detail = str(exc)
                if result is not None:
                    detail += f" (persisted {persisted} of {len(result.pending)} headlines)"
                # Never let the bookkeeping write mask the real failure.
                with contextlib.suppress(Exception):
                    db.finish_run(
                        conn,
                        run_id,
                        fresh=result.fresh_count if result else 0,
                        vintage=result.vintage_count if result else 0,
                        rejected=result.rejected if result else 0,
                        error=detail,
                    )
            raise

    print(
        f"published {len(headline_ids)} headlines "
        f"({result.fresh_count} fresh, {result.vintage_count} vintage); "
        f"{result.rejected} truth-gate rejections"
    )
    _print_pending(result)
    if images is not None:
        _report_images(images)
    elif cfg.can_illustrate:
        print("images skipped (--no-images)")
    else:
        print("no OPENROUTER_API_KEY; headlines keep their generated SVG thumbnails")

    if cfg.can_purge:
        tags = tags_for(result.pending, headline_ids)
        assert cfg.netlify_purge_token and cfg.netlify_site_id
        made = purge.purge(tags, token=cfg.netlify_purge_token, site_id=cfg.netlify_site_id)
        print(f"purged {len(tags)} cache tags in {made} request(s)")
    else:
        print("no purge credentials configured; new headlines appear as the CDN TTL lapses")
    return 0


def command_images(args: argparse.Namespace) -> int:
    """Backfill illustrations for headlines that do not have one.

    Uses `load_for_images` rather than the full loader for the same reason
    `hide` does: this needs a database, a key and the image knobs, and must not
    be blocked by an arXiv or Anthropic setting it will never read.
    """
    cfg = config_module.load_for_images()
    if not cfg.can_illustrate:
        print(
            "no OPENROUTER_API_KEY set (or XLICKBAIT_IMAGES is off); nothing to do",
            file=sys.stderr,
        )
        return 1

    with db.connect(cfg.database_url) as conn:
        try:
            db.assert_schema(conn, images=True)
        except SchemaMismatch as exc:
            print(str(exc), file=sys.stderr)
            return 1

        if args.limit < 1:
            print("--limit must be a positive integer", file=sys.stderr)
            return 1
        targets = db.headlines_missing_images(conn, limit=args.limit)
        if not targets:
            print("every published headline already has an image")
            return 0

        if args.dry_run:
            print(f"DRY RUN -- would illustrate {len(targets)} headlines. Nothing was written.")
            for target in targets:
                print(f"  [{target.headline_id}] {target.headline}")
            return 0

        with _painter(cfg) as painter:
            result = illustrate(
                painter, targets, store=lambda hid, img: db.upsert_image(conn, hid, img)
            )

    _report_images(result)

    # Unlike a fresh run, these headlines have been on cached pages for a while
    # with an <img> whose URL was returning 404. Nothing invalidates those pages
    # on its own, so the purge is the half of this command that makes the other
    # half visible.
    tags = tags_for_illustrations(result.illustrated)
    if tags and cfg.can_purge:
        assert cfg.netlify_purge_token and cfg.netlify_site_id
        made = purge.purge(tags, token=cfg.netlify_purge_token, site_id=cfg.netlify_site_id)
        print(f"purged {len(tags)} cache tags in {made} request(s)")
    elif tags:
        print("no purge credentials configured; images appear as the CDN TTL lapses")
    return 0


def command_hide(args: argparse.Namespace) -> int:
    # Database and purge only -- no generation settings are read or validated,
    # so a bad cron tuning value cannot disable the takedown path.
    cfg = config_module.load_for_hide()
    with db.connect(cfg.database_url) as conn:
        if not db.hide(conn, args.id):
            print(f"no headline with id {args.id}", file=sys.stderr)
            return 1
    print(f"headline {args.id} is now hidden")

    if cfg.can_purge:
        from generator import tags as tag_names

        assert cfg.netlify_purge_token and cfg.netlify_site_id
        # Deliberately blunt: `site` and not just this headline's own tags. A
        # hidden headline also sits in the chumbox of other headlines' permalinks,
        # and those pages are tagged only with their OWN h:<id> -- so purging
        # h:<this id> would leave the removed item on screen there for up to
        # sMaxAge + swr, which is over an hour. A takedown that half-works is not
        # a takedown, and this runs rarely enough that the cost does not matter.
        purge.purge(
            [tag_names.SITE],
            token=cfg.netlify_purge_token,
            site_id=cfg.netlify_site_id,
        )
        print("purged the whole site (the headline can appear in other pages' chumboxes)")
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
    run.add_argument(
        "--no-images",
        action="store_true",
        help="publish without illustrations, whatever the environment says",
    )
    run.set_defaults(func=command_run)

    images = sub.add_parser("images", help="backfill illustrations for headlines without one")
    images.add_argument(
        "--limit", type=int, default=10, help="how many headlines to illustrate (default 10)"
    )
    images.add_argument(
        "--dry-run", action="store_true", help="list what would be illustrated and write nothing"
    )
    images.set_defaults(func=command_images)

    hide = sub.add_parser("hide", help="hide a headline (the kill switch)")
    hide.add_argument("id", type=int)
    hide.set_defaults(func=command_hide)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
