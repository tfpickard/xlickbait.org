import type { LayoutServerLoad } from './$types';

/**
 * One timestamp per request, shared by every relative time on the page.
 *
 * Rendering "3 hours ago" from `new Date()` inside each component would mean a
 * page could disagree with itself, and would make component output depend on the
 * clock rather than on its inputs. Passing it down keeps rendering a pure
 * function of data, which is what makes the snapshot tests meaningful.
 */
export const load: LayoutServerLoad = () => {
	return { now: new Date().toISOString() };
};
