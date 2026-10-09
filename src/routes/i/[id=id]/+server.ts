import { error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { getHeadlineImage } from '$lib/server/db/queries';
import { setCache } from '$lib/server/page';
import { CACHE_WINDOWS } from '$lib/config';
import { TAGS } from '$lib/cache';

/**
 * One headline's illustration.
 *
 * The bytes live in Postgres rather than in object storage, which is a
 * deliberate trade and worth stating plainly: it keeps the whole system to one
 * Neon account and one write credential -- held only by the generator -- at the
 * cost of an origin round trip per image per CDN node, and of watching the
 * database's size. The generator caps each image at a few hundred kilobytes for
 * that second reason.
 *
 * Every request that gets past the CDN is a single indexed primary-key lookup,
 * and the response is held for a year, so "per CDN node" is the operative part.
 *
 * `setCache` rather than `setHeaders`, because `hooks.server.ts` is the only
 * place headers are written -- SvelteKit throws if a header is set twice in one
 * request, and going around the one place that knows that is how it happens.
 */
export const GET: RequestHandler = async (event) => {
	// The matcher already rejected anything that is not a bounded run of digits;
	// this is the second half of the same check, against what `Number` can
	// actually represent.
	const id = Number(event.params.id);
	if (!Number.isSafeInteger(id) || id <= 0) error(404, 'Not found');

	const image = await getHeadlineImage(id);
	// Also the path for a hidden headline: `getHeadlineImage` applies the same
	// visibility rule the pages do, so a takedown takes the picture with it.
	if (!image) error(404, 'Not found');

	const bytes = Buffer.from(image.base64, 'base64');
	// The generator writes `byte_size` from Python instead of letting Postgres
	// compute it, precisely so this comparison is possible. A mismatch means the
	// blob was truncated somewhere between the two, which in a binary column is
	// otherwise completely silent -- the reader just gets a broken image icon and
	// nobody ever finds out why.
	if (bytes.byteLength !== image.byteSize) {
		error(500, 'Image is corrupt');
	}

	setCache(event, {
		...CACHE_WINDOWS.image,
		tags: [TAGS.headline(id)],
		// Written once, and the URL is derived from the id: there is no later
		// revision for a reader to miss.
		immutable: true
	});

	return new Response(bytes, {
		headers: {
			'content-type': image.mime,
			'content-length': String(bytes.byteLength),
			// The bytes come from an image model and are served from our own
			// origin. Neither is a reason to let a browser sniff them into
			// something executable.
			'x-content-type-options': 'nosniff'
		}
	});
};
