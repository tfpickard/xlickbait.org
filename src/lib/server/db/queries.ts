import { and, count, desc, eq, gt, inArray, lte, not, sql } from 'drizzle-orm';
import { getDb } from './client';
import { headlineImages, headlines, papers, type HeadlineKind } from './schema';
import { decodeCursor, encodeCursor, type Cursor } from './cursor';
import { CHUMBOX_MAX, CHUMBOX_MIN } from '$lib/config';
import { seededRandom, shuffle } from '$lib/rng';

/**
 * Every SELECT the site makes. Nothing here writes, and nothing can: the handle
 * from `getDb()` does not expose insert/update/delete at the type level.
 *
 * All of these use the core query builder with an explicit `innerJoin` rather
 * than the relational query API. Headlines-to-papers is a single join, so the
 * relational layer would buy nothing and cost a second schema-definition surface
 * to keep in sync with the Python generator.
 */

/** The shape every list and detail query returns. */
const headlineColumns = {
	id: headlines.id,
	headline: headlines.headline,
	dek: headlines.dek,
	anchor: headlines.anchor,
	actualPoint: headlines.actualPoint,
	kind: headlines.kind,
	publishAt: headlines.publishAt,
	arxivId: papers.arxivId,
	title: papers.title,
	primaryCategory: papers.primaryCategory,
	categories: papers.categories,
	absUrl: papers.absUrl,
	/**
	 * Whether this headline has an illustration -- NOT the illustration.
	 *
	 * A text column from the left join rather than a computed boolean, on the
	 * same principle as the `to_char` in `listArchiveDays`: `sql<boolean>` is a
	 * type assertion with no runtime validation, and what a driver makes of a
	 * Postgres boolean is the driver's business. A nullable text column is
	 * unambiguous in every driver, and `toCard` turns it into the flag.
	 *
	 * The bytes themselves are never selected here. They live in their own table
	 * precisely so a hundred kilobytes per row cannot end up on the front page by
	 * accident; `getHeadlineImage` is the only thing that reads them.
	 */
	imageMime: headlineImages.mime,
	imageWidth: headlineImages.width,
	imageHeight: headlineImages.height
} as const;

/**
 * Every query selecting `headlineColumns` must also carry this join.
 *
 * `leftJoin`, never `innerJoin`: an illustration is optional by design, so
 * joining it the other way would silently drop every headline that does not have
 * one yet -- which, on the day this ships, is all of them. It is a probe against
 * the image table's primary key, so it costs one index lookup per row and reads
 * no bytes: `mime` is a short text column, and the blob beside it is never
 * touched.
 */
const IMAGE_JOIN_ON = eq(headlineImages.headlineId, headlines.id);

export interface HeadlineCard {
	id: number;
	headline: string;
	dek: string;
	anchor: string;
	actualPoint: string;
	kind: HeadlineKind;
	publishAt: string;
	arxivId: string;
	title: string;
	primaryCategory: string;
	categories: string[];
	absUrl: string;
	/**
	 * `null` means no illustration -- render the SVG fallback.
	 *
	 * The dimensions travel with it because the thumbnail box is sized from them.
	 * A tabloid illustration carries the headline typeset across its top, and
	 * `object-fit: cover` into a box of the wrong shape crops exactly that off.
	 * Every generated image is the same ratio in practice, but reading it from the
	 * row rather than assuming it means `XLICKBAIT_IMAGE_ASPECT` can be changed
	 * without the CSS quietly starting to lie.
	 */
	image: { width: number; height: number } | null;
}

type HeadlineRow = {
	imageMime: string | null;
	imageWidth: number | null;
	imageHeight: number | null;
} & Omit<HeadlineCard, 'image'>;

/**
 * The one place a row becomes a card.
 *
 * Every query funnels through this so `image` cannot be populated in one code
 * path and undefined in another -- which, in a Svelte component, renders as the
 * SVG fallback silently rather than as an error.
 *
 * `Number()` on the dimensions for the same reason `listArchiveDays` casts its
 * day key in SQL: what a driver makes of an integer column is the driver's
 * business, and these two go straight into a CSS `aspect-ratio`.
 */
