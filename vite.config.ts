import { defineConfig } from 'vitest/config';
import adapter from '@sveltejs/adapter-netlify';
import { sveltekit } from '@sveltejs/kit/vite';

export default defineConfig({
	plugins: [
		sveltekit({
			compilerOptions: {
				// Force runes mode for the project, except for libraries. Can be removed in svelte 6.
				runes: ({ filename }) =>
					filename.split(/[/\\]/).includes('node_modules') ? undefined : true
			},
			// `edge` and `split` are passed explicitly rather than left to default.
			//
			// `edge` defaults to reading the NETLIFY_SVELTEKIT_USE_EDGE environment
			// variable, so omitting it would let the environment move SSR onto the
			// Deno edge runtime without a code change. That would break us: the edge
			// runtime has no `fs`, caps CPU per request, and Netlify's `durable`
			// cache directive has no effect on edge function responses.
			//
			// `split: false` keeps SSR in a single `sveltekit-render` Node function.
			adapter: adapter({ edge: false, split: false })
		})
	],
	test: {
		expect: { requireAssertions: true },
		setupFiles: ['./tests/setup.ts'],
		projects: [
			{
				extends: './vite.config.ts',
				test: {
					name: 'server',
					environment: 'node',
					include: ['src/**/*.{test,spec}.{js,ts}', 'tests/unit/**/*.{test,spec}.{js,ts}'],
					exclude: ['src/**/*.svelte.{test,spec}.{js,ts}']
				}
			}
		]
	}
});
