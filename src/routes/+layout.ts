/**
 * Nothing on this site is prerendered.
 *
 * Content arrives in the database from a generator running elsewhere on a cron,
 * and the entire point is that it appears without a rebuild. Prerendering any
 * DB-backed page would freeze it at build time. SvelteKit already defaults
 * `prerender` to false; this is an explicit guard so that turning it on somewhere
 * has to be a deliberate, visible act.
 */
export const prerender = false;
export const ssr = true;
