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
}

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
export function cacheHeaders({ sMaxAge, swr, tags = [] }: CacheOptions): Record<string, string> {
	const shared = `public, s-maxage=${sMaxAge}, stale-while-revalidate=${swr}`;
	const tagValue = cacheTagValue(tags);
	return {
		'cache-control': 'public, max-age=0, must-revalidate',
		'netlify-cdn-cache-control': `${shared}, durable`,
		'cdn-cache-control': shared,
		'netlify-cache-tag': tagValue,
		'cache-tag': tagValue
	};
}

/** Headers for a response that must never be cached (404s, bad cursors). */
export function noCacheHeaders(): Record<string, string> {
	return {
		'cache-control': 'no-store',
		'netlify-cdn-cache-control': 'no-store',
		'cdn-cache-control': 'no-store'
	};
}
