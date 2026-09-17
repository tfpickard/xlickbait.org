/**
 * Permalink slugs.
 *
 * A permalink is `/h/<id>-<slug>`. The id is authoritative; the slug is
 * decoration that exists for humans and search engines. A request with the wrong
 * slug still resolves, then redirects to the canonical spelling, so that link rot
 * is impossible when a headline is edited.
 */

const MAX_SLUG_LENGTH = 80;

export function slugify(input: string): string {
	const slug = input
		.normalize('NFKD')
		// Strip combining marks so "Schrödinger" becomes "schrodinger" rather than
		// losing the letter entirely.
		.replace(/[̀-ͯ]/g, '')
		.toLowerCase()
		.replace(/['’]/g, '')
		.replace(/[^a-z0-9]+/g, '-')
		.replace(/^-+|-+$/g, '')
		.slice(0, MAX_SLUG_LENGTH)
		.replace(/-+$/g, '');

	// A headline of pure punctuation or non-Latin script would otherwise produce
	// an empty slug and a permalink ending in a bare hyphen.
	return slug || 'story';
}

/** The `<id>-<slug>` value of the `[entry]` route parameter. */
export function headlineEntry(id: number, headline: string): string {
	return `${id}-${slugify(headline)}`;
}

/**
 * The permalink path, without any base path applied.
 *
 * Components should prefer `permalinkPath()` from `$lib/links`, which routes
 * through SvelteKit's `resolve()`. This plain form exists for the Atom feed,
 * which builds absolute URLs and is unit-tested outside a SvelteKit context.
 */
export function headlinePath(id: number, headline: string): string {
	return `/h/${headlineEntry(id, headline)}`;
}

/**
 * A headline illustration, without any base path applied.
 *
 * No slug, and deliberately so. The permalink carries one because humans read
 * and share it; this URL is only ever an `<img src>`, and a slug on it would be
 * a second spelling of the headline to keep in sync for nobody's benefit.
 *
 * Components should use `resolve('/i/[id=id]', ...)` so the base path is
 * applied. This plain form exists for the OG tags, which need an absolute URL
 * built from the request origin.
 */
export function imagePath(id: number): string {
	return `/i/${id}`;
}

/**
 * Split the `<id>-<slug>` segment. The route matcher guarantees a leading run of
 * digits, so this only has to peel it off.
 */
export function parseHeadlineSegment(segment: string): { id: number; slug: string } | null {
	const match = /^(\d+)-(.*)$/.exec(segment);
	if (!match) return null;
	const id = Number(match[1]);
	if (!Number.isSafeInteger(id) || id <= 0) return null;
	return { id, slug: match[2] ?? '' };
}
