import { execFileSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { beforeAll, describe, expect, it } from 'vitest';

/**
 * Assertions against the BUILT Netlify function.
 *
 * The unit tests around `cacheHeaders()` prove the helper computes the right
 * directives. They cannot prove those directives survive the trip through
 * `hooks.server.ts`, SvelteKit's response handling and the adapter's wrapper.
 * This does.
 *
 * It runs the handler in a separate Node process via `tests/probe-built.mjs`,
 * because importing the bundle into Vitest puts it back through Vite's transform
 * pipeline -- which changes its behaviour and would mean testing something other
 * than the artifact that gets deployed.
 *
 * What this still does NOT prove is that Netlify's CDN acts on these headers.
 * There is no CDN here. That is only observable on a deployed site via
 * `Cache-Status`, and it is tracked as a post-deploy check rather than quietly
 * folded in.
 *
 * Skips unless `npm run build` has run, so a fresh checkout is not red for the
 * wrong reason; `npm run test:built` does both in order.
 */

const HANDLER = fileURLToPath(
	new URL('../../.netlify/functions-internal/sveltekit-render.mjs', import.meta.url)
);
const PROBE = fileURLToPath(new URL('../probe-built.mjs', import.meta.url));
const runnable = existsSync(HANDLER) && Boolean(process.env.DATABASE_URL);
const describeBuilt = runnable ? describe : describe.skip;

interface Probe {
	path: string;
	status: number;
	headers: Record<string, string>;
	body: string;
}

function probe(...paths: string[]): Probe[] {
	const out = execFileSync('node', [PROBE, ...paths], {
		env: process.env,
		encoding: 'utf8',
		maxBuffer: 32 * 1024 * 1024
	});
	return JSON.parse(out) as Probe[];
}

describeBuilt('the built SSR function', () => {
	let permalink: string;
	let headlineId: string;

	beforeAll(() => {
		// Take a permalink from the feed rather than scraping HTML: SvelteKit
		// renders internal hrefs relative to the current page, while the feed
		// carries absolute URLs by construction.
		const [feed] = probe('/feed.xml') as [Probe];
		const match = /rel="alternate" type="text\/html" href="[^"]*(\/h\/(\d+)-[^"]*)"/.exec(
			feed.body
		);
		if (!match) throw new Error('no permalink found in the feed');
		permalink = match[1] as string;
		headlineId = match[2] as string;
	});

	it('serves the front page with both cache-header spellings', () => {
		const [home] = probe('/') as [Probe];
		expect(home.status).toBe(200);
		// The Netlify-prefixed header is what its CDN reads; the standard one is
		// what survives to a client in production, where the former is stripped.
		expect(home.headers['netlify-cdn-cache-control']).toBe(
			'public, s-maxage=60, stale-while-revalidate=300, durable'
		);
		expect(home.headers['cdn-cache-control']).toBe(
			'public, s-maxage=60, stale-while-revalidate=300'
		);
		expect(home.headers['cache-control']).toBe('public, max-age=0, must-revalidate');
		expect(home.headers['cache-tag']).toBe('site,list');
		expect(home.headers['netlify-cache-tag']).toBe('site,list');
	});

	it('tags a permalink with its own id so one story can be purged alone', () => {
		const [page] = probe(permalink) as [Probe];
		expect(page.status).toBe(200);
		expect(page.headers['cache-tag']).toBe(`site,h:${headlineId}`);
	});

	it('serves the feed as Atom with the feed tag', () => {
		const [feed] = probe('/feed.xml') as [Probe];
		expect(feed.status).toBe(200);
		expect(feed.headers['content-type']).toContain('application/atom+xml');
		expect(feed.headers['cache-tag']).toBe('site,feed');
	});

	it('refuses to cache a 404', () => {
		const [missing] = probe('/definitely-not-a-page') as [Probe];
		expect(missing.status).toBe(404);
		expect(missing.headers['cache-control']).toBe('no-store');
		expect(missing.headers['netlify-cdn-cache-control']).toBe('no-store');
		expect(missing.headers['cache-tag']).toBeUndefined();
	});

	it('redirects a wrong slug and caches the redirect itself', () => {
		const [redirect] = probe(`/h/${headlineId}-wrong-slug-entirely`) as [Probe];
		expect(redirect.status).toBe(301);
		expect(redirect.headers['location']).toContain(`/h/${headlineId}-`);
		// This also proves the immutable-headers fallback in hooks.server.ts works:
		// a redirect Response rejects header mutation, so the tag is only present
		// if the response was rebuilt rather than mutated.
		expect(redirect.headers['cache-tag']).toBe(`site,h:${headlineId}`);
	});

	it('rejects a malformed cursor rather than serving page one', () => {
		const [bad] = probe('/?cursor=not-a-real-cursor') as [Probe];
		expect(bad.status).toBe(400);
	});

	it('tags a day page and a category page distinctly', () => {
		const [day, category] = probe('/2026/09/17', '/c/cs.LG') as [Probe, Probe];
		expect(day.status).toBe(200);
		expect(day.headers['cache-tag']).toBe('site,list,day:2026-09-17');
		expect(category.status).toBe(200);
		expect(category.headers['cache-tag']).toBe('site,list,cat:cs.LG');
	});
});
