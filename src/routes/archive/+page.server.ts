import type { PageServerLoad } from './$types';
import { listArchiveDays, listCategories } from '$lib/server/db/queries';
import { loadChumbox, setTimeSensitiveCache } from '$lib/server/page';
import { CACHE_WINDOWS } from '$lib/config';
import { TAGS } from '$lib/cache';

export const load: PageServerLoad = async (event) => {
	const [days, categories] = await Promise.all([listArchiveDays(), listCategories()]);
	const chumbox = await loadChumbox(event, [], CACHE_WINDOWS.archive.sMaxAge);
	await setTimeSensitiveCache(event, CACHE_WINDOWS.archive, [TAGS.archive]);
	return { days, categories, chumbox };
};
