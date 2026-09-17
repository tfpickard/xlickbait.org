import { describe, expect, it } from 'vitest';
import { formatDayLong, isValidUtcDate, relativeTime, utcDayKey, utcDayRange } from '$lib/time';

describe('utcDayKey', () => {
	it('uses UTC, not the host timezone', () => {
		// 23:30 UTC is already "tomorrow" in Sydney and still "today" in New York.
		// The site has one answer, and it is the UTC one.
		expect(utcDayKey('2026-09-17T23:30:00.000Z')).toBe('2026-09-17');
		expect(utcDayKey('2026-09-17T00:00:00.000Z')).toBe('2026-09-17');
		expect(utcDayKey('2026-09-17T23:59:59.999Z')).toBe('2026-09-17');
	});

	it('handles the Postgres timestamptz spelling', () => {
		expect(utcDayKey('2026-09-17 02:03:50.076495+00')).toBe('2026-09-17');
	});

	it('throws on nonsense rather than returning a wrong day', () => {
		expect(() => utcDayKey('not a date')).toThrow(RangeError);
	});
});

describe('utcDayRange', () => {
	it('is half-open, so a day and the next never overlap', () => {
		const day = utcDayRange(2026, 9, 17);
		const next = utcDayRange(2026, 9, 18);
		expect(day.start.toISOString()).toBe('2026-09-17T00:00:00.000Z');
		expect(day.end.toISOString()).toBe('2026-09-18T00:00:00.000Z');
		expect(day.end.getTime()).toBe(next.start.getTime());
	});

	it('spans exactly 24 hours, with no DST shortening', () => {
		// A local-timezone implementation would make two days a year 23 or 25 hours
		// long, and the pagination over those days would quietly misbehave.
		for (const [y, m, d] of [
			[2026, 3, 29],
			[2026, 10, 25],
			[2026, 2, 28]
		] as const) {
			const range = utcDayRange(y, m, d);
			expect(range.end.getTime() - range.start.getTime()).toBe(86_400_000);
		}
	});

	it('rolls over month and year boundaries', () => {
		expect(utcDayRange(2026, 12, 31).end.toISOString()).toBe('2027-01-01T00:00:00.000Z');
	});
});

describe('isValidUtcDate', () => {
	it('accepts real dates', () => {
		expect(isValidUtcDate(2026, 9, 17)).toBe(true);
		expect(isValidUtcDate(2024, 2, 29)).toBe(true);
	});

	it('rejects dates that pass a shape check but do not exist', () => {
		// The route matchers allow 01-31 for any month, so this is the only thing
		// standing between /2026/02/31 and a silently wrong page.
		expect(isValidUtcDate(2026, 2, 31)).toBe(false);
		expect(isValidUtcDate(2026, 2, 29)).toBe(false);
		expect(isValidUtcDate(2026, 4, 31)).toBe(false);
		expect(isValidUtcDate(2026, 13, 1)).toBe(false);
		expect(isValidUtcDate(2026, 0, 1)).toBe(false);
	});
});

describe('relativeTime', () => {
	const now = new Date('2026-09-17T12:00:00.000Z');

	it('describes recent times', () => {
		expect(relativeTime('2026-09-17T11:59:30.000Z', now)).toBe('just now');
		expect(relativeTime('2026-09-17T11:59:00.000Z', now)).toBe('1 minute ago');
		expect(relativeTime('2026-09-17T11:30:00.000Z', now)).toBe('30 minutes ago');
		expect(relativeTime('2026-09-17T11:00:00.000Z', now)).toBe('1 hour ago');
		expect(relativeTime('2026-09-16T12:00:00.000Z', now)).toBe('1 day ago');
	});

	it('never says something in the future is old', () => {
		// Scheduled headlines exist, and a clock skew of a second must not render
		// "in -1 minutes".
		expect(relativeTime('2026-09-17T13:00:00.000Z', now)).toBe('just now');
	});
});

describe('formatDayLong', () => {
	it('renders in UTC regardless of host timezone', () => {
		expect(formatDayLong('2026-09-17')).toBe('17 September 2026');
		expect(formatDayLong('2026-01-01')).toBe('1 January 2026');
	});
});
