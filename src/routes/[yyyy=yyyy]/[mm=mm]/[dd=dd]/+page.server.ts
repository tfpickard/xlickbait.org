import { error } from '@sveltejs/kit';
import type { PageServerLoad } from './$types';
import { listHeadlines, parseCursorParam } from '$lib/server/db/queries';
import { loadChumbox, setTimeSensitiveCache } from '$lib/server/page';
import { isValidUtcDate, utcDayRange } from '$lib/time';
import { CACHE_WINDOWS, PAGE_SIZE } from '$lib/config';
import { TAGS } from '$lib/cache';

export const load: PageServerLoad = async (event) => {
	const year = Number(event.params.yyyy);
	const month = Number(event.params.mm);
	const day = Number(event.params.dd);

	// The matchers guarantee the shape (four digits, 01-12, 01-31) but not that
	// the date exists -- 2026/02/31 passes every one of them.
	if (!isValidUtcDate(year, month, day)) error(404, 'No such date');

	const cursor = parseCursorParam(event.url.searchParams.get('cursor'));
	if (cursor === 'invalid') error(400, 'That pagination cursor is not valid.');

	const range = utcDayRange(year, month, day);
	const page = await listHeadlines({ limit: PAGE_SIZE, cursor, day: range });

	const dayKey = `${event.params.yyyy}-${event.params.mm}-${event.params.dd}`;
	const chumbox = await loadChumbox(
		event,
		page.items.map((i) => i.id),
		CACHE_WINDOWS.list.sMaxAge
	);
	await setTimeSensitiveCache(event, CACHE_WINDOWS.list, [TAGS.list, TAGS.day(dayKey)]);

	return { dayKey, page, chumbox };
};
