/**
 * Opaque pagination cursors.
 *
 * The cursor is the row value `(publish_at, id)`, not `publish_at` alone. The
 * generator inserts several headlines in one transaction, so identical
 * `publish_at` values are normal rather than exotic -- and with a non-unique sort
 * key, rows on a page boundary get duplicated or skipped depending on which way
 * the tie falls. The id breaks the tie and makes the ordering total.
 *
 * The timestamp is carried as the exact string Postgres returned, not as epoch
 * milliseconds. `timestamptz` has microsecond resolution; rounding to
 * milliseconds would reintroduce the exact ambiguity the tiebreaker exists to
 * remove.
 */

const SEPARATOR = '|';

export interface Cursor {
	publishAt: string;
	id: number;
}

export function encodeCursor(cursor: Cursor): string {
	const raw = `${cursor.publishAt}${SEPARATOR}${cursor.id}`;
	return Buffer.from(raw, 'utf8').toString('base64url');
}

/**
 * Parse a cursor from a query string. Returns null for anything malformed; the
 * caller turns that into a 400 rather than silently serving page one, because
 * quietly ignoring a broken cursor is how a paginating client ends up in an
 * infinite loop.
 */
export function decodeCursor(encoded: string | null | undefined): Cursor | null {
	if (!encoded) return null;
	let raw: string;
	try {
		raw = Buffer.from(encoded, 'base64url').toString('utf8');
	} catch {
		return null;
	}

	// Split on the LAST separator: the id can never contain one, but we do not
	// want to depend on that being true of the timestamp format forever.
	const index = raw.lastIndexOf(SEPARATOR);
	if (index <= 0) return null;
	const publishAt = raw.slice(0, index);
	const idPart = raw.slice(index + 1);

	const id = Number(idPart);
	if (!/^[0-9]+$/.test(idPart) || !Number.isSafeInteger(id) || id <= 0) return null;
	if (Number.isNaN(new Date(publishAt).getTime())) return null;

	return { publishAt, id };
}
