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
import { connectionStringForScripts, writableDb } from './db';
import { headlines, papers } from '../src/lib/server/db/schema';
import { headlineFixtures, paperFixtures } from './fixtures';

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

const now = Date.now();
const published = headlineFixtures.filter((h) => h.status === 'published');
const future = published.filter((h) => Date.parse(h.publishAt) > now);

console.log(`seeded ${paperFixtures.length} papers and ${headlineFixtures.length} headlines`);
console.log(`  ${published.length - future.length} live now`);
console.log(`  ${future.length} future-dated (must not appear on the site yet)`);
console.log(`  ${headlineFixtures.length - published.length} hidden`);
console.log(`  host: ${new URL(url).hostname}`);
