import { error, redirect } from '@sveltejs/kit';
import type { PageServerLoad } from './$types';
import { getHeadline } from '$lib/server/db/queries';
import { loadChumbox, setCache } from '$lib/server/page';
import { headlinePath, imagePath, parseHeadlineSegment } from '$lib/slug';
import { CACHE_WINDOWS } from '$lib/config';
import { TAGS } from '$lib/cache';

export const load: PageServerLoad = async (event) => {
	const parsed = parseHeadlineSegment(event.params.entry);
	if (!parsed) error(404, 'Not found');

	const item = await getHeadline(parsed.id);
	if (!item) error(404, 'Not found');

	// Set cache directives BEFORE the redirect check. `redirect()` throws, so
	// anything after it is unreachable on the redirect path -- and a permanent
	// canonical redirect is exactly the sort of response worth holding at the CDN
	// rather than recomputing for every stale link on the internet.
	setCache(event, { ...CACHE_WINDOWS.item, tags: [TAGS.headline(item.id)] });

	// The id is authoritative and the slug is decoration, so a stale or wrong slug
	// still resolves and then redirects to the canonical spelling. That keeps old
	// links working after a headline is edited instead of turning them into 404s.
	const canonical = headlinePath(item.id, item.headline);
	if (event.url.pathname !== canonical) {
		redirect(301, canonical + event.url.search);
	}

	const chumbox = await loadChumbox(event, [item.id], CACHE_WINDOWS.item.sMaxAge);

	// Open Graph wants an absolute URL, and the origin comes from the request for
	// the same reason the feed derives its own: the site is served from a Netlify
	// preview domain as well as its own, and a baked-in origin makes every share
	// card on a preview point at production.
	//
	// Falls back to the static card when this headline has no illustration, which
	// is the only state the site had before images existed.
	const ogImage = new URL(item.image ? imagePath(item.id) : '/og-default.png', event.url.origin)
		.href;

	return { item, chumbox, canonical, ogImage };
};
