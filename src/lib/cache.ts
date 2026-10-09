/**
 * CDN cache headers and the cache-tag vocabulary.
 *
 * This is a pure function of its inputs so it can be tested exhaustively without
 * a server, a port, or a network. `hooks.server.ts` is the only caller that
 * writes the result onto a real response.
 *
 * Two deliberate decisions, both of which come from how Netlify actually behaves
 * rather than how the docs read at a glance:
 *
 * 1. We emit BOTH the Netlify-specific and the standard header spellings.
 *    `Netlify-CDN-Cache-Control` and `Netlify-Cache-Tag` are consumed and then
 *    STRIPPED by Netlify before the response reaches the client, while
 *    `CDN-Cache-Control` and `Cache-Tag` are always passed downstream. Emitting
 *    only the Netlify pair would mean a curl check that passes locally (where
 *    there is no CDN to strip anything) and fails in production against the real
 *    one. Netlify prefers its own headers, so behaviour is unchanged.
 *
 * 2. `durable` appears only in the Netlify header. It is a Netlify extension
 *    that stores the response in a shared cache behind the edge nodes, and it has
 *    no meaning to any other CDN. It also has no effect on Edge Function
 *    responses -- which is one of the reasons SSR is pinned to a Node function.
 */

/** Cache tags. The Phase 2 generator purges by these exact strings. */
export const TAGS = {
	/** Every page. Purging this invalidates the entire site. */
	site: 'site',
	/** Any page showing a list of headlines: front page, day, category, pagination. */
	list: 'list',
	/** The Atom feed. */
	feed: 'feed',
	/** One headline's permalink. */
	headline: (id: number) => `h:${id}`,
	/** One UTC day page, keyed `day:YYYY-MM-DD`. */
	day: (dayKey: string) => `day:${dayKey}`,
	/** One category page. Dots are legal in a cache tag; `cs.LG` stays readable. */
	category: (category: string) => `cat:${category}`,
	/** The archive index. */
	archive: 'archive'
} as const;

export interface CacheOptions {
	/** Seconds the CDN may serve this without revalidating. */
	sMaxAge: number;
	/** Seconds the CDN may serve a stale copy while revalidating in background. */
	swr: number;
	/** Cache tags to attach. `site` is added automatically. */
	tags?: readonly string[];
	/**
	 * Content at this URL never changes, so the browser may hold it too.
	 *
	 * Only for `/i/<id>`: a headline's illustration is written once and the URL
	 * is derived from the id, so there is no revision to miss. Everything else on
	 * this site is content whose whole point is that it changes without a
	 * rebuild, and a browser holding it would defeat a purge for that reader.
	 *
	 * The browser TTL is deliberately an hour rather than a year even so. `hide`
	 * is a takedown, and a takedown that leaves the picture in ten thousand
	 * browser caches for twelve months is not one. An hour buys essentially all
	 * the benefit -- the CDN, which is purgeable, absorbs the rest.
	 */
	immutable?: boolean;
}

/**
 * How long a browser may hold an `immutable: true` response.
 *
 * Not `immutable` the Cache-Control directive, and not a year: see the note on
 * `CacheOptions.immutable`. The CDN still gets the full window, because the CDN
 * can be purged.
 */
const IMMUTABLE_BROWSER_MAX_AGE = 3600;

/** Netlify's documented limits. Exceeding them is a silently dropped tag. */
const MAX_TAGS = 500;
const MAX_TAG_LENGTH = 1024;

export function cacheTagValue(tags: readonly string[]): string {
	const unique = [...new Set([TAGS.site, ...tags])].filter(
		(t) => t.length > 0 && t.length <= MAX_TAG_LENGTH
	);
	return unique.slice(0, MAX_TAGS).join(',');
}

/**
 * Build the full header set for a cacheable HTML or feed response.
 *
 * The browser-facing `Cache-Control` deliberately says `max-age=0,
 * must-revalidate`: we want the CDN holding content for a minute, not a user's
 * browser holding it for a minute. Otherwise a reader who just saw a purge would
 * still be looking at the old front page.
 */
export function cacheHeaders({
	sMaxAge,
	swr,
	tags = [],
	immutable = false
}: CacheOptions): Record<string, string> {
	const shared = `public, s-maxage=${sMaxAge}, stale-while-revalidate=${swr}`;
	const tagValue = cacheTagValue(tags);
	return {
		'cache-control': immutable
			? `public, max-age=${IMMUTABLE_BROWSER_MAX_AGE}`
			: 'public, max-age=0, must-revalidate',
		'netlify-cdn-cache-control': `${shared}, durable`,
		'cdn-cache-control': shared,
		'netlify-cache-tag': tagValue,
		'cache-tag': tagValue
	};
}

/**
 * Shorten a cache window so it expires when the next scheduled headline goes
 * live, rather than up to a full stale-while-revalidate window afterwards.
 *
 * The CDN has no concept of `now()`, so a page rendered at 10:00 with a headline
 * scheduled for 10:01 would otherwise keep serving the pre-10:01 version until
 * its TTL lapsed. Clamping makes the cache entry expire exactly when the content
 * changes.
 *
 * Returns at least 1: a zero s-maxage would disable CDN caching entirely, and a
 * negative one is meaningless. `nextPublishAt` is null when nothing is scheduled.
 */
export function clampSMaxAge(sMaxAge: number, nextPublishAt: string | null, now: Date): number {
	if (!nextPublishAt) return sMaxAge;
	const until = Math.floor((new Date(nextPublishAt).getTime() - now.getTime()) / 1000);
	if (!Number.isFinite(until)) return sMaxAge;
	return Math.max(1, Math.min(sMaxAge, until));
}

/**
 * Clamp a whole cache window to the next scheduled publication.
 *
 * Clamping `s-maxage` alone is not enough, and that was a real hole. Once the
 * shortened TTL lapses, `stale-while-revalidate` still authorises the CDN to
 * serve THIS response -- the pre-publication one -- for up to another `swr`
 * seconds while it revalidates in the background. For the feed that is half an
 * hour of a headline being live in the database and absent from the page, which
 * is precisely the invisibility the clamp was added to prevent.
 *
 * So when the clamp actually binds -- when this entry's freshness ends at the
 * publication boundary rather than before it -- the stale window is dropped to
 * zero, forcing a synchronous revalidation at exactly that moment. When it does
 * not bind, the entry expires before anything changes and normal stale serving
 * is harmless, so it is left alone.
 */
export function clampWindow(
	window: { sMaxAge: number; swr: number },
	nextPublishAt: string | null,
	now: Date
): { sMaxAge: number; swr: number } {
	const sMaxAge = clampSMaxAge(window.sMaxAge, nextPublishAt, now);
	const binds = sMaxAge < window.sMaxAge;
	return { sMaxAge, swr: binds ? 0 : window.swr };
}

/** Headers for a response that must never be cached (404s, bad cursors). */
export function noCacheHeaders(): Record<string, string> {
	return {
		'cache-control': 'no-store',
		'netlify-cdn-cache-control': 'no-store',
		'cdn-cache-control': 'no-store'
	};
}
