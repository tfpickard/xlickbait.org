import { mulberry32, xmur3 } from './rng';

/**
 * Procedurally generated thumbnails.
 *
 * Every headline gets an image that looks like it was chosen to imply drama: a
 * saturated gradient, big soft shapes suggesting a figure or an object, a hard
 * diagonal light streak. It is entirely fictional, which is the point -- there
 * are no stock photos, no hotlinking, and nothing fetched from anywhere.
 *
 * The output must be byte-identical for a given arXiv id, forever, because it is
 * inlined into CDN-cached HTML. That rules out `Math.random`, the clock, locale
 * formatting, and any floating-point value printed at full precision. Every
 * number below goes through `n()`, which fixes two decimal places.
 *
 * The id is never interpolated into the SVG as text -- only as a numeric seed and
 * as a hex suffix on element ids. There is therefore no string from the database
 * reaching the markup, and no escaping surface.
 */

/** Lurid but contemporary. Each entry is [from, via, to, accent]. */
const PALETTES: readonly (readonly [string, string, string, string])[] = [
	['#2b0a3d', '#7b1fa2', '#ff4081', '#ffd54f'],
	['#001f3f', '#0074d9', '#7fdbff', '#ff851b'],
	['#3d0000', '#c62828', '#ff7043', '#fff176'],
	['#0b3d2e', '#00897b', '#64ffda', '#ffab40'],
	['#1a1a2e', '#16213e', '#e94560', '#f5f5f5'],
	['#2d1b00', '#ff6f00', '#ffca28', '#4fc3f7'],
	['#12002e', '#4a148c', '#00e5ff', '#ff4081'],
	['#0d0d0d', '#424242', '#ff1744', '#69f0ae']
];

const WIDTH = 800;
const HEIGHT = 450;

/** Fixed-precision number formatting -- the determinism guarantee lives here. */
function n(value: number): string {
	return value.toFixed(2);
}

export interface Thumbnail {
	svg: string;
	/** A flat description for `aria-label`; the image carries no information. */
	label: string;
}

export function thumbnailFor(arxivId: string): Thumbnail {
	const seedOf = xmur3(arxivId);
	const suffix = seedOf().toString(16).padStart(8, '0');
	const random = mulberry32(seedOf());

	const palette = PALETTES[Math.floor(random() * PALETTES.length)] as readonly [
		string,
		string,
		string,
		string
	];
	const [from, via, to, accent] = palette;

	const gradientId = `g${suffix}`;
	const blurId = `b${suffix}`;
	const angle = 20 + random() * 50;

	const blobs: string[] = [];
	const blobCount = 3 + Math.floor(random() * 2);
	for (let i = 0; i < blobCount; i++) {
		const cx = WIDTH * (0.15 + random() * 0.7);
		const cy = HEIGHT * (0.15 + random() * 0.7);
		const rx = WIDTH * (0.12 + random() * 0.22);
		const ry = HEIGHT * (0.14 + random() * 0.26);
		const fill = i % 2 === 0 ? to : via;
		const opacity = 0.35 + random() * 0.3;
		blobs.push(
			`<ellipse cx="${n(cx)}" cy="${n(cy)}" rx="${n(rx)}" ry="${n(ry)}" fill="${fill}" opacity="${n(opacity)}" filter="url(#${blurId})"/>`
		);
	}

	// The focal blob: smaller, brighter, off-centre. Reads as "the thing the
	// photo is supposedly of".
	const fx = WIDTH * (0.3 + random() * 0.4);
	const fy = HEIGHT * (0.3 + random() * 0.35);
	const fr = WIDTH * (0.05 + random() * 0.05);
	const focal = `<circle cx="${n(fx)}" cy="${n(fy)}" r="${n(fr)}" fill="${accent}" opacity="0.85"/>`;

	// Hard diagonal light streak across the frame.
	const streakX = WIDTH * (0.1 + random() * 0.5);
	const streakWidth = WIDTH * (0.04 + random() * 0.08);
	const streak =
		`<g transform="rotate(${n(angle)} ${n(WIDTH / 2)} ${n(HEIGHT / 2)})">` +
		`<rect x="${n(streakX)}" y="${n(-HEIGHT)}" width="${n(streakWidth)}" height="${n(HEIGHT * 3)}" fill="#ffffff" opacity="0.14"/>` +
		`</g>`;

	// A flat darkening pass over the whole frame, so light text sits legibly on
	// top of whatever the palette produced.
	const vignette = `<rect width="${WIDTH}" height="${HEIGHT}" fill="#000000" opacity="0.18"/>`;

	const svg =
		`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${WIDTH} ${HEIGHT}" width="${WIDTH}" height="${HEIGHT}" role="img" aria-hidden="true" preserveAspectRatio="xMidYMid slice">` +
		`<defs>` +
		`<linearGradient id="${gradientId}" x1="0" y1="0" x2="1" y2="1">` +
		`<stop offset="0" stop-color="${from}"/>` +
		`<stop offset="0.55" stop-color="${via}"/>` +
		`<stop offset="1" stop-color="${to}"/>` +
		`</linearGradient>` +
		`<filter id="${blurId}" x="-30%" y="-30%" width="160%" height="160%">` +
		`<feGaussianBlur stdDeviation="${n(18 + random() * 22)}"/>` +
		`</filter>` +
		`</defs>` +
		`<rect width="${WIDTH}" height="${HEIGHT}" fill="url(#${gradientId})"/>` +
		blobs.join('') +
		focal +
		streak +
		vignette +
		`</svg>`;

	return { svg, label: 'Abstract illustration' };
}
