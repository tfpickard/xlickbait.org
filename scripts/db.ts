/**
 * A WRITABLE database handle, for scripts only.
 *
 * The web app deliberately cannot write -- `src/lib/server/db/client.ts` exports
 * a handle narrowed to the select side. Seeding and migrating genuinely need
 * insert and delete, and they run from a developer's machine rather than from
 * Netlify, so they get their own client here in `scripts/` where the
 * no-writes-in-web-code rules do not apply.
 */
import { neon, neonConfig } from '@neondatabase/serverless';
import { drizzle } from 'drizzle-orm/neon-http';
import { ProductionGuardError, assertNotProduction } from '../src/lib/server/db/guard';

export function connectionStringForScripts(): string {
	const url = process.env.DATABASE_URL;
	if (!url) {
		console.error('DATABASE_URL is not set. Copy .env.example to .env and fill it in.');
		process.exit(1);
	}
	return url;
}

/**
 * Build a writable client, refusing to proceed if it points at production.
 * The guard runs before the client is constructed, so a refusal cannot race a
 * connection that was already opened.
 */
export function writableDb(url: string) {
	// Present a refusal as a refusal, not as a stack trace. An operator who has
	// just been stopped from wiping a database should see why in one line.
	try {
		assertNotProduction(url, process.env);
	} catch (error) {
		if (error instanceof ProductionGuardError) {
			console.error(`\n  REFUSED\n\n  ${error.message.split('\n').join('\n  ')}\n`);
			process.exit(1);
		}
		throw error;
	}
	const host = new URL(url).hostname;
	if (host === 'localhost' || host === '127.0.0.1' || host.endsWith('.localtest.me')) {
		neonConfig.fetchEndpoint = `http://${host}:4444/sql`;
	}
	return drizzle({ client: neon(url) });
}
