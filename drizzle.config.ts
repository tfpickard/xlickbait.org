import { defineConfig } from 'drizzle-kit';

/**
 * drizzle-kit reads the DIRECT (unpooled) connection string, never the pooled
 * one. Neon's pooler runs PgBouncer in transaction mode, which cannot hold the
 * session state that DDL and advisory locks rely on.
 *
 * This config is used by `drizzle-kit generate` (which needs no database at all)
 * and by `drizzle-kit migrate` via `bin/migrate.sh`. Never run `drizzle-kit push`
 * against the `main` branch -- schema changes reach production only as committed,
 * reviewed migrations.
 */
const url = process.env.DATABASE_URL_UNPOOLED;

export default defineConfig({
	dialect: 'postgresql',
	schema: './src/lib/server/db/schema.ts',
	out: './drizzle/migrations',
	strict: true,
	verbose: true,
	dbCredentials: { url: url ?? '' }
});
