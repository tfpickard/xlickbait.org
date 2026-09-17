/**
 * Guards for destructive scripts (seed, reset) and for migrations.
 *
 * The whole point of these is to make "oops, that was production" impossible
 * rather than unlikely, so every failure mode here is fail-closed: an
 * unparseable URL, an unconfigured guard, or a host match all refuse to run.
 */

export class ProductionGuardError extends Error {
	constructor(message: string) {
		super(message);
		this.name = 'ProductionGuardError';
	}
}

/**
 * Extract the hostname from a Postgres connection string.
 *
 * Uses `new URL()` deliberately. Neon hostnames are not a fixed shape -- busy
 * AWS regions insert a cell identifier, so an endpoint can be
 * `ep-name-123456.c-6.us-east-2.aws.neon.tech` (five labels) rather than the
 * four-label form most examples show. A regex built on label count silently
 * fails to match production, which is the one case that must never slip through.
 * `new URL()` also handles Neon's endpoint-in-password workaround, where the
 * password may itself contain `=` and `;`.
 */
export function databaseHost(connectionString: string): string {
	let parsed: URL;
	try {
		parsed = new URL(connectionString);
	} catch {
		throw new ProductionGuardError(
			'Refusing to run: the connection string could not be parsed as a URL, so its host cannot be checked against production.'
		);
	}
	if (!parsed.hostname) {
		throw new ProductionGuardError('Refusing to run: the connection string has no hostname.');
	}
	return parsed.hostname.toLowerCase();
}

/**
 * Normalise a Neon hostname for comparison by stripping the `-pooler` suffix
 * from the endpoint label.
 *
 * Pooled and direct connection strings for the SAME database differ only in that
 * suffix. Comparing raw hostnames would treat them as different databases, so a
 * pooled production URL would sail past a guard configured with the direct host.
 */
export function normalizeDatabaseHost(host: string): string {
	const labels = host.toLowerCase().split('.');
	const [endpoint, ...rest] = labels;
	if (endpoint === undefined) return host.toLowerCase();
	return [endpoint.replace(/-pooler$/, ''), ...rest].join('.');
}

export interface GuardEnv {
	XLICKBAIT_PROD_DB_HOST?: string | undefined;
	XLICKBAIT_ALLOW_NO_PROD_GUARD?: string | undefined;
}

/**
 * Throw if `connectionString` points at the production database.
 *
 * Also throws when no production host is configured at all: a guard with nothing
 * to compare against protects nothing, and silently allowing that would be worse
 * than useless because it looks like protection. Set XLICKBAIT_PROD_DB_HOST, or
 * set XLICKBAIT_ALLOW_NO_PROD_GUARD=1 to acknowledge in writing that no
 * production database exists yet.
 */
export function assertNotProduction(connectionString: string, env: GuardEnv): void {
	const target = normalizeDatabaseHost(databaseHost(connectionString));
	const configured = env.XLICKBAIT_PROD_DB_HOST?.trim();

	if (!configured) {
		if (env.XLICKBAIT_ALLOW_NO_PROD_GUARD === '1') return;
		throw new ProductionGuardError(
			'Refusing to run: XLICKBAIT_PROD_DB_HOST is not set, so this script cannot tell whether it is pointed at production.\n' +
				'Set it to the hostname of the Neon `main` branch endpoint, or set XLICKBAIT_ALLOW_NO_PROD_GUARD=1 if no production database exists yet.'
		);
	}

	if (normalizeDatabaseHost(configured) === target) {
		throw new ProductionGuardError(
			`Refusing to run against the production database (${target}).\n` +
				'This script is destructive and is only ever allowed to touch the `dev` branch.'
		);
	}
}
