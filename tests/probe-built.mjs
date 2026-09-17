/**
 * Probe the built Netlify function in a real Node process.
 *
 * Deliberately NOT imported into Vitest: Vitest runs modules through Vite's
 * transform pipeline, which re-processes the already-bundled output and changes
 * its behaviour. The point of this tier is to exercise the artifact exactly as
 * Netlify's runtime loads it, so it has to run outside that pipeline.
 *
 * Usage: node tests/probe-built.mjs /path /another
 * Prints one JSON array of { path, status, headers, body } to stdout.
 */
const handlerUrl = new URL('../.netlify/functions-internal/sveltekit-render.mjs', import.meta.url);
const { default: handler } = await import(handlerUrl.href);

const results = [];
for (const path of process.argv.slice(2)) {
	const response = await handler(new Request(`https://xlickbait.org${path}`), {});
	results.push({
		path,
		status: response.status,
		headers: Object.fromEntries(response.headers),
		body: response.status === 200 ? (await response.text()).slice(0, 4000) : ''
	});
}
process.stdout.write(JSON.stringify(results));
