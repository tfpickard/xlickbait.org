import { describe, expect, it } from 'vitest';
import { decodeCursor, encodeCursor } from '$lib/server/db/cursor';

describe('cursors', () => {
	it('round-trips', () => {
		const cursor = { publishAt: '2026-09-17 02:03:50.076495+00', id: 1234 };
		expect(decodeCursor(encodeCursor(cursor))).toEqual(cursor);
	});

	it('preserves microsecond precision exactly', () => {
		// Carrying the timestamp as epoch milliseconds would round these two to the
		// same value and reintroduce the ambiguity the id tiebreaker exists to
		// remove. The exact string Postgres returned goes in and comes back out.
		const a = { publishAt: '2026-09-17 02:03:50.076495+00', id: 1 };
		const b = { publishAt: '2026-09-17 02:03:50.076496+00', id: 1 };
		expect(encodeCursor(a)).not.toBe(encodeCursor(b));
		expect(decodeCursor(encodeCursor(a))?.publishAt).toBe(a.publishAt);
		expect(decodeCursor(encodeCursor(b))?.publishAt).toBe(b.publishAt);
	});

	it('is URL-safe', () => {
		const encoded = encodeCursor({ publishAt: '2026-09-17T02:03:50.000Z', id: 99 });
		expect(encoded).toMatch(/^[A-Za-z0-9_-]+$/);
		expect(encodeURIComponent(encoded)).toBe(encoded);
	});

	it('returns null for absent cursors', () => {
		expect(decodeCursor(null)).toBeNull();
		expect(decodeCursor(undefined)).toBeNull();
		expect(decodeCursor('')).toBeNull();
	});

	it('rejects malformed cursors instead of guessing', () => {
		const bad = [
			'not-base64!!',
			Buffer.from('no-separator').toString('base64url'),
			Buffer.from('2026-09-17|abc').toString('base64url'),
			Buffer.from('2026-09-17|-5').toString('base64url'),
			Buffer.from('2026-09-17|0').toString('base64url'),
			Buffer.from('not-a-date|5').toString('base64url'),
			Buffer.from('|5').toString('base64url'),
			Buffer.from('2026-09-17|1.5').toString('base64url')
		];
		for (const value of bad) {
			expect(decodeCursor(value), `expected null for ${value}`).toBeNull();
		}
	});

	it('rejects ids past the safe integer range', () => {
		const encoded = Buffer.from('2026-09-17T00:00:00Z|99999999999999999999').toString('base64url');
		expect(decodeCursor(encoded)).toBeNull();
	});
});
