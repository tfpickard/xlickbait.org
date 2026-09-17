import { beforeAll, describe, expect, it } from 'vitest';
import {
	getChumbox,
	getHeadline,
	listArchiveDays,
	listHeadlines,
	nextScheduledAt,
	type HeadlineCard
} from '$lib/server/db/queries';
import { decodeCursor } from '$lib/server/db/cursor';
import { CHUMBOX_MAX, CHUMBOX_MIN } from '$lib/config';
import { utcDayKey, utcDayRange } from '$lib/time';

/**
 * Integration tests against the seeded Neon `dev` branch.
 *
 * These run the real driver against real Postgres, because the behaviour under
 * test -- row-value cursor comparison, `publish_at <= now()`, array containment --
 * lives in the database, not in TypeScript. A mock would only assert that I can
 * restate my own assumptions.
 *
 * They skip rather than fail without a DATABASE_URL, so a fresh checkout still
 * gets a green unit suite.
 */
const hasDb = Boolean(process.env.DATABASE_URL);
const describeDb = hasDb ? describe : describe.skip;

describeDb('queries against the seeded dev branch', () => {
	let all: HeadlineCard[];

	beforeAll(async () => {
		// Large limit: everything live, in canonical order, as the baseline.
		all = (await listHeadlines({ limit: 500 })).items;
	});

	it('has a corpus big enough for these tests to mean anything', () => {
		expect(all.length).toBeGreaterThan(20);
	});

	describe('visibility', () => {
		it('never returns a hidden headline', async () => {
			// The fixture headline about a 60-page appendix is status = hidden.
			expect(all.some((h) => h.headline.includes('60-PAGE APPENDIX'))).toBe(false);
		});

		it('never returns a future-dated headline', () => {
			const now = Date.now();
			for (const item of all) {
				expect(
					Date.parse(item.publishAt),
					`${item.headline} is scheduled for the future but was returned`
				).toBeLessThanOrEqual(now);
			}
		});

		it('is not vacuous: the seed still holds something scheduled', async () => {
			// This used to name two fixtures ("BY MULE", "11 NIGHTS") and assert they
			// were absent. Fixtures are dated relative to SEED time -- `at(+1 * HOUR)`
			// -- so an hour after seeding the mule headline published on schedule and
			// the assertion failed, having proved nothing about the query.
			//
			// The invariant above is the real test. This one exists so that it cannot
			// pass simply because nothing is scheduled any more, and it asks the
			// database rather than trusting a name to stay in the future.
			const next = await nextScheduledAt();
			expect(
				next,
				'no fixture is scheduled ahead of now, so the visibility test proves nothing. Re-seed: npm run db:reset-dev'
			).not.toBeNull();
			expect(Date.parse(next as string)).toBeGreaterThan(Date.now());
			// And whatever that is, it must not be in the live list.
			expect(all.some((h) => h.publishAt === next)).toBe(false);
		});

		it('hides a hidden headline from its permalink too, not just from lists', async () => {
			const everything = await listHeadlines({ limit: 500 });
			const maxId = Math.max(...everything.items.map((i) => i.id));
			// Probe ids around the corpus; any hidden or future row must 404 (null).
			for (let id = 1; id <= maxId; id++) {
				const item = await getHeadline(id);
				if (item === null) continue;
				expect(Date.parse(item.publishAt)).toBeLessThanOrEqual(Date.now());
			}
		});
	});

	describe('ordering', () => {
		it('is strictly descending by (publish_at, id)', () => {
			for (let i = 0; i + 1 < all.length; i++) {
				const a = all[i] as HeadlineCard;
				const b = all[i + 1] as HeadlineCard;
				const at = Date.parse(a.publishAt);
				const bt = Date.parse(b.publishAt);
				expect(at).toBeGreaterThanOrEqual(bt);
				if (at === bt) expect(a.id).toBeGreaterThan(b.id);
			}
		});

		it('actually contains a tied pair, or the tiebreaker test below is vacuous', () => {
			const stamps = all.map((h) => h.publishAt);
			expect(new Set(stamps).size).toBeLessThan(stamps.length);
		});
	});

	describe('cursor pagination', () => {
		it('walks the whole corpus with no duplicates and no gaps', async () => {
			const pageSize = 5;
			const seen: number[] = [];
			let cursor = null as ReturnType<typeof decodeCursor>;
			let guard = 0;

			for (;;) {
				const page = await listHeadlines({ limit: pageSize, cursor });
				seen.push(...page.items.map((i) => i.id));
				if (!page.nextCursor) break;
				cursor = decodeCursor(page.nextCursor);
				expect(cursor).not.toBeNull();
				if (++guard > 200) throw new Error('pagination did not terminate');
			}

			// No duplicates.
			expect(new Set(seen).size).toBe(seen.length);
			// No gaps: paging yields exactly the same set, in the same order, as one
			// unpaginated query.
			expect(seen).toEqual(all.map((i) => i.id));
		});

		it('does not drop or repeat a row across a page boundary that falls on a tie', async () => {
			// Walk with page size 1, which forces a boundary between every pair --
			// including the two fixtures that deliberately share a publish_at. A
			// cursor keyed on publish_at alone loses or repeats one of them here.
			const seen: number[] = [];
			let cursor = null as ReturnType<typeof decodeCursor>;
			let guard = 0;
			for (;;) {
				const page = await listHeadlines({ limit: 1, cursor });
				seen.push(...page.items.map((i) => i.id));
				if (!page.nextCursor) break;
				cursor = decodeCursor(page.nextCursor);
				if (++guard > 500) throw new Error('pagination did not terminate');
			}
			expect(new Set(seen).size).toBe(seen.length);
			expect(seen).toEqual(all.map((i) => i.id));
		});

		it('stops cleanly instead of offering a cursor past the end', async () => {
			const page = await listHeadlines({ limit: 500 });
			expect(page.nextCursor).toBeNull();
		});
	});

	describe('filters', () => {
		it('splits fresh from vintage without losing anything', async () => {
			const fresh = (await listHeadlines({ kind: 'fresh', limit: 500 })).items;
			const vintage = (await listHeadlines({ kind: 'vintage', limit: 500 })).items;
			expect(fresh.every((i) => i.kind === 'fresh')).toBe(true);
			expect(vintage.every((i) => i.kind === 'vintage')).toBe(true);
			expect(fresh.length + vintage.length).toBe(all.length);
		});

		it('matches a category against cross-lists, not just the primary', async () => {
			const target = 'cs.LG';
			const items = (await listHeadlines({ category: target, limit: 500 })).items;
			expect(items.length).toBeGreaterThan(0);
			expect(items.every((i) => i.categories.includes(target))).toBe(true);
			// At least one match must be a cross-list, or the array containment is
			// doing nothing a primary_category equality check would not.
			expect(items.some((i) => i.primaryCategory !== target)).toBe(true);
		});

		it('confines a day page to that UTC day', async () => {
			const sample = all[0] as HeadlineCard;
			const key = utcDayKey(sample.publishAt);
			const [y, m, d] = key.split('-').map(Number) as [number, number, number];
			const items = (await listHeadlines({ limit: 500, day: utcDayRange(y, m, d) })).items;
			expect(items.length).toBeGreaterThan(0);
			for (const item of items) expect(utcDayKey(item.publishAt)).toBe(key);
		});
	});

	describe('archive', () => {
		it('accounts for every live headline exactly once', async () => {
			const days = await listArchiveDays();
			expect(days.reduce((sum, d) => sum + d.count, 0)).toBe(all.length);
		});

		it('is grouped by UTC day and sorted newest first', async () => {
			const days = await listArchiveDays();
			const keys = days.map((d) => d.day);
			expect(keys).toEqual([...keys].sort().reverse());
			expect(new Set(keys).size).toBe(keys.length);
			for (const key of keys) expect(key).toMatch(/^\d{4}-\d{2}-\d{2}$/);
		});
	});

	describe('chumbox', () => {
		it('excludes everything already on the page', async () => {
			const onPage = all.slice(0, 10).map((i) => i.id);
			const items = await getChumbox(onPage, 'seed-a');
			expect(items.length).toBeGreaterThan(0);
			for (const item of items) expect(onPage).not.toContain(item.id);
		});

		it('returns between six and nine items when the corpus allows', async () => {
			const items = await getChumbox([], 'seed-b');
			expect(items.length).toBeGreaterThanOrEqual(CHUMBOX_MIN);
			expect(items.length).toBeLessThanOrEqual(CHUMBOX_MAX);
		});

		it('is deterministic for a given seed, so a cached page is self-consistent', async () => {
			const a = await getChumbox([], 'same-seed');
			const b = await getChumbox([], 'same-seed');
			expect(a.map((i) => i.id)).toEqual(b.map((i) => i.id));
		});

		it('changes with the seed, so it churns between cache windows', async () => {
			const a = await getChumbox([], 'window-1');
			const b = await getChumbox([], 'window-2');
			expect(a.map((i) => i.id)).not.toEqual(b.map((i) => i.id));
		});

		it('returns no duplicates within one draw', async () => {
			const items = await getChumbox([], 'dupes');
			expect(new Set(items.map((i) => i.id)).size).toBe(items.length);
		});

		it('shows only live headlines', async () => {
			const items = await getChumbox([], 'live-only');
			for (const item of items) {
				expect(Date.parse(item.publishAt)).toBeLessThanOrEqual(Date.now());
			}
		});
	});

	describe('permalinks', () => {
		it('returns a live headline by id', async () => {
			const sample = all[0] as HeadlineCard;
			const found = await getHeadline(sample.id);
			expect(found?.id).toBe(sample.id);
			expect(found?.headline).toBe(sample.headline);
		});

		it('returns null for an id that does not exist', async () => {
			expect(await getHeadline(9_999_999)).toBeNull();
		});

		it('joins through to the paper every time', () => {
			for (const item of all) {
				expect(item.arxivId).toMatch(/^\d{4}\.\d{4,5}$/);
				expect(item.absUrl).toBe(`https://arxiv.org/abs/${item.arxivId}`);
				expect(item.title.length).toBeGreaterThan(0);
				expect(Array.isArray(item.categories)).toBe(true);
			}
		});
	});
});
