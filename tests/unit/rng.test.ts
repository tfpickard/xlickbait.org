import { describe, expect, it } from 'vitest';
import { mulberry32, seededRandom, shuffle, xmur3 } from '$lib/rng';

describe('seeded randomness', () => {
	it('gives the same sequence for the same seed', () => {
		const a = seededRandom('hello');
		const b = seededRandom('hello');
		const left = Array.from({ length: 20 }, () => a());
		const right = Array.from({ length: 20 }, () => b());
		expect(left).toEqual(right);
	});

	it('gives different sequences for different seeds', () => {
		const a = Array.from({ length: 10 }, seededRandom('alpha'));
		const b = Array.from({ length: 10 }, seededRandom('beta'));
		expect(a).not.toEqual(b);
	});

	it('stays within [0, 1)', () => {
		const random = seededRandom('bounds');
		for (let i = 0; i < 1000; i++) {
			const value = random();
			expect(value).toBeGreaterThanOrEqual(0);
			expect(value).toBeLessThan(1);
		}
	});

	it('hashes distinct strings to distinct seeds', () => {
		const seeds = ['a', 'b', 'c', 'aa', 'ab', ''].map((s) => xmur3(s)());
		expect(new Set(seeds).size).toBe(seeds.length);
	});

	it('shuffles deterministically without mutating the input', () => {
		const input = Object.freeze([1, 2, 3, 4, 5, 6, 7, 8]);
		const a = shuffle(input, mulberry32(42));
		const b = shuffle(input, mulberry32(42));
		expect(a).toEqual(b);
		expect(input).toEqual([1, 2, 3, 4, 5, 6, 7, 8]);
		expect([...a].sort((x, y) => x - y)).toEqual([...input].sort((x, y) => x - y));
	});
});
