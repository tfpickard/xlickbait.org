import { sql } from 'drizzle-orm';
import {
	bigint,
	customType,
	index,
	integer,
	pgEnum,
	pgTable,
	text,
	timestamp,
	uniqueIndex
} from 'drizzle-orm/pg-core';

/**
 * This file is the source of truth for the database, and the seam between two
 * codebases in two languages: the SvelteKit site reads through it, and the
 * Python generator writes rows that must match the SQL it generates.
 *
 * Because of that, the generated migrations in `drizzle/migrations/` are a
 * contract. Never edit one after it is committed, and prefer additive changes so
 * a migration can land before the code that depends on it.
 *
 * Timestamps use `mode: 'string'`. Postgres hands back an ISO-8601 string with
 * an offset either way; asking Drizzle to reconstitute a `Date` just adds a
 * lossy round-trip between the Python writer and the TypeScript reader, and
 * SvelteKit would re-serialise it across the load boundary anyway. Parsing is
 * explicit, at the one place that needs it.
 */

/**
 * `bytea`, which drizzle-orm has no first-class column for.
 *
 * The site never selects this column through Drizzle: `queries.ts` asks Postgres
 * for `encode(bytes, 'base64')` instead, for the same reason `listArchiveDays`
 * casts its day key to text in SQL. What a driver hands back for a binary column
 * is a driver decision -- neon-http renders it as Postgres's `\x<hex>` escape,
 * which is twice the bytes of base64 and one more format to parse correctly at
 * the exact moment an image is being served.
 *
 * So this type exists to make drizzle-kit emit `bytea` in the migration, and
 * `fromDriver` is the honest decoder for that escape format rather than a
 * `throw`, in case someone does reach for it later.
 */
const bytea = customType<{ data: Uint8Array; driverData: string }>({
	dataType() {
		return 'bytea';
	},
	fromDriver(value) {
		if (!value.startsWith('\\x')) throw new Error('expected a \\x-prefixed bytea escape');
		const hex = value.slice(2);
		const out = new Uint8Array(hex.length / 2);
		for (let i = 0; i < out.length; i++) out[i] = parseInt(hex.substr(i * 2, 2), 16);
		return out;
	}
});

export const headlineKind = pgEnum('headline_kind', ['fresh', 'vintage']);
export const headlineStatus = pgEnum('headline_status', ['published', 'hidden']);

export const papers = pgTable(
	'papers',
	{
		arxivId: text('arxiv_id').primaryKey(),
		title: text('title').notNull(),
		abstract: text('abstract').notNull(),
		authors: text('authors').array().notNull(),
		primaryCategory: text('primary_category').notNull(),
		categories: text('categories').array().notNull(),
		publishedAt: timestamp('published_at', { withTimezone: true, mode: 'string' }).notNull(),
		absUrl: text('abs_url').notNull()
	},
	(t) => [
		index('papers_primary_category_idx').on(t.primaryCategory),
		// `/c/[category]` matches against the full category array so cross-listed
		// papers show up under every category they were filed in, not just the
		// primary one. That is an array containment query, which needs GIN.
		index('papers_categories_gin_idx').using('gin', t.categories)
	]
);

