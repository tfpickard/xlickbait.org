/**
 * Apply migrations over Neon's SQL-over-HTTP endpoint.
 *
 * This exists because some networks allow outbound HTTPS but not raw Postgres on
 * 5432 -- including the container this project was built in. `drizzle-kit
 * migrate` speaks the wire protocol and simply cannot run there.
 *
 * The tradeoff is real and is why `bin/migrate.sh` refuses this transport for
 * `main`: the HTTP driver has no transactions, so a migration that fails halfway
 * leaves the schema partially applied with no rollback. That is tolerable on a
 * branch you can reset and unacceptable on production.
 */
import { neon } from '@neondatabase/serverless';
import { drizzle } from 'drizzle-orm/neon-http';
import { migrate } from 'drizzle-orm/neon-http/migrator';

const url = process.env.DATABASE_URL_UNPOOLED;
if (!url) {
	console.error('DATABASE_URL_UNPOOLED is not set');
	process.exit(1);
}

const db = drizzle({ client: neon(url) });

await migrate(db, { migrationsFolder: './drizzle/migrations' });
console.log('migrations applied');
