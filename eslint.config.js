import prettier from 'eslint-config-prettier';
import path from 'node:path';
import js from '@eslint/js';
import svelte from 'eslint-plugin-svelte';
import { defineConfig, includeIgnoreFile } from 'eslint/config';
import globals from 'globals';
import ts from 'typescript-eslint';

const gitignorePath = path.resolve(import.meta.dirname, '.gitignore');

export default defineConfig(
	includeIgnoreFile(gitignorePath),
	js.configs.recommended,
	ts.configs.recommended,
	svelte.configs.recommended,
	prettier,
	svelte.configs.prettier,
	{
		languageOptions: { globals: { ...globals.browser, ...globals.node } },
		rules: {
			// typescript-eslint strongly recommend that you do not use the no-undef lint rule on TypeScript projects.
			// see: https://typescript-eslint.io/troubleshooting/faqs/eslint/#i-get-errors-from-the-no-undef-rule-about-global-variables-not-being-defined-even-though-there-are-no-typescript-errors
			'no-undef': 'off'
		}
	},
	{
		files: ['**/*.svelte', '**/*.svelte.ts', '**/*.svelte.js'],
		languageOptions: {
			parserOptions: {
				projectService: true,
				extraFileExtensions: ['.svelte'],
				parser: ts.parser
			}
		}
	},
	{
		// Layer two of the read-only guarantee (the type system is layer one, and a
		// source scan in tests/unit/no-writes.test.ts is layer three).
		//
		// Scoped to src/ only: scripts/ genuinely needs to seed and reset, and runs
		// from a developer's machine rather than from Netlify.
		files: ['src/**/*.{ts,js,svelte}'],
		rules: {
			'no-restricted-syntax': [
				'error',
				{
					selector:
						'CallExpression > MemberExpression[property.name=/^(insert|update|delete|execute)$/]',
					message:
						'The web app is read-only. Writes belong in the Python generator; see src/lib/server/db/client.ts.'
				}
			]
		}
	},
	{
		// Nothing outside the db client may reach for the driver directly -- that is
		// how a second, unrestricted handle would get created.
		files: ['src/**/*.{ts,js,svelte}'],
		ignores: ['src/lib/server/db/client.ts'],
		rules: {
			'no-restricted-imports': [
				'error',
				{
					paths: [
						{
							name: 'drizzle-orm/neon-http',
							message: 'Import the read-only handle from $lib/server/db/client instead.'
						},
						{
							name: '@neondatabase/serverless',
							message: 'Import the read-only handle from $lib/server/db/client instead.'
						}
					]
				}
			]
		}
	}
);
