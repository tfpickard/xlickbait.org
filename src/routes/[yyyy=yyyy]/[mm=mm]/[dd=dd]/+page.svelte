<script lang="ts">
	import Card from '$lib/components/Card.svelte';
	import Chumbox from '$lib/components/Chumbox.svelte';
	import { SITE_NAME } from '$lib/config';
	import { resolve } from '$app/paths';
	import { formatDayLong, splitDayKey } from '$lib/time';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();
	const pretty = $derived(formatDayLong(data.dayKey));
</script>

<svelte:head>
	<title>{pretty} — {SITE_NAME}</title>
	<meta name="description" content="Every headline published on {pretty}." />
	<meta property="og:title" content="{pretty} — {SITE_NAME}" />
	<meta property="og:image" content="/og-default.png" />
	<meta name="twitter:card" content="summary_large_image" />
</svelte:head>

<h1>{pretty}</h1>
<p class="sub">Everything we published that day, UTC.</p>

{#if data.page.items.length === 0}
	<p class="empty">Nothing was published on this date.</p>
{:else}
	<div class="grid">
		{#each data.page.items as item (item.id)}
			<Card {item} now={data.now} />
		{/each}
	</div>
{/if}

{#if data.page.nextCursor}
	<p class="more">
		<a
			href="{resolve(
				'/[yyyy=yyyy]/[mm=mm]/[dd=dd]',
				splitDayKey(data.dayKey)
			)}?cursor={encodeURIComponent(data.page.nextCursor)}">More from this day →</a
		>
	</p>
{/if}

<p class="back"><a href={resolve('/archive')}>← All dates</a></p>

<Chumbox items={data.chumbox} />

<style>
	h1 {
		margin-top: 32px;
		font-size: clamp(1.6rem, 4.5vw, 2.4rem);
		font-weight: 900;
	}

	.sub {
		color: var(--text-muted);
		margin-bottom: 24px;
		font-size: 0.9rem;
	}

	.grid {
		display: grid;
		gap: 20px;
		grid-template-columns: repeat(auto-fill, minmax(min(100%, 260px), 1fr));
	}

	.empty,
	.back {
		color: var(--text-muted);
		margin-top: 24px;
	}

	.more {
		margin-top: 28px;
	}
</style>
