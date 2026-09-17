import { error } from '@sveltejs/kit';
import type { PageServerLoad } from './$types';
import { listHeadlines, parseCursorParam } from '$lib/server/db/queries';
import { loadChumbox, setCache } from '$lib/server/page';
import { CACHE_WINDOWS, PAGE_SIZE } from '$lib/config';
import { TAGS } from '$lib/cache';

/**
 * arXiv categories look like `cs.LG`, `hep-ex`, `math.NT`. Validating the shape
 * here keeps arbitrary strings out of the query and out of the cache tag.
 */
const CATEGORY_PATTERN = /^[a-zA-Z-]+(\.[a-zA-Z-]+)?$/;

export const load: PageServerLoad = async (event) => {
	const category = event.params.category;
	if (!CATEGORY_PATTERN.test(category)) error(404, 'No such section');

	const cursor = parseCursorParam(event.url.searchParams.get('cursor'));
	if (cursor === 'invalid') error(400, 'That pagination cursor is not valid.');

	const page = await listHeadlines({ limit: PAGE_SIZE, cursor, category });
	const chumbox = await loadChumbox(
		event,
		page.items.map((i) => i.id),
		CACHE_WINDOWS.list.sMaxAge
	);
	setCache(event, { ...CACHE_WINDOWS.list, tags: [TAGS.list, TAGS.category(category)] });

	return { category, page, chumbox };
};
