import { error } from '@sveltejs/kit';
import type { PageServerLoad } from './$types';
import {
	listHeadlines,
	parseCursorParam,
	type HeadlineCard,
	type ListResult
} from '$lib/server/db/queries';
import { loadChumbox, setTimeSensitiveCache } from '$lib/server/page';
import { BREAKING_COUNT, CACHE_WINDOWS, PAGE_SIZE, VINTAGE_COUNT } from '$lib/config';
import { TAGS } from '$lib/cache';

export const load: PageServerLoad = async (event) => {
	const cursor = parseCursorParam(event.url.searchParams.get('cursor'));
	if (cursor === 'invalid') {
		// A malformed cursor is a client error, not a silent reset to page one:
		// quietly serving the first page is how a paginating client loops forever.
		error(400, 'That pagination cursor is not valid.');
	}

	// Paginated views drop the hero/vintage split and become a plain list --
	// "More stories" continues one ordering rather than restating the front page.
	const paging = cursor !== null;

	let hero: HeadlineCard | null = null;
	let breaking: HeadlineCard[] = [];
	let vintage: HeadlineCard[] = [];
	let more: ListResult;

	if (paging) {
		more = await listHeadlines({ limit: PAGE_SIZE, cursor });
	} else {
		const fresh = await listHeadlines({ kind: 'fresh', limit: BREAKING_COUNT + 1 });
		const vintageResult = await listHeadlines({ kind: 'vintage', limit: VINTAGE_COUNT });

		hero = fresh.items[0] ?? null;
		breaking = fresh.items.slice(1);
		vintage = vintageResult.items;

		// "More stories" continues the COMBINED ordering, not the fresh-only one.
		// Paging from the fresh cursor would silently skip every vintage item newer
		// than the last fresh headline on the page.
		more = await listHeadlines({ limit: PAGE_SIZE });
	}

	// Exclude only what is actually RENDERED. `more` is fetched on the front page
	// purely for its nextCursor -- its items are not shown unless we are paging --
	// and excluding them too would empty the chumbox pool on a small corpus.
	const onPage = paging
		? more.items.map((i) => i.id)
		: [...(hero ? [hero.id] : []), ...breaking.map((i) => i.id), ...vintage.map((i) => i.id)];
	const chumbox = await loadChumbox(event, onPage, CACHE_WINDOWS.list.sMaxAge);

	await setTimeSensitiveCache(event, CACHE_WINDOWS.list, [TAGS.list]);
	return { paging, hero, breaking, vintage, more, chumbox };
};
