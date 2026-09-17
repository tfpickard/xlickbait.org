import { expect, test } from '@playwright/test';

/**
 * A smoke test, deliberately narrow: does every route render, does every
 * headline point at a real arXiv paper, and does the page pull anything from
 * off-site?
 *
 * The last one is a standing requirement rather than a nicety. Artwork is either
 * generated from the paper identifier or served from this origin at `/i/<id>`,
 * so a single external image request would mean something is reaching the
 * network that should not be. There is no hotlinking and no stock photography.
 */

const ARXIV_ABS = /^https:\/\/arxiv\.org\/abs\/\d{4}\.\d{4,5}$/;

/** Fails the test if the page requests anything from another origin. */
async function forbidExternalRequests(page: import('@playwright/test').Page, baseURL: string) {
	const offenders: string[] = [];
	page.on('request', (request) => {
		const url = request.url();
		if (!url.startsWith(baseURL) && !url.startsWith('data:') && !url.startsWith('blob:')) {
			offenders.push(`${request.resourceType()} ${url}`);
		}
	});
	return () => offenders;
}

test.describe('xlickbait smoke', () => {
	test('front page renders and every headline links to a real paper', async ({ page, baseURL }) => {
		const offenders = await forbidExternalRequests(page, baseURL as string);
		await page.goto('/');

		await expect(page.locator('header .wordmark')).toHaveAttribute('aria-label', /xlickbait/);

		const links = page.locator('a[href^="https://arxiv.org/"]');
		const count = await links.count();
		expect(count).toBeGreaterThan(5);

		for (let i = 0; i < count; i++) {
			const href = await links.nth(i).getAttribute('href');
			expect(href, `link ${i} is not a canonical abs URL`).toMatch(ARXIV_ABS);
		}

		// Artwork is either an inline SVG or an <img> served from this origin at
		// `/i/<id>`. This used to assert there were no <img> elements at all, which
		// was a proxy for the real rule -- nothing comes from off-site -- and stopped
		// being true when headlines gained illustrations. The rule itself has not
		// moved, so assert it directly instead.
		const images = page.locator('img');
		const imageCount = await images.count();
		const sources: string[] = [];
		for (let i = 0; i < imageCount; i++) {
			const src = new URL((await images.nth(i).getAttribute('src')) ?? '', page.url());
			expect(src.origin, 'an image is loaded from another origin').toBe(
				new URL(baseURL as string).origin
			);
			expect(src.pathname, 'an image is not a headline illustration').toMatch(/^\/i\/\d+$/);
			sources.push(src.href);
		}

		// Whatever the mix, every card has artwork of one kind or the other.
		const svgCount = await page.locator('.thumb svg').count();
		expect(imageCount + svgCount).toBeGreaterThan(5);

		// The hero image is eager, so the browser really has decoded it by now. A
		// naturalWidth of 0 is how a 404 or a broken bytea round trip presents.
		if (imageCount > 0) {
			const hero = page.locator('img[loading="eager"]').first();
			await expect
				.poll(() => hero.evaluate((el: HTMLImageElement) => el.naturalWidth))
				.toBeGreaterThan(0);
		}

		// Check the rest by fetching them rather than by waiting for the viewport:
		// the others are `loading="lazy"` and a headless page never scrolls to them,
		// so asserting on their naturalWidth would assert on lazy loading instead of
		// on the route.
		expect(offenders()).toEqual([]);
		for (const src of sources) {
			const response = await page.request.get(src);
			expect(response.status(), `${src} did not serve`).toBe(200);
			expect(response.headers()['content-type']).toBe('image/webp');
			expect((await response.body()).byteLength).toBeGreaterThan(0);
		}
	});

	test('the fact check works without JavaScript', async ({ browser, baseURL }) => {
		// The reveal is a native <details>. If it ever needed JS, this would fail.
		const context = await browser.newContext({ javaScriptEnabled: false });
		const page = await context.newPage();
		await page.goto(`${baseURL}/`);

		const details = page.locator('details.fact-check').first();
		await expect(details).toBeVisible();
		await expect(details.locator('summary')).toHaveText('Fact check');
		await details.locator('summary').click();
		await expect(details).toHaveAttribute('open', '');
		await expect(details.locator('blockquote')).toBeVisible();
		await context.close();
	});

	test('a permalink renders and canonicalises a wrong slug', async ({ page }) => {
		await page.goto('/');
		const permalink = await page.locator('a[href^="/h/"]').first().getAttribute('href');
		expect(permalink).toBeTruthy();

		await page.goto(permalink as string);
		await expect(page.locator('h1')).toBeVisible();
		await expect(page.locator('details.fact-check')).toBeVisible();

		// A wrong slug must land on the canonical URL, not 404.
		const id = (permalink as string).replace('/h/', '').split('-')[0];
		await page.goto(`/h/${id}-a-completely-wrong-slug`);
		expect(new URL(page.url()).pathname).toBe(permalink);
	});

	test('a day page renders', async ({ page }) => {
		await page.goto('/archive');
		await expect(page.locator('h1')).toHaveText('Archive');

		const firstDay = page.locator('a[href^="/20"]').first();
		await expect(firstDay).toBeVisible();
		await firstDay.click();
		await expect(page.locator('h1')).toBeVisible();
		await expect(page).toHaveURL(/\/\d{4}\/\d{2}\/\d{2}$/);
	});

	test('the feed is served as Atom', async ({ request }) => {
		const response = await request.get('/feed.xml');
		expect(response.status()).toBe(200);
		expect(response.headers()['content-type']).toContain('application/atom+xml');

		const body = await response.text();
		expect(body).toContain('<feed xmlns="http://www.w3.org/2005/Atom">');
		expect(body).toContain('<entry>');
		for (const match of body.matchAll(/rel="related" type="text\/html" href="([^"]+)"/g)) {
			expect(match[1]).toMatch(ARXIV_ABS);
		}
	});

	test('a missing page returns a styled 404', async ({ page }) => {
		const response = await page.goto('/definitely-not-a-page');
		expect(response?.status()).toBe(404);
		await expect(page.locator('h1')).toContainText('Does Not Exist');
		// Chrome is still present on an error page.
		await expect(page.locator('header .wordmark')).toBeVisible();
	});

	test('renders at 360px without horizontal overflow', async ({ page }) => {
		await page.setViewportSize({ width: 360, height: 780 });
		await page.goto('/');
		const overflow = await page.evaluate(
			() => document.documentElement.scrollWidth - document.documentElement.clientWidth
		);
		expect(overflow).toBeLessThanOrEqual(0);
	});
});
