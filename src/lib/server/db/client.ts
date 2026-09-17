import { neon, neonConfig } from '@neondatabase/serverless';
import { drizzle } from 'drizzle-orm/neon-http';
import { env } from '$env/dynamic/private';

/**
 * The database handle for the web app.
 *
 * `$env/dynamic/private` rather than `$env/static/private`: DATABASE_URL is
 * present at runtime in a Netlify Function, not at build time, and a static
 * import would bake in whatever was (not) set during the build.
 *
 * The neon-http driver fits because every request is one or two one-shot
 * SELECTs. There is no pool to leak across invocations and no WebSocket
 * dependency. It cannot open a transaction -- `db.transaction()` type-checks and
 * then throws at runtime -- which does not matter for a read-only app and is one
 * more reason writes live in the Python generator.
 */

let cached: ReturnType<typeof create> | undefined;

function configureLocalProxy(connectionString: string): void {
	// Running against a local Neon HTTP proxy (see docker-compose.dev.yml) needs
	// exactly one knob. It is global rather than per-client, so it has to be set
	// before the first neon() call.
	//
	// The switch is on the connection string's HOST, never on NODE_ENV. A host is
	// a fact about where we are actually pointed; NODE_ENV is a variable anyone
	// can set, and keying off it means a stray value could aim production traffic
	// at localhost. This way the production code path is byte-identical.
	const host = new URL(connectionString).hostname;
	const isLocal = host === 'localhost' || host === '127.0.0.1' || host.endsWith('.localtest.me');
	if (isLocal) {
		neonConfig.fetchEndpoint = `http://${host}:4444/sql`;
	}
}

function create() {
	const connectionString = env.DATABASE_URL;
	if (!connectionString) {
		throw new Error(
			'DATABASE_URL is not set. On Netlify it must be scoped to the runtime (functions), not only to builds.'
		);
	}
	configureLocalProxy(connectionString);
	return drizzle({ client: neon(connectionString) });
}

/**
 * The select-only surface of the Drizzle database.
 *
 * The full handle is deliberately never exported. `insert`, `update`, `delete`
 * and `execute` are not on this type, so a write in web code is a compile error
 * rather than something caught in review -- the strongest of the three layers
 * that keep this app read-only (the others are an ESLint rule and a source scan
 * in the test suite).
 */
export type ReadOnlyDatabase = Pick<
	ReturnType<typeof create>,
	'select' | 'selectDistinct' | 'with' | '$with' | '$count'
>;

/**
 * Lazily created and memoised. Lazy so that importing this module during a build
 * or a `svelte-kit sync` does not require a live DATABASE_URL; memoised so a warm
 * function instance reuses the same client.
 */
export function getDb(): ReadOnlyDatabase {
	cached ??= create();
	return cached;
}
