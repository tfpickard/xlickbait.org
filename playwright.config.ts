import { existsSync } from 'node:fs';
import { defineConfig, devices } from '@playwright/test';

/**
 * Smoke tests run against `netlify dev`, which is what a developer actually runs
 * locally. It is a Vite proxy rather than the built SSR function, so it proves
 * the routes and markup are right -- not that the deployed function behaves
 * identically. Assertions that need the real adapter output live in the Vitest
 * suite, which invokes the built handler directly.
 *
 * Point PLAYWRIGHT_BASE_URL at an already-running server to skip the startup.
 */
const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? 'http://localhost:8888';

/**
 * Some CI images ship a Chromium build that does not match the one this
 * Playwright version would download, and have no network budget to fetch
 * another. CHROMIUM_PATH (or a matching pre-installed binary) is used when
 * present; otherwise Playwright uses its own, which is what happens on a normal
 * development machine.
 */
const preinstalledChromium = [
	process.env.CHROMIUM_PATH,
	'/opt/pw-browsers/chromium-1194/chrome-linux/chrome'
].find((candidate) => candidate && existsSync(candidate));

export default defineConfig({
	testMatch: '**/*.e2e.{ts,js}',
	use: {
		...devices['Desktop Chrome'],
		baseURL,
		...(preinstalledChromium ? { launchOptions: { executablePath: preinstalledChromium } } : {})
	},
	...(process.env.PLAYWRIGHT_BASE_URL
		? {}
		: {
				webServer: {
					// Ports come from [dev] in netlify.toml. BROWSER=none stops the CLI
					// from trying to open a browser in a headless environment.
					command: 'BROWSER=none npx netlify dev --offline',
					port: 8888,
					reuseExistingServer: true,
					timeout: 180_000
				}
			})
});
