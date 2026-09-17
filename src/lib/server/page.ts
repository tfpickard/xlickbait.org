import type { RequestEvent } from '@sveltejs/kit';
import { getChumbox, type HeadlineCard } from './db/queries';
import type { CacheOptions } from '$lib/cache';

/**
 * Record cache directives for this request. `hooks.server.ts` applies them.
 */
export function setCache(event: RequestEvent, options: CacheOptions): void {
	event.locals.cache = options;
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
