import { describe, expect, it } from 'vitest';
import { headlinePath, parseHeadlineSegment, slugify } from '$lib/slug';

describe('slugify', () => {
	it('lowercases and hyphenates', () => {
		expect(slugify('Why Are Computer Scientists So Obsessed?')).toBe(
			'why-are-computer-scientists-so-obsessed'
		);
	});

	it('folds diacritics rather than dropping the letter', () => {
		expect(slugify('Schrödinger and Erdős')).toBe('schrodinger-and-erdos');
	});

	it('drops apostrophes instead of turning them into hyphens', () => {
		// "Luxembourg's" must not become "luxembourg-s".
		expect(slugify("Luxembourg's Roads")).toBe('luxembourgs-roads');
		expect(slugify('You Won’t Believe')).toBe('you-wont-believe');
	});

	it('never produces leading, trailing or doubled hyphens', () => {
		const slug = slugify('  ...Multiple   Spaces & Symbols!!!  ');
		expect(slug).not.toMatch(/^-|-$|--/);
	});

	it('falls back rather than producing an empty slug', () => {
		// A headline of pure punctuation would otherwise yield "/h/12-".
		expect(slugify('!!!')).toBe('story');
		expect(slugify('')).toBe('story');
	});

	it('caps length without leaving a trailing hyphen', () => {
		const slug = slugify('a '.repeat(200));
		expect(slug.length).toBeLessThanOrEqual(80);
		expect(slug.endsWith('-')).toBe(false);
	});
});

describe('parseHeadlineSegment', () => {
	it('splits the id from a slug that itself contains hyphens', () => {
		expect(parseHeadlineSegment('42-why-are-they-obsessed')).toEqual({
			id: 42,
			slug: 'why-are-they-obsessed'
		});
	});

	it('round-trips with headlinePath', () => {
		const path = headlinePath(7, 'Scientists Baffled By Luxembourg');
		const parsed = parseHeadlineSegment(path.replace('/h/', ''));
		expect(parsed?.id).toBe(7);
		expect(`/h/${parsed?.id}-${parsed?.slug}`).toBe(path);
	});

	it('accepts an empty slug so a bare id still resolves and redirects', () => {
		expect(parseHeadlineSegment('42-')).toEqual({ id: 42, slug: '' });
	});

	it('rejects anything that is not a positive integer id', () => {
		for (const bad of ['abc-def', '-slug', '0-slug', '4.2-slug', '-1-slug', '', '99']) {
			expect(parseHeadlineSegment(bad)).toBeNull();
		}
	});

	it('rejects ids beyond safe integer range rather than silently rounding', () => {
		expect(parseHeadlineSegment('99999999999999999999-x')).toBeNull();
	});
});
