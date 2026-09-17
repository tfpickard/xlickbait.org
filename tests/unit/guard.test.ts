import { describe, expect, it } from 'vitest';
import {
	ProductionGuardError,
	assertNotProduction,
	databaseHost,
	normalizeDatabaseHost
} from '$lib/server/db/guard';

const POOLED =
	'postgresql://u:p@ep-aged-mud-b4pxzrd6-pooler.c-6.us-east-2.aws.neon.tech/neondb?sslmode=require';
const DIRECT =
	'postgresql://u:p@ep-aged-mud-b4pxzrd6.c-6.us-east-2.aws.neon.tech/neondb?sslmode=require';
const DIRECT_HOST = 'ep-aged-mud-b4pxzrd6.c-6.us-east-2.aws.neon.tech';
const POOLED_HOST = 'ep-aged-mud-b4pxzrd6-pooler.c-6.us-east-2.aws.neon.tech';

describe('databaseHost', () => {
	it('parses hosts that carry a cell identifier', () => {
		// Busy AWS regions insert a cell label, making the host five parts rather
		// than the four most examples show. A regex on label count would fail to
		// match production here -- the one case that must never slip through.
		expect(databaseHost(POOLED)).toBe(POOLED_HOST);
		expect(databaseHost('postgresql://u:p@ep-x-1.us-east-2.aws.neon.tech/db')).toBe(
			'ep-x-1.us-east-2.aws.neon.tech'
		);
	});

	it('survives a password containing separator characters', () => {
		// Neon's endpoint-in-password workaround puts `=` and `;` in the password.
		const url = 'postgresql://user:endpoint%3Dep-abc%3Bsecret@ep-abc.us-east-2.aws.neon.tech/db';
		expect(databaseHost(url)).toBe('ep-abc.us-east-2.aws.neon.tech');
	});

	it('refuses rather than guessing when the URL will not parse', () => {
		expect(() => databaseHost('this is not a url')).toThrow(ProductionGuardError);
	});
});

describe('normalizeDatabaseHost', () => {
	it('treats the pooled and direct forms of one endpoint as the same database', () => {
		expect(normalizeDatabaseHost(POOLED_HOST)).toBe(normalizeDatabaseHost(DIRECT_HOST));
	});

	it('only strips -pooler from the endpoint label', () => {
		expect(normalizeDatabaseHost('ep-pooler-test-1.c-2.aws.neon.tech')).toBe(
			'ep-pooler-test-1.c-2.aws.neon.tech'
		);
	});
});

describe('assertNotProduction', () => {
	it('refuses an exact host match', () => {
		expect(() => assertNotProduction(POOLED, { XLICKBAIT_PROD_DB_HOST: POOLED_HOST })).toThrow(
			ProductionGuardError
		);
	});

	it('refuses a POOLED url when production is configured by its DIRECT host', () => {
		// This is the case a naive string comparison lets straight through, and it
		// is the likely one: Netlify gets the pooled URL, humans copy the direct one.
		expect(() => assertNotProduction(POOLED, { XLICKBAIT_PROD_DB_HOST: DIRECT_HOST })).toThrow(
			ProductionGuardError
		);
		expect(() => assertNotProduction(DIRECT, { XLICKBAIT_PROD_DB_HOST: POOLED_HOST })).toThrow(
			ProductionGuardError
		);
	});

	it('ignores case and surrounding whitespace in the configured host', () => {
		expect(() =>
			assertNotProduction(POOLED, { XLICKBAIT_PROD_DB_HOST: `  ${DIRECT_HOST.toUpperCase()} ` })
		).toThrow(ProductionGuardError);
	});

	it('fails closed when no production host is configured', () => {
		// A guard with nothing to compare against protects nothing, and silently
		// allowing it would be worse than useless because it looks like protection.
		expect(() => assertNotProduction(POOLED, {})).toThrow(ProductionGuardError);
		expect(() => assertNotProduction(POOLED, { XLICKBAIT_PROD_DB_HOST: '   ' })).toThrow(
			ProductionGuardError
		);
	});

	it('allows an unguarded run only on an explicit written acknowledgement', () => {
		expect(() => assertNotProduction(POOLED, { XLICKBAIT_ALLOW_NO_PROD_GUARD: '1' })).not.toThrow();
		// Anything other than an exact "1" is not an acknowledgement.
		expect(() => assertNotProduction(POOLED, { XLICKBAIT_ALLOW_NO_PROD_GUARD: 'true' })).toThrow(
			ProductionGuardError
		);
	});

	it('allows a genuinely different database', () => {
		expect(() =>
			assertNotProduction(POOLED, {
				XLICKBAIT_PROD_DB_HOST: 'ep-other-999999.c-2.us-east-2.aws.neon.tech'
			})
		).not.toThrow();
	});

	it('refuses an unparseable target even when a prod host is configured', () => {
		expect(() => assertNotProduction('garbage', { XLICKBAIT_PROD_DB_HOST: DIRECT_HOST })).toThrow(
			ProductionGuardError
		);
	});
});
