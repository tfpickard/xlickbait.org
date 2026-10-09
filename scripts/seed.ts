/**
 * Load development fixtures into the Neon `dev` branch.
 *
 * Idempotent: it removes the fixture papers first (headlines cascade) and then
 * reinserts. Scoped to the fixture ids, so it will not touch anything the
 * generator wrote. Re-running without the delete would violate the
 * one-published-headline-per-paper index, which is the constraint working as
 * intended rather than a bug to route around.
 */
import { inArray } from 'drizzle-orm';
import sharp from 'sharp';
import { connectionStringForScripts, writableDb } from './db';
import { headlineImages, headlines, papers } from '../src/lib/server/db/schema';
import { headlineFixtures, paperFixtures } from './fixtures';
import { thumbnailFor } from '../src/lib/thumb';

const url = connectionStringForScripts();
const db = writableDb(url);

const arxivIds = paperFixtures.map((p) => p.arxivId);

await db.delete(papers).where(inArray(papers.arxivId, arxivIds));

await db.insert(papers).values(
	paperFixtures.map((p) => ({
		arxivId: p.arxivId,
		title: p.title,
		abstract: p.abstract,
		authors: p.authors,
		primaryCategory: p.primaryCategory,
		categories: p.categories,
		publishedAt: p.publishedAt,
		absUrl: p.absUrl
	}))
);

await db.insert(headlines).values(
	headlineFixtures.map((h) => ({
		arxivId: h.arxivId,
		headline: h.headline,
		dek: h.dek,
		anchor: h.anchor,
		actualPoint: h.actualPoint,
		kind: h.kind,
		model: h.model,
		status: h.status,
		publishAt: h.publishAt
	}))
);

/**
 * Fixture illustrations, so `/i/<id>` is exercised locally without an
 * OpenRouter key -- or a cent of spend.
 *
 * These are the site's own deterministic SVG thumbnails, rasterised to WebP by
 * the `sharp` that already builds the OG image. They look nothing like what the
 * generator produces, and that is fine: what needs exercising here is the
 * bytea round trip, the Content-Type, the byte-length check and the `hasImage`
 * branch in `Thumb.svelte`, none of which care what the picture is of.
 *
 * Deliberately only SOME of them. Both branches -- served image and SVG
 * fallback -- have to be visible on the front page at once, because the failure
 * mode worth catching by eye is one of them silently never rendering.
 */
const withImages = headlineFixtures
	.map((h, index) => ({ h, index }))
	.filter(({ h, index }) => h.status === 'published' && index % 2 === 0);

const rows = await db
	.select({ id: headlines.id, arxivId: headlines.arxivId, headline: headlines.headline })
	.from(headlines)
	.where(
		inArray(
			headlines.arxivId,
			withImages.map(({ h }) => h.arxivId)
		)
	);

// Match on (arxivId, headline): a paper can carry a hidden headline as well as a
// published one, and `arxivId` alone would pick whichever came back first.
const wanted = new Set(withImages.map(({ h }) => `${h.arxivId}\u0000${h.headline}`));
const targets = rows.filter((r) => wanted.has(`${r.arxivId}\u0000${r.headline}`));

for (const row of targets) {
	const webp = await sharp(Buffer.from(thumbnailFor(row.arxivId).svg))
		.resize(1200, 800, { fit: 'cover' })
		.webp({ quality: 80 })
		.toBuffer();
	await db
		.insert(headlineImages)
		.values({
			headlineId: row.id,
			mime: 'image/webp',
			width: 1200,
			height: 800,
			byteSize: webp.byteLength,
			bytes: webp,
			model: 'fixture',
			prompt: 'seeded fixture: the deterministic SVG thumbnail, rasterised'
		})
		.onConflictDoNothing();
}

const now = Date.now();
const published = headlineFixtures.filter((h) => h.status === 'published');
const future = published.filter((h) => Date.parse(h.publishAt) > now);

console.log(`seeded ${paperFixtures.length} papers and ${headlineFixtures.length} headlines`);
console.log(`  ${published.length - future.length} live now`);
console.log(`  ${future.length} future-dated (must not appear on the site yet)`);
console.log(`  ${headlineFixtures.length - published.length} hidden`);
console.log(`  ${targets.length} with a fixture illustration at /i/<id>`);
console.log(`  host: ${new URL(url).hostname}`);
