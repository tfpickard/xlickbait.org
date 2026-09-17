/**
 * Time handling. Every "day" on this site is a UTC day -- the day pages, the
 * archive grouping and the displayed date all agree, with no DST-shortened days
 * and no dependence on the server's locale.
 */

const MINUTE = 60;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

/** `YYYY-MM-DD` for the UTC day containing an ISO timestamp. */
export function utcDayKey(timestamp: string): string {
	const d = new Date(timestamp);
	if (Number.isNaN(d.getTime())) throw new RangeError(`invalid timestamp: ${timestamp}`);
	return d.toISOString().slice(0, 10);
}

/**
 * Half-open UTC day bounds, `[start, end)`.
 *
 * Returned as timestamps to compare a column against directly, rather than
 * wrapping the column in `date_trunc`. Wrapping the column would make the
 * predicate non-sargable and throw away the `(status, publish_at desc, id desc)`
 * index that every list query depends on.
 */
export function utcDayRange(year: number, month: number, day: number): { start: Date; end: Date } {
	const start = new Date(Date.UTC(year, month - 1, day));
	const end = new Date(start.getTime() + DAY * 1000);
	return { start, end };
}

/** True if y-m-d is a real calendar date (rejects 2026-02-31 and friends). */
export function isValidUtcDate(year: number, month: number, day: number): boolean {
	if (month < 1 || month > 12 || day < 1 || day > 31) return false;
	const d = new Date(Date.UTC(year, month - 1, day));
	return d.getUTCFullYear() === year && d.getUTCMonth() === month - 1 && d.getUTCDate() === day;
}

/** `2026-09-17` -> the params for the day route. */
export function splitDayKey(dayKey: string): { yyyy: string; mm: string; dd: string } {
	const [yyyy, mm, dd] = dayKey.split('-') as [string, string, string];
	return { yyyy, mm, dd };
}

/** `2026-09-17` -> `17 September 2026`. */
export function formatDayLong(dayKey: string): string {
	const [y, m, d] = dayKey.split('-').map(Number);
	const date = new Date(Date.UTC(y as number, (m as number) - 1, d as number));
	return date.toLocaleDateString('en-GB', {
		day: 'numeric',
		month: 'long',
		year: 'numeric',
		timeZone: 'UTC'
	});
}

/**
 * Coarse relative time, tabloid-urgent at the short end.
 *
 * `now` is injected rather than read from the clock so this is testable and so a
 * rendered page is a pure function of its inputs.
 */
export function relativeTime(timestamp: string, now: Date): string {
	const then = new Date(timestamp);
	const seconds = Math.floor((now.getTime() - then.getTime()) / 1000);

	if (seconds < 0) return 'just now';
	if (seconds < MINUTE) return 'just now';
	if (seconds < HOUR) {
		const m = Math.floor(seconds / MINUTE);
		return `${m} minute${m === 1 ? '' : 's'} ago`;
	}
	if (seconds < DAY) {
		const h = Math.floor(seconds / HOUR);
		return `${h} hour${h === 1 ? '' : 's'} ago`;
	}
	const days = Math.floor(seconds / DAY);
	if (days < 30) return `${days} day${days === 1 ? '' : 's'} ago`;
	const months = Math.floor(days / 30);
	if (months < 12) return `${months} month${months === 1 ? '' : 's'} ago`;
	const years = Math.floor(days / 365);
	return `${years} year${years === 1 ? '' : 's'} ago`;
}
