/**
 * Build the single static Open Graph image.
 *
 * Run with `npm run og:build`; the PNG is committed. Dynamic per-headline OG
 * images are a later task, so every page currently points at this one.
 *
 * sharp is a devDependency and never reaches a Netlify function -- it exists
 * solely so this script can rasterise the SVG below once.
 */
import { mkdir, writeFile } from 'node:fs/promises';
import sharp from 'sharp';

const WIDTH = 1200;
const HEIGHT = 630;

// A Greek chi, matching the masthead. The alt text and every other surface keep
// the ASCII spelling.
const WORDMARK = 'χLICKBAIT';

const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${WIDTH}" height="${HEIGHT}" viewBox="0 0 ${WIDTH} ${HEIGHT}">
	<defs>
		<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
			<stop offset="0" stop-color="#12002e"/>
			<stop offset="0.55" stop-color="#4a148c"/>
			<stop offset="1" stop-color="#d81324"/>
		</linearGradient>
		<filter id="soft" x="-30%" y="-30%" width="160%" height="160%">
			<feGaussianBlur stdDeviation="60"/>
		</filter>
	</defs>

	<rect width="${WIDTH}" height="${HEIGHT}" fill="url(#bg)"/>
	<ellipse cx="240" cy="140" rx="300" ry="220" fill="#00e5ff" opacity="0.30" filter="url(#soft)"/>
	<ellipse cx="980" cy="520" rx="320" ry="240" fill="#ff4081" opacity="0.32" filter="url(#soft)"/>
	<rect width="${WIDTH}" height="${HEIGHT}" fill="#000000" opacity="0.28"/>

	<text x="72" y="330" font-family="DejaVu Sans, FreeSans, sans-serif" font-size="132" font-weight="bold" fill="#ffffff" letter-spacing="-4">${WORDMARK}</text>
	<rect x="76" y="384" width="150" height="10" fill="#ffffff" opacity="0.95"/>
	<text x="76" y="452" font-family="DejaVu Sans, FreeSans, sans-serif" font-size="30" font-weight="bold" fill="#ffffff" opacity="0.92" letter-spacing="6">THE PREPRINT AUTHORITY</text>
	<text x="76" y="524" font-family="DejaVu Sans, FreeSans, sans-serif" font-size="27" fill="#ffffff" opacity="0.78">Technically true headlines about real arXiv preprints.</text>
	<text x="76" y="564" font-family="DejaVu Sans, FreeSans, sans-serif" font-size="27" fill="#ffffff" opacity="0.78">Every one of them misses the point. Satire.</text>
</svg>`;

await mkdir('static', { recursive: true });
await writeFile('static/og-default.svg', svg, 'utf8');

const png = await sharp(Buffer.from(svg)).png({ compressionLevel: 9 }).toBuffer();
await writeFile('static/og-default.png', png);

const meta = await sharp(png).metadata();
console.log(`wrote static/og-default.png (${meta.width}x${meta.height}, ${png.length} bytes)`);
