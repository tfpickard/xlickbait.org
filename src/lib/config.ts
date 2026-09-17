/**
 * Every tunable in one place. Phase 2's generator has a matching Python module;
 * anything shared between them (notably the cache tag vocabulary in `cache.ts`)
 * is documented in CLAUDE.md so the two cannot drift silently.
 */

export const SITE_NAME = 'xlickbait';
/** The masthead only. Body copy, <title>, OG tags and the feed stay ASCII. */
export const SITE_WORDMARK = 'χLICKBAIT';
export const SITE_TAGLINE = 'THE PREPRINT AUTHORITY';

/** Headlines per "More stories" page. */
export const PAGE_SIZE = 12;
/** Fresh items in the BREAKING grid, after the hero takes the newest one. */
export const BREAKING_COUNT = 6;
/** Vintage items in FROM THE ARCHIVE. */
export const VINTAGE_COUNT = 4;
/** Entries in the Atom feed. */
export const FEED_SIZE = 50;

export const CHUMBOX_MIN = 6;
export const CHUMBOX_MAX = 9;

/**
 * CDN cache windows, in seconds.
 *
 * These set how long a scheduled headline can sit invisible after its
 * `publish_at` passes: worst case is roughly `sMaxAge + swr`, because a stale
 * response may still be served while revalidation happens in the background.
 * Sixty seconds of fresh plus five minutes of stale keeps "new headlines appear
 * within minutes" true without hammering the database.
 */
export const CACHE_WINDOWS = {
	/** Front page, day pages, category pages, paginated lists. */
	list: { sMaxAge: 60, swr: 300 },
	/** Permalinks -- a published headline's content does not change. */
	item: { sMaxAge: 300, swr: 3600 },
	/** Archive index: counts per day, changes slowly. */
	archive: { sMaxAge: 300, swr: 1800 },
	/** Atom feed. */
	feed: { sMaxAge: 300, swr: 1800 },
	/**
	 * Headline illustrations.
	 *
	 * A year, because the bytes at `/i/<id>` are written once and the URL is
	 * derived from the id: there is no later revision for a reader to miss. This
	 * is the one response on the site the browser is allowed to keep as well (see
	 * `CacheOptions.immutable`), which matters because it is also the only one
	 * that costs a hundred kilobytes.
	 */
	image: { sMaxAge: 31_536_000, swr: 86_400 }
} as const;

/** Canonical arXiv abs URL for a paper. Never a PDF, never full text. */
export function absUrl(arxivId: string): string {
	return `https://arxiv.org/abs/${arxivId}`;
}
