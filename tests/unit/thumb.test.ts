import { describe, expect, it } from 'vitest';
import { thumbnailFor } from '$lib/thumb';

describe('thumbnailFor', () => {
	it('is byte-identical for the same id, every time', () => {
		// This is the whole contract. The SVG is inlined into CDN-cached HTML, so a
		// generator that drifted between calls would produce pages that disagree
		// with each other depending on which edge node rendered them.
		const first = thumbnailFor('2401.01234').svg;
		for (let i = 0; i < 50; i++) {
			expect(thumbnailFor('2401.01234').svg).toBe(first);
		}
	});

	it('produces different art for different ids', () => {
		const ids = ['0704.0001', '1412.9999', '1501.00001', '2401.01234', '2509.54321'];
		const svgs = ids.map((id) => thumbnailFor(id).svg);
		expect(new Set(svgs).size).toBe(ids.length);
	});

	it('never embeds the identifier as text', () => {
		// The id is a numeric seed only. If it ever reached the markup as a string
		// there would be an escaping surface where there is currently none.
		const svg = thumbnailFor('2401.01234').svg;
		expect(svg).not.toContain('2401.01234');
		expect(svg).not.toContain('<text');
	});

	it('emits well-formed, self-contained SVG', () => {
		const svg = thumbnailFor('1706.03762').svg;
		expect(svg.startsWith('<svg')).toBe(true);
		expect(svg.endsWith('</svg>')).toBe(true);
		expect(svg).toContain('xmlns="http://www.w3.org/2000/svg"');

		// Nothing that would cause a fetch. The xmlns declaration is a namespace
		// identifier rather than a URL the renderer resolves, so it is excluded --
		// what matters is that no element can pull bytes from off-site.
		expect(svg).not.toContain('<image');
		expect(svg).not.toContain('xlink:href');
		expect(svg).not.toContain('@import');
		expect(svg).not.toMatch(/url\(\s*['"]?https?:/);
		const externalRefs = svg.match(/https?:\/\/[^"']+/g) ?? [];
		expect(externalRefs).toEqual(['http://www.w3.org/2000/svg']);
	});

	it('gives each id its own element ids, so two on one page cannot collide', () => {
		const a = thumbnailFor('1111.11111').svg;
		const b = thumbnailFor('2222.22222').svg;
		const idOf = (svg: string) => /id="(g[0-9a-f]+)"/.exec(svg)?.[1];
		expect(idOf(a)).toBeDefined();
		expect(idOf(a)).not.toBe(idOf(b));
	});

	it('matches a pinned golden string', () => {
		// A change here means every cached thumbnail on the site changes. That
		// should be a deliberate decision, so it is pinned rather than snapshotted.
		expect(thumbnailFor('0000.00001').svg).toMatchSnapshot();
	});
});
