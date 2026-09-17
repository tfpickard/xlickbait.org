import type { RequestEvent } from '@sveltejs/kit';
import { getChumbox, nextScheduledAt, type HeadlineCard } from './db/queries';
import { clampSMaxAge, type CacheOptions } from '$lib/cache';

/**
 * Record cache directives for this request. `hooks.server.ts` applies them.
 */
export function setCache(event: RequestEvent, options: CacheOptions): void {
	event.locals.cache = options;
}

/**
 * Cache a response whose contents depend on `publish_at <= now()`.
 *
 * Shortens the window so the cache entry expires when the next scheduled
 * headline is due, instead of leaving it invisible for up to a full
 * stale-while-revalidate window. Permalinks do not need this -- a published
 * headline's own content does not change on a timer.
 */
export async function setTimeSensitiveCache(
	event: RequestEvent,
	window: { sMaxAge: number; swr: number },
	tags: readonly string[]
): Promise<void> {
	const next = await nextScheduledAt();
	setCache(event, {
		...window,
		sMaxAge: clampSMaxAge(window.sMaxAge, next, new Date()),
		tags
	});
}

/**
 * Load the chumbox for a page, excluding whatever is already on it.
 *
 * The seed combines the route id with a coarse time bucket. Within one CDN cache
 * window every request for this URL produces the same selection, so the cached
 * HTML is internally consistent; in the next window it reshuffles. Seeding from
 * the clock directly would make the response unreproducible and the test
 * meaningless.
 */
export async function loadChumbox(
	event: RequestEvent,
	excludeIds: readonly number[],
	bucketSeconds: number
): Promise<HeadlineCard[]> {
	const bucket = Math.floor(Date.now() / (bucketSeconds * 1000));
	const seed = `${event.url.pathname}${event.url.search}:${bucket}`;
	return getChumbox(excludeIds, seed);
}
