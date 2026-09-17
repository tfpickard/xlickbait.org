/**
 * Confirm a migration is pointed where it claims to be, in both directions.
 *
 * `bin/migrate.sh dev` must not reach production, and -- just as important --
 * `bin/migrate.sh main` must not quietly apply production migrations to the dev
 * branch because a shell variable was empty. Both are the same class of mistake
 * and both are caught here, using the same host-normalising guard the seed and
 * reset scripts use.
 */
import {
	ProductionGuardError,
	assertNotProduction,
	databaseHost,
	normalizeDatabaseHost
} from '../src/lib/server/db/guard';

const [branch, url] = process.argv.slice(2);

function refuse(message: string): never {
	console.error(`\n  REFUSED\n\n  ${message.split('\n').join('\n  ')}\n`);
	process.exit(1);
}

if (!branch || !url) refuse('usage: check-migration-target.ts <dev|main> <connection-string>');

try {
	const target = normalizeDatabaseHost(databaseHost(url));

	if (branch === 'dev') {
		assertNotProduction(url, process.env);
	} else {
		const configured = process.env.XLICKBAIT_PROD_DB_HOST?.trim();
		if (configured && normalizeDatabaseHost(configured) !== target) {
			refuse(
				`Refusing to migrate 'main' against ${target}, which is not the configured production host (${normalizeDatabaseHost(configured)}).\n` +
					'Check DATABASE_URL_UNPOOLED_MAIN.'
			);
		}
	}
	console.log(`==> target for '${branch}' is ${target}`);
} catch (error) {
	if (error instanceof ProductionGuardError) refuse(error.message);
	throw error;
}