function toCard(row: HeadlineRow): HeadlineCard {
	const { imageMime, imageWidth, imageHeight, ...rest } = row;
	const image =
		imageMime !== null && imageWidth !== null && imageHeight !== null
			? { width: Number(imageWidth), height: Number(imageHeight) }
			: null;
	return { ...rest, image };
}

/**
 * The visibility rule, in one place.
 *
 * `publish_at <= now()` is what lets the generator schedule headlines to trickle
 * out through the day. It is evaluated by Postgres per request, so a future-dated
 * row becomes visible on its own without a deploy -- within one CDN cache window
 * of its timestamp.
 */
function isLive() {
	return and(eq(headlines.status, 'published'), lte(headlines.publishAt, sql`now()`));
}

export interface ListOptions {
	kind?: HeadlineKind;
	limit: number;
	cursor?: Cursor | null;
	category?: string;
	day?: { start: Date; end: Date };
}

export interface ListResult {
	items: HeadlineCard[];
	nextCursor: string | null;
}

export async function listHeadlines(options: ListOptions): Promise<ListResult> {
	const { kind, limit, cursor, category, day } = options;

	const filters = [isLive()];
	if (kind) filters.push(eq(headlines.kind, kind));
	if (category) {
		// Array containment, backed by the GIN index on papers.categories, so a
		// cross-listed paper appears under every category it was filed in.
		filters.push(sql`${papers.categories} @> ARRAY[${category}]::text[]`);
	}
	if (day) {
		// Half-open range against the bare column. Wrapping publish_at in
		// date_trunc here would be more obvious but non-sargable, and would throw
		// away the index this query depends on.
		filters.push(
			and(
				sql`${headlines.publishAt} >= ${day.start.toISOString()}::timestamptz`,
				sql`${headlines.publishAt} < ${day.end.toISOString()}::timestamptz`
			)!
		);
	}
	if (cursor) {
		// Row-value comparison. Matches the index ordering exactly, so this stays a
		// single index scan rather than a filter over a larger result.
		filters.push(
			sql`(${headlines.publishAt}, ${headlines.id}) < (${cursor.publishAt}::timestamptz, ${cursor.id}::bigint)`
		);
	}

	// One extra row is the has-more probe: cheaper and more reliable than a
	// separate COUNT, which could disagree with the page under concurrent writes.
	const rows = await getDb()
		.select(headlineColumns)
		.from(headlines)
		.innerJoin(papers, eq(headlines.arxivId, papers.arxivId))
		.leftJoin(headlineImages, IMAGE_JOIN_ON)
		.where(and(...filters))
		.orderBy(desc(headlines.publishAt), desc(headlines.id))
		.limit(limit + 1);

	const hasMore = rows.length > limit;
	const items = (hasMore ? rows.slice(0, limit) : rows).map(toCard);
	const last = items.at(-1);

	return {
		items,
		nextCursor: hasMore && last ? encodeCursor({ publishAt: last.publishAt, id: last.id }) : null
	};
}

/** Convenience wrapper for routes that take `?cursor=` from a query string. */
export function parseCursorParam(value: string | null): Cursor | null | 'invalid' {
	if (!value) return null;
	const decoded = decodeCursor(value);
	return decoded ?? 'invalid';
}

export async function getHeadline(id: number): Promise<HeadlineCard | null> {
	const rows = await getDb()
		.select(headlineColumns)
		.from(headlines)
		.innerJoin(papers, eq(headlines.arxivId, papers.arxivId))
		.leftJoin(headlineImages, IMAGE_JOIN_ON)
		.where(and(isLive(), eq(headlines.id, id)))
		.limit(1);
	const row = rows[0];
	return row ? toCard(row) : null;
}

export interface ArchiveDay {
	day: string;
	count: number;
}

export async function listArchiveDays(): Promise<ArchiveDay[]> {
	// date_trunc is fine here -- the archive index is an aggregate over the whole
	// published set, so there is no index scan to preserve. Cast to text in SQL
	// rather than trusting the driver: `sql<T>` is a type assertion with no
	// runtime validation, and the neon-http driver hands back timestamps as
	// strings in a format we would then have to re-parse.
	const day = sql<string>`to_char(date_trunc('day', ${headlines.publishAt} AT TIME ZONE 'UTC'), 'YYYY-MM-DD')`;
	const rows = await getDb()
		.select({ day, count: count() })
		.from(headlines)
		.where(isLive())
		.groupBy(day)
		.orderBy(desc(day));
	return rows.map((r) => ({ day: r.day, count: Number(r.count) }));
}

