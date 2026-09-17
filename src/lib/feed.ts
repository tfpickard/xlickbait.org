import type { HeadlineCard } from './server/db/queries';
import { headlinePath } from './slug';
import { SITE_NAME } from './config';

/**
 * Atom 1.0 generation.
 *
 * Hand-rolled rather than pulled from a library: the feed is one element type
 * with a fixed shape, and the only genuinely tricky part -- escaping -- is
 * something worth owning outright rather than inheriting. The test suite parses
 * the output with a real XML parser, so this is checked against a parser rather
 * than against my expectations of one.
 */

/**
 * Escape text for an XML text node or attribute value.
 *
 * `&` is replaced first, or it would double-escape the entities introduced by
 * the replacements that follow it.
 */
export function escapeXml(value: string): string {
	return value
		.replaceAll('&', '&amp;')
		.replaceAll('<', '&lt;')
		.replaceAll('>', '&gt;')
		.replaceAll('"', '&quot;')
		.replaceAll("'", '&apos;');
}

/**
 * The XML 1.0 `Char` production, stated positively.
 *
 * Escaping does not help with these: a raw control character is a hard parse
 * error however it is encoded, so it has to be removed rather than escaped.
 * Abstracts come from an external API, so this is not hypothetical.
 */
function isLegalXmlCodePoint(code: number): boolean {
	return (
		code === 0x9 ||
		code === 0xa ||
		code === 0xd ||
		(code >= 0x20 && code <= 0xd7ff) ||
		(code >= 0xe000 && code <= 0xfffd) ||
		(code >= 0x10000 && code <= 0x10ffff)
	);
}

/** Iterates by code point, so surrogate pairs survive intact. */
export function stripIllegalXml(value: string): string {
	let out = '';
	for (const character of value) {
		const code = character.codePointAt(0);
		if (code !== undefined && isLegalXmlCodePoint(code)) out += character;
	}
	return out;
}

export function xmlSafe(value: string): string {
	return escapeXml(stripIllegalXml(value));
}

export interface FeedOptions {
	origin: string;
	items: HeadlineCard[];
	updated: string;
}

export function renderAtomFeed({ origin, items, updated }: FeedOptions): string {
	const selfUrl = `${origin}/feed.xml`;
	const latest = items[0]?.publishAt ?? updated;

	const entries = items
		.map((item) => {
			const url = `${origin}${headlinePath(item.id, item.headline)}`;
			// A tag: URI rather than the permalink, so an entry keeps its identity
			// even if the headline -- and therefore the slug -- is later edited.
			const id = `tag:xlickbait.org,2026:headline/${item.id}`;
			const summary = `${item.dek}\n\nWhat the paper actually says: ${item.actualPoint}`;
			return `	<entry>
		<title>${xmlSafe(item.headline)}</title>
		<id>${xmlSafe(id)}</id>
		<link rel="alternate" type="text/html" href="${xmlSafe(url)}"/>
		<link rel="related" type="text/html" href="${xmlSafe(item.absUrl)}"/>
		<published>${xmlSafe(item.publishAt)}</published>
		<updated>${xmlSafe(item.publishAt)}</updated>
		<category term="${xmlSafe(item.primaryCategory)}"/>
		<summary type="text">${xmlSafe(summary)}</summary>
	</entry>`;
		})
		.join('\n');

	return `<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
	<title>${xmlSafe(SITE_NAME)}</title>
	<subtitle>Sensational, technically true headlines about real arXiv preprints.</subtitle>
	<id>${xmlSafe(`${origin}/`)}</id>
	<link rel="self" type="application/atom+xml" href="${xmlSafe(selfUrl)}"/>
	<link rel="alternate" type="text/html" href="${xmlSafe(`${origin}/`)}"/>
	<updated>${xmlSafe(latest)}</updated>
	<rights>Paper metadata is CC0 via arXiv. Not affiliated with arXiv.</rights>
${entries}
</feed>
`;
}
