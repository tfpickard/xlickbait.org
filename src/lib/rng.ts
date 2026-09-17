/**
 * Deterministic seeded randomness.
 *
 * Used for procedurally generated thumbnails (which must be byte-identical for a
 * given arXiv id, forever) and for the chumbox shuffle. Nothing here touches
 * `Math.random` or the clock, so output depends only on the seed string.
 *
 * xmur3 and mulberry32 are the standard small-PRNG pair for this job: integer
 * operations only, no floating-point accumulation, identical results on every
 * engine.
 */

/** Hash a string into a 32-bit seed generator. */
export function xmur3(input: string): () => number {
	let h = 1779033703 ^ input.length;
	for (let i = 0; i < input.length; i++) {
		h = Math.imul(h ^ input.charCodeAt(i), 3432918353);
		h = (h << 13) | (h >>> 19);
	}
	return () => {
		h = Math.imul(h ^ (h >>> 16), 2246822507);
		h = Math.imul(h ^ (h >>> 13), 3266489909);
		h ^= h >>> 16;
		return h >>> 0;
	};
}

/** A 32-bit PRNG returning floats in [0, 1). */
export function mulberry32(seed: number): () => number {
	let a = seed >>> 0;
	return () => {
		a = (a + 0x6d2b79f5) >>> 0;
		let t = a;
		t = Math.imul(t ^ (t >>> 15), t | 1);
		t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
		return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
	};
}

/** Convenience: a PRNG seeded from an arbitrary string. */
export function seededRandom(seed: string): () => number {
	return mulberry32(xmur3(seed)());
}

/**
 * Fisher-Yates using a supplied PRNG. Returns a new array; the input is not
 * mutated, so callers can shuffle a cached query result safely.
 */
export function shuffle<T>(items: readonly T[], random: () => number): T[] {
	const out = items.slice();
	for (let i = out.length - 1; i > 0; i--) {
		const j = Math.floor(random() * (i + 1));
		const a = out[i] as T;
		const b = out[j] as T;
		out[i] = b;
		out[j] = a;
	}
	return out;
}
