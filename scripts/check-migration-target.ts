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
		// Fail closed. `if (configured && ...)` silently skipped the whole check
		// when the variable was unset, so `bin/migrate.sh main` would apply
		// production migrations to whatever DATABASE_URL_UNPOOLED_MAIN happened to
		// hold -- including the dev branch. An unconfigured guard protects nothing
		// and is worse than none, because it looks like protection.
		if (!configured) {
			refuse(
				"Refusing to migrate 'main': XLICKBAIT_PROD_DB_HOST is not set, so there is nothing to check the target against.\n" +
					'Set it to the hostname of the production branch endpoint.\n' +
					'XLICKBAIT_ALLOW_NO_PROD_GUARD does not apply here: it acknowledges that no production database exists, which cannot be true while migrating one.'
			);
		}
		if (normalizeDatabaseHost(configured) !== target) {
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