/**
 * "Around the Preprint Web".
 *
 * Deliberately not `ORDER BY random()`. These pages sit behind a CDN, so a
 * per-request random draw would be frozen for the whole cache window anyway --
 * paying a full scan and nondeterministic tests for an effect almost nobody sees.
 * Instead a bounded recent pool is shuffled with a PRNG seeded from the route and
 * a coarse time bucket: stable within a cache window, different in the next one,
 * and exactly reproducible in a test.
 */
export async function getChumbox(
	excludeIds: readonly number[],
	seed: string
): Promise<HeadlineCard[]> {
	const POOL = 120;
	const filters = [isLive()];
	if (excludeIds.length > 0) filters.push(not(inArray(headlines.id, [...excludeIds])));

	const pool = (
		await getDb()
			.select(headlineColumns)
			.from(headlines)
			.innerJoin(papers, eq(headlines.arxivId, papers.arxivId))
			.leftJoin(headlineImages, IMAGE_JOIN_ON)
			.where(and(...filters))
			.orderBy(desc(headlines.publishAt), desc(headlines.id))
			.limit(POOL)
	).map(toCard);

	const random = seededRandom(seed);
	const span = CHUMBOX_MAX - CHUMBOX_MIN + 1;
	const wanted = CHUMBOX_MIN + Math.floor(random() * span);
	return shuffle(pool, random).slice(0, wanted);
}

/**
 * When the next scheduled headline becomes visible, or null if none is pending.
 *
 * Served by the same `(status, publish_at desc, id desc)` index as every list
 * query, so it is a cheap index probe rather than a scan.
 */
export async function nextScheduledAt(): Promise<string | null> {
	const rows = await getDb()
		.select({ publishAt: headlines.publishAt })
		.from(headlines)
		.where(and(eq(headlines.status, 'published'), gt(headlines.publishAt, sql`now()`)))
		.orderBy(headlines.publishAt)
		.limit(1);
	return rows[0]?.publishAt ?? null;
}

export async function listFeedEntries(limit: number): Promise<HeadlineCard[]> {
	const { items } = await listHeadlines({ limit });
	return items;
}

/** Distinct primary categories that currently have at least one live headline. */
export async function listCategories(): Promise<{ category: string; count: number }[]> {
	const rows = await getDb()
		.select({ category: papers.primaryCategory, count: count() })
		.from(headlines)
		.innerJoin(papers, eq(headlines.arxivId, papers.arxivId))
		.where(isLive())
		.groupBy(papers.primaryCategory)
		.orderBy(desc(count()));
	return rows.map((r) => ({ category: r.category, count: Number(r.count) }));
}

export interface StoredImage {
	/** The bytes, base64 encoded by Postgres. */
	base64: string;
	mime: string;
	/** `length(bytes)` as stored by the generator, for the integrity check. */
	byteSize: number;
}

/**
 * The bytes behind `/i/<id>`, for a headline that is currently visible.
 *
 * `isLive()` is applied here rather than left to the route, so a hidden headline
 * takes its picture down with it. The kill switch is the whole reason: hiding a
 * headline whose illustration kept serving from a guessable URL would be a
 * takedown that only covered the words.
 *
 * Base64 rather than the raw `bytea`, asked for in SQL. What a driver returns
 * for a binary column is a driver decision -- neon-http renders Postgres's
 * `\x<hex>` escape, which is twice the bytes over the wire and one more format
 * to parse correctly while serving an image. `encode()` makes the wire format
 * this code's decision instead, and `Buffer.from(..., 'base64')` is the
 * single, well-specified step back.
 */
export async function getHeadlineImage(id: number): Promise<StoredImage | null> {
	const rows = await getDb()
		.select({
			base64: sql<string>`encode(${headlineImages.bytes}, 'base64')`,
			mime: headlineImages.mime,
			byteSize: headlineImages.byteSize
		})
		.from(headlineImages)
		.innerJoin(headlines, IMAGE_JOIN_ON)
		.where(and(isLive(), eq(headlineImages.headlineId, id)))
		.limit(1);

	const row = rows[0];
	if (!row) return null;
	return { base64: row.base64, mime: row.mime, byteSize: Number(row.byteSize) };
}
