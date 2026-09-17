import type { Handle } from '@sveltejs/kit';
import { cacheHeaders, noCacheHeaders } from '$lib/cache';

/**
 * Apply cache headers to every response, in exactly one place.
 *
 * Routes declare what they want via `event.locals.cache`; anything that does not
 * declare gets `no-store`, so a new route is uncached-but-correct by default
 * rather than accidentally cached with someone else's directives.
 */
function withHeaders(response: Response, headers: Record<string, string>): Response {
	try {
		for (const [key, value] of Object.entries(headers)) {
			response.headers.set(key, value);
		}
		return response;
	} catch {
		// Some responses -- notably those produced by `Response.redirect()` -- have
		// immutable headers, and setting one throws a TypeError. Rebuilding the
		// response is the documented way around it. This matters here because the
		// permalink canonicalisation path issues a redirect on every wrong-slug hit.
		const rebuilt = new Response(response.body, {
			status: response.status,
			statusText: response.statusText,
			headers: new Headers(response.headers)
		});
		for (const [key, value] of Object.entries(headers)) {
			rebuilt.headers.set(key, value);
		}
		return rebuilt;
	}
}

export const handle: Handle = async ({ event, resolve }) => {
	const response = await resolve(event);
	const cache = event.locals.cache;
	return withHeaders(response, cache ? cacheHeaders(cache) : noCacheHeaders());
};
