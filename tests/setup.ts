/**
 * Load .env so integration tests can reach the dev branch.
 *
 * Tests that need a database skip themselves when DATABASE_URL is absent rather
 * than failing, so a fresh checkout with no .env still gets a green unit suite.
 */
import { existsSync } from 'node:fs';

if (existsSync('.env')) {
	process.loadEnvFile('.env');
}
