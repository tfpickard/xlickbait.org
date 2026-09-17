import { describe, expect, it } from 'vitest';
import { TAGS, cacheHeaders, cacheTagValue, clampSMaxAge, noCacheHeaders } from '$lib/cache';

describe('cacheHeaders', () => {
	const headers = cacheHeaders({ sMaxAge: 60, swr: 300, tags: [TAGS.list] });

	it('emits both the Netlify and the standard spellings', () => {
		// Netlify consumes and strips its own headers before the response reaches
		// the client, while the standard ones are passed downstream. Emitting only
		// the Netlify pair would give a curl check that passes locally and fails in
		// production, which is worse than having no check.
		expect(headers['netlify-cdn-cache-control']).toBeDefined();
		expect(headers['cdn-cache-control']).toBeDefined();
		expect(headers['netlify-cache-tag']).toBeDefined();
		expect(headers['cache-tag']).toBeDefined();
	});

	it('puts durable only on the Netlify header', () => {
		// `durable` is a Netlify extension. Advertising it to other CDNs is noise at
		// best and a parse failure at worst.
		expect(headers['netlify-cdn-cache-control']).toContain('durable');
		expect(headers['cdn-cache-control']).not.toContain('durable');
	});

	it('keeps the browser revalidating while the CDN holds the copy', () => {
		// A reader who arrives just after a purge must not be looking at their own
		// browser's minute-old copy.
		expect(headers['cache-control']).toBe('public, max-age=0, must-revalidate');
		expect(headers['cdn-cache-control']).toBe('public, s-maxage=60, stale-while-revalidate=300');
	});

	it('always includes the site-wide tag so everything is purgeable at once', () => {
		expect(headers['cache-tag']?.split(',')).toContain('site');
	});

	it('agrees between the two tag spellings', () => {
		expect(headers['cache-tag']).toBe(headers['netlify-cache-tag']);
	});
});

describe('cacheTagValue', () => {
	it('de-duplicates and comma-separates without spaces', () => {
		expect(cacheTagValue(['list', 'list', 'site'])).toBe('site,list');
	});

	it('drops tags longer than Netlify accepts rather than truncating them', () => {
		// A truncated tag is a DIFFERENT tag: it would silently never be purged.
		const tooLong = 'x'.repeat(1025);
		expect(cacheTagValue([tooLong])).toBe('site');
		expect(cacheTagValue(['x'.repeat(1024)]).split(',')).toHaveLength(2);
	});

	it('caps the tag count at the documented limit', () => {
		const many = Array.from({ length: 600 }, (_, i) => `t${i}`);
		expect(cacheTagValue(many).split(',')).toHaveLength(500);
	});

	it('builds readable structured tags', () => {
		expect(TAGS.headline(42)).toBe('h:42');
		expect(TAGS.day('2026-09-17')).toBe('day:2026-09-17');
		expect(TAGS.category('cs.LG')).toBe('cat:cs.LG');
	});
});

describe('noCacheHeaders', () => {
	it('tells every layer not to store', () => {
		const headers = noCacheHeaders();
		expect(headers['cache-control']).toBe('no-store');
		expect(headers['cdn-cache-control']).toBe('no-store');
		expect(headers['netlify-cdn-cache-control']).toBe('no-store');
	});

	it('attaches no tags, because there is nothing to purge', () => {
		expect(noCacheHeaders()['cache-tag']).toBeUndefined();
	});
});

describe('clampSMaxAge', () => {
	const now = new Date('2026-09-17T12:00:00.000Z');

	it('leaves the window alone when nothing is scheduled', () => {
		expect(clampSMaxAge(60, null, now)).toBe(60);
	});

	it('shortens the window to the next scheduled headline', () => {
		// The CDN has no concept of now(), so without this a headline scheduled 20
		// seconds out would stay invisible for the full 60-second window.
		expect(clampSMaxAge(60, '2026-09-17T12:00:20.000Z', now)).toBe(20);
	});

	it('does not lengthen a window for a distant headline', () => {
		expect(clampSMaxAge(60, '2026-09-18T12:00:00.000Z', now)).toBe(60);
	});

	it('never returns zero, which would disable CDN caching entirely', () => {
		expect(clampSMaxAge(60, '2026-09-17T12:00:00.000Z', now)).toBe(1);
		expect(clampSMaxAge(60, '2026-09-17T11:00:00.000Z', now)).toBe(1);
	});

	it('ignores an unparseable timestamp rather than caching for one second forever', () => {
		expect(clampSMaxAge(60, 'not a date', now)).toBe(60);
	});

	it('handles the Postgres timestamptz spelling', () => {
		expect(clampSMaxAge(60, '2026-09-17 12:00:30+00', now)).toBe(30);
	});
});
