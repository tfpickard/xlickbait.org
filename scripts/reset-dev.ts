/**
 * Wipe the dev branch and reload fixtures.
 *
 * Carries the same production guard as the seed script -- this one truncates
 * every table, so it is the script that most needs to be impossible to point at
 * production.
 */
import { sql } from 'drizzle-orm';
import { connectionStringForScripts, writableDb } from './db';

const url = connectionStringForScripts();
const db = writableDb(url);

// RESTART IDENTITY so headline ids start from 1 again and permalinks in a
// developer's browser history keep meaning the same thing between resets.
await db.execute(sql`TRUNCATE TABLE headlines, papers, generator_runs RESTART IDENTITY CASCADE`);
console.log(`truncated all tables on ${new URL(url).hostname}`);

await import('./seed');
