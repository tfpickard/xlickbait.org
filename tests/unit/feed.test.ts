import { describe, expect, it } from 'vitest';
import { XMLParser, XMLValidator } from 'fast-xml-parser';
import { escapeXml, renderAtomFeed, stripIllegalXml, xmlSafe } from '$lib/feed';
import type { HeadlineCard } from '$lib/server/db/queries';

function card(overrides: Partial<HeadlineCard> = {}): HeadlineCard {
	return {
		id: 1,
		headline: 'Scientists Baffled',
		dek: 'They cannot explain it.',
		anchor: 'baffled',
		actualPoint: 'It is a paper about statistics.',
		kind: 'fresh',
		publishAt: '2026-09-17T02:03:50.000Z',
		arxivId: '0000.00001',
		title: 'A Paper',
		primaryCategory: 'stat.ML',
		categories: ['stat.ML'],
		absUrl: 'https://arxiv.org/abs/0000.00001',
		image: null,
		...overrides
	};
}

describe('renderAtomFeed', () => {
	it('produces XML a real parser accepts', () => {
		const xml = renderAtomFeed({
			origin: 'https://xlickbait.org',
			items: [card(), card({ id: 2, headline: 'Another' })],
			updated: '2026-09-17T00:00:00.000Z'
		});
		expect(XMLValidator.validate(xml)).toBe(true);
	});

	it('has the structure Atom requires', () => {
		const xml = renderAtomFeed({
			origin: 'https://xlickbait.org',
			items: [card()],
			updated: '2026-09-17T00:00:00.000Z'
		});
		const parsed = new XMLParser({ ignoreAttributes: false }).parse(xml);
		const feed = parsed.feed;
		expect(feed['@_xmlns']).toBe('http://www.w3.org/2005/Atom');
		for (const required of ['id', 'title', 'updated']) {
			expect(feed[required], `feed is missing <${required}>`).toBeDefined();
		}
		const entry = feed.entry;
		for (const required of ['id', 'title', 'updated', 'link']) {
			expect(entry[required], `entry is missing <${required}>`).toBeDefined();
		}
	});

	it('links entries to the permalink and relates them to the paper', () => {
		const xml = renderAtomFeed({
			origin: 'https://xlickbait.org',
			items: [card()],
			updated: '2026-09-17T00:00:00.000Z'
		});
		const entry = new XMLParser({ ignoreAttributes: false }).parse(xml).feed.entry;
		const links: { '@_rel': string; '@_href': string }[] = entry.link;
		const alternate = links.find((l) => l['@_rel'] === 'alternate');
		const related = links.find((l) => l['@_rel'] === 'related');
		expect(alternate?.['@_href']).toBe('https://xlickbait.org/h/1-scientists-baffled');
		expect(related?.['@_href']).toBe('https://arxiv.org/abs/0000.00001');
	});

	it('uses a stable tag: id that survives a headline edit', () => {
		const a = renderAtomFeed({
			origin: 'https://xlickbait.org',
			items: [card({ headline: 'Original Wording' })],
			updated: '2026-09-17T00:00:00.000Z'
		});
		const b = renderAtomFeed({
			origin: 'https://xlickbait.org',
			items: [card({ headline: 'Completely Rewritten' })],
			updated: '2026-09-17T00:00:00.000Z'
		});
		const idOf = (xml: string) => new XMLParser().parse(xml).feed.entry.id as string;
		expect(idOf(a)).toBe(idOf(b));
		expect(idOf(a)).toBe('tag:xlickbait.org,2026:headline/1');
	});

	it('survives headlines full of XML metacharacters', () => {
		// These arrive from a language model and quote real abstracts, so angle
		// brackets and ampersands are a matter of time, not a hypothetical.
		const nasty = 'AT&T <script>alert("x")</script> & "quotes" & \'apostrophes\'';
		const xml = renderAtomFeed({
			origin: 'https://xlickbait.org',
			items: [card({ headline: nasty, dek: nasty, actualPoint: nasty })],
			updated: '2026-09-17T00:00:00.000Z'
		});
		expect(XMLValidator.validate(xml)).toBe(true);
		expect(xml).not.toContain('<script>');
		const title = new XMLParser().parse(xml).feed.entry.title;
		expect(title).toContain('AT&T');
	});

	it('stays valid when an abstract carries illegal control characters', () => {
		// Escaping cannot save a raw control character -- it is a hard parse error
		// however it is encoded -- so it has to be removed outright.
		const withControls = `Bad${String.fromCharCode(0)}chars${String.fromCharCode(8)}here`;
		const xml = renderAtomFeed({
			origin: 'https://xlickbait.org',
			items: [card({ dek: withControls })],
			updated: '2026-09-17T00:00:00.000Z'
		});
		expect(XMLValidator.validate(xml)).toBe(true);
	});

	it('renders an empty feed without breaking', () => {
		const xml = renderAtomFeed({
			origin: 'https://xlickbait.org',
			items: [],
			updated: '2026-09-17T00:00:00.000Z'
		});
		expect(XMLValidator.validate(xml)).toBe(true);
	});
});

describe('escaping helpers', () => {
	it('escapes ampersands first, so entities are not double-escaped', () => {
		expect(escapeXml('a & b < c')).toBe('a &amp; b &lt; c');
		expect(escapeXml('&lt;')).toBe('&amp;lt;');
	});

	it('keeps tab, newline and carriage return, which are legal', () => {
		expect(stripIllegalXml('a\tb\nc\rd')).toBe('a\tb\nc\rd');
	});

	it('preserves astral characters instead of splitting surrogate pairs', () => {
		// Iterating by code unit would cut an emoji in half and produce invalid XML.
		const astral = 'telescope \u{1F52D} here';
		expect(stripIllegalXml(astral)).toBe(astral);
		expect(xmlSafe(astral)).toContain('\u{1F52D}');
	});
});
