import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';
import { describe, expect, it } from 'vitest';

/**
 * The web app is read-only. Three independent layers enforce that, and this file
 * is the third.
 *
 *   1. The type system. `src/lib/server/db/client.ts` exports a handle narrowed
 *      to the select side, so `db.insert(...)` does not compile.
 *   2. ESLint, via no-restricted-syntax.
 *   3. This scan -- which is the only one that catches a write smuggled through a
 *      raw SQL template string, where there is no `.insert(` member call for the
 *      other two layers to see.
 *
 * Deleting or weakening any of these to make a change pass is exactly the thing
 * they exist to prevent.
 */

const SRC = new URL('../../src', import.meta.url).pathname;

function sourceFiles(dir: string): string[] {
	const out: string[] = [];
	for (const entry of readdirSync(dir)) {
		const full = join(dir, entry);
		if (statSync(full).isDirectory()) {
			out.push(...sourceFiles(full));
		} else if (/\.(ts|js|svelte)$/.test(entry)) {
			out.push(full);
		}
	}
	return out;
}

/** Strip comments so prose describing a write is not mistaken for one. */
function stripComments(source: string): string {
	return source.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:])\/\/.*$/gm, '$1');
}

const WRITE_CALLS = /\.\s*(insert|update|delete|execute)\s*\(/;
const RAW_DML =
	/\b(insert\s+into|update\s+\w+\s+set|delete\s+from|truncate\b|drop\s+(table|index|type|schema)|alter\s+table|create\s+(table|index|type|schema))\b/i;

describe('the web app cannot write to the database', () => {
	const files = sourceFiles(SRC);

	it('scans a meaningful number of files', () => {
		// Guards the guard: a broken walk would make everything below vacuously pass.
		expect(files.length).toBeGreaterThan(15);
	});

	it('contains no insert/update/delete/execute calls anywhere in src/', () => {
		const offenders = files.filter((file) =>
			WRITE_CALLS.test(stripComments(readFileSync(file, 'utf8')))
		);
		expect(offenders.map((f) => relative(SRC, f))).toEqual([]);
	});

	it('contains no raw DML or DDL in SQL strings', () => {
		const offenders = files.filter((file) =>
			RAW_DML.test(stripComments(readFileSync(file, 'utf8')))
		);
		expect(offenders.map((f) => relative(SRC, f))).toEqual([]);
	});

	it('never exports the unrestricted drizzle handle', () => {
		const client = readFileSync(join(SRC, 'lib/server/db/client.ts'), 'utf8');
		// The instance itself must stay module-private; only the narrowed accessor
		// may leave this file.
		expect(client).not.toMatch(/export\s+(const|let)\s+db\b/);
		expect(client).toMatch(/export\s+function\s+getDb/);
		expect(client).toMatch(/ReadOnlyDatabase/);
	});

	it('imports the driver in exactly one place', () => {
		const importers = files.filter((file) =>
			/from\s+['"](drizzle-orm\/neon-http|@neondatabase\/serverless)['"]/.test(
				readFileSync(file, 'utf8')
			)
		);
		expect(importers.map((f) => relative(SRC, f))).toEqual(['lib/server/db/client.ts']);
	});
});
