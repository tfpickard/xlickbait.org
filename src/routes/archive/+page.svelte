<script lang="ts">
	import Chumbox from '$lib/components/Chumbox.svelte';
	import { SITE_NAME } from '$lib/config';
	import { resolve } from '$app/paths';
	import { formatDayLong, splitDayKey } from '$lib/time';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();
	const total = $derived(data.days.reduce((sum, d) => sum + d.count, 0));
</script>

<svelte:head>
	<title>Archive — {SITE_NAME}</title>
	<meta name="description" content="Every day we have published, with counts." />
	<meta property="og:title" content="Archive — {SITE_NAME}" />
	<meta property="og:image" content="/og-default.png" />
	<meta name="twitter:card" content="summary_large_image" />
</svelte:head>

<h1>Archive</h1>
<p class="sub">
	{total}
	{total === 1 ? 'story' : 'stories'} across {data.days.length}
	{data.days.length === 1 ? 'day' : 'days'}. Dates are UTC.
</p>

{#if data.categories.length > 0}
	<h2 class="section-heading">Sections</h2>
	<p class="categories">
		{#each data.categories as c (c.category)}
			<a class="tag" href={resolve('/c/[category]', { category: c.category })}
				>{c.category} ({c.count})</a
			>
		{/each}
	</p>
{/if}

<h2 class="section-heading">By date</h2>
{#if data.days.length === 0}
	<p class="empty">Nothing published yet.</p>
{:else}
	<ul>
		{#each data.days as d (d.day)}
			<li>
				<a href={resolve('/[yyyy=yyyy]/[mm=mm]/[dd=dd]', splitDayKey(d.day))}>
					<span class="date">{formatDayLong(d.day)}</span>
					<span class="count">{d.count}</span>
				</a>
			</li>
		{/each}
	</ul>
{/if}

<Chumbox items={data.chumbox} />

<style>
	h1 {
		margin-top: 32px;
		font-size: clamp(1.6rem, 4.5vw, 2.4rem);
		font-weight: 900;
	}

	.sub {
		color: var(--text-muted);
		font-size: 0.9rem;
	}

	.categories {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
	}

	ul {
		list-style: none;
		margin: 0;
		padding: 0;
		border-top: 1px solid var(--border);
	}

	li a {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
		gap: 16px;
		padding: 12px 4px;
		border-bottom: 1px solid var(--border);
		text-decoration: none;
	}

	li a:hover .date,
	li a:focus-visible .date {
		color: var(--accent);
	}

	.date {
		font-weight: 600;
	}

	.count {
		font-variant-numeric: tabular-nums;
		color: var(--text-muted);
		font-size: 0.85rem;
	}

	.empty {
		color: var(--text-muted);
	}
</style>
