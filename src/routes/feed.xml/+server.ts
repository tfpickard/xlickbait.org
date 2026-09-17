import type { RequestHandler } from './$types';
import { listFeedEntries } from '$lib/server/db/queries';
import { setTimeSensitiveCache } from '$lib/server/page';
import { renderAtomFeed } from '$lib/feed';
import { CACHE_WINDOWS, FEED_SIZE } from '$lib/config';
import { TAGS } from '$lib/cache';

export const GET: RequestHandler = async (event) => {
	const items = await listFeedEntries(FEED_SIZE);

	// `event.url.origin` rather than a configured constant, so the feed is
	// self-consistent on localhost, on a deploy preview and in production without
	// needing three different builds.
	const body = renderAtomFeed({
		origin: event.url.origin,
		items,
		updated: new Date().toISOString()
	});

	// Cache directives still go through locals, so the feed obeys exactly the same
	// code path -- and the same tag vocabulary -- as every HTML response.
	await setTimeSensitiveCache(event, CACHE_WINDOWS.feed, [TAGS.feed]);

	return new Response(body, {
		headers: { 'content-type': 'application/atom+xml; charset=utf-8' }
	});
};