export const headlines = pgTable(
	'headlines',
	{
		id: bigint('id', { mode: 'number' }).generatedAlwaysAsIdentity().primaryKey(),
		arxivId: text('arxiv_id')
			.notNull()
			.references(() => papers.arxivId, { onDelete: 'cascade' }),
		headline: text('headline').notNull(),
		dek: text('dek').notNull(),
		anchor: text('anchor').notNull(),
		actualPoint: text('actual_point').notNull(),
		kind: headlineKind('kind').notNull(),
		model: text('model').notNull(),
		status: headlineStatus('status').notNull().default('published'),
		createdAt: timestamp('created_at', { withTimezone: true, mode: 'string' })
			.notNull()
			.defaultNow(),
		publishAt: timestamp('publish_at', { withTimezone: true, mode: 'string' })
			.notNull()
			.defaultNow()
	},
	(t) => [
		// At most one published headline per paper. The predicate is written as a
		// raw `sql` template with a literal rather than `eq(t.status, 'published')`
		// because drizzle-kit renders an index predicate by serialising the SQL
		// node: an `eq()` becomes a bound parameter and emits `WHERE "status" = $1`,
		// which is not valid DDL and fails at migrate time rather than generate
		// time. `bin/migrate.sh` greps for that pattern as a backstop.
		uniqueIndex('headlines_one_published_per_paper')
			.on(t.arxivId)
			.where(sql`${t.status} = 'published'`),
		// Serves the front page, day pages and feed: the filter columns first, then
		// the cursor ordering INCLUDING its tiebreaker, in the same direction as the
		// ORDER BY so the scan stays a single index read.
		index('headlines_status_publish_at_id_idx').on(t.status, t.publishAt.desc(), t.id.desc()),
		index('headlines_kind_status_publish_at_idx').on(t.kind, t.status, t.publishAt.desc())
	]
);

/**
 * One generated illustration per headline, written by the generator and served
 * by `/i/<id>`.
 *
 * Its own table rather than columns on `headlines` for two reasons. The bytes
 * are large enough that Postgres TOASTs them, and every list query on the site
 * selects a fixed column set from `headlines` -- keeping the blob in a separate
 * relation makes it impossible to drag a hundred kilobytes per row through the
 * front page by adding a column to `headlineColumns` without noticing.
 *
 * It is also optional by design. A headline with no row here falls back to the
 * deterministic SVG in `src/lib/thumb.ts`, so an image model being down, slow or
 * out of credit costs the site nothing: the run still publishes.
 */
export const headlineImages = pgTable('headline_images', {
	// Not `generatedAlwaysAsIdentity`: the headline id IS the identity here, one
	// image per headline, and the cascade means a deleted headline cannot leave
	// an orphaned blob behind.
	headlineId: bigint('headline_id', { mode: 'number' })
		.primaryKey()
		.references(() => headlines.id, { onDelete: 'cascade' }),
	/** Always `image/webp` today; stored rather than assumed, since it is what the route sends as Content-Type. */
	mime: text('mime').notNull(),
	width: integer('width').notNull(),
	height: integer('height').notNull(),
	/** Denormalised `length(bytes)`, so a size audit does not have to detoast every row. */
	byteSize: integer('byte_size').notNull(),
	bytes: bytea('bytes').notNull(),
	/** OpenRouter model slug, e.g. `openai/gpt-image-1-mini`. */
	model: text('model').notNull(),
	/** The prompt that produced it. Kept so a bad image can be diagnosed without re-deriving it. */
	prompt: text('prompt').notNull(),
	createdAt: timestamp('created_at', { withTimezone: true, mode: 'string' }).notNull().defaultNow()
});

/**
 * Written only by the Python generator (Phase 2). The site never reads this
 * table; it exists so a failed or partial run leaves a trace worth waking up to.
 */
export const generatorRuns = pgTable('generator_runs', {
	id: bigint('id', { mode: 'number' }).generatedAlwaysAsIdentity().primaryKey(),
	startedAt: timestamp('started_at', { withTimezone: true, mode: 'string' }).notNull().defaultNow(),
	finishedAt: timestamp('finished_at', { withTimezone: true, mode: 'string' }),
	freshCount: integer('fresh_count').notNull().default(0),
	vintageCount: integer('vintage_count').notNull().default(0),
	rejectedCount: integer('rejected_count').notNull().default(0),
	error: text('error')
});

export type Paper = typeof papers.$inferSelect;
export type Headline = typeof headlines.$inferSelect;
export type HeadlineImage = typeof headlineImages.$inferSelect;
export type HeadlineKind = (typeof headlineKind.enumValues)[number];
export type HeadlineStatus = (typeof headlineStatus.enumValues)[number];
