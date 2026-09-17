import type { CacheOptions } from '$lib/cache';

declare global {
	namespace App {
		interface Locals {
			/**
			 * Cache directives for this response, set by a route's load function and
			 * applied once in `hooks.server.ts`.
			 *
			 * This is centralised rather than set per-route with `setHeaders()`
			 * because SvelteKit throws if the same header is set twice during one
			 * request -- including across a layout load and a page load, which is
			 * exactly the shape this app has.
			 */
			cache?: CacheOptions;
		}
	}
}

export {};
