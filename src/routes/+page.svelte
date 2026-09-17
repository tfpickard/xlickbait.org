<script lang="ts">
	import Hero from '$lib/components/Hero.svelte';
	import Card from '$lib/components/Card.svelte';
	import Chumbox from '$lib/components/Chumbox.svelte';
	import { SITE_NAME } from '$lib/config';
	import { resolve } from '$app/paths';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();
</script>

<svelte:head>
	<title>{SITE_NAME} — the preprint authority</title>
	<meta
		name="description"
		content="Sensational, technically true headlines about real arXiv preprints. Satire."
	/>
	<meta property="og:site_name" content={SITE_NAME} />
	<meta property="og:title" content="{SITE_NAME} — the preprint authority" />
	<meta property="og:type" content="website" />
	<meta property="og:image" content="/og-default.png" />
	<meta name="twitter:card" content="summary_large_image" />
</svelte:head>

<h1 class="visually-hidden">{SITE_NAME}</h1>

{#if data.paging}
	<h2 class="section-heading">More stories</h2>
	<div class="grid">
		{#each data.more.items as item (item.id)}
			<Card {item} now={data.now} />
		{/each}
	</div>
{:else}
	{#if data.hero}
		<Hero item={data.hero} now={data.now} />
	{/if}

	{#if data.breaking.length > 0}
		<h2 class="section-heading">Breaking</h2>
		<div class="grid">
			{#each data.breaking as item (item.id)}
				<Card {item} now={data.now} />
			{/each}
		</div>
	{/if}

	{#if data.vintage.length > 0}
		<h2 class="section-heading">From the ar&#x3c7;ive</h2>
		<div class="grid">
			{#each data.vintage as item (item.id)}
				<Card {item} now={data.now} />
			{/each}
		</div>
	{/if}

	{#if data.hero === null && data.breaking.length === 0 && data.vintage.length === 0}
		<p class="empty">No headlines have been published yet. The presses are warming up.</p>
	{/if}
{/if}

{#if data.more.nextCursor}
	<p class="more">
		<a href="{resolve('/')}?cursor={encodeURIComponent(data.more.nextCursor)}">More stories →</a>
	</p>
{/if}

<Chumbox items={data.chumbox} />

<style>
	.visually-hidden {
		position: absolute;
		width: 1px;
		height: 1px;
		overflow: hidden;
		clip-path: inset(50%);
		white-space: nowrap;
	}

	.grid {
		display: grid;
		gap: 20px;
		grid-template-columns: repeat(auto-fill, minmax(min(100%, 260px), 1fr));
	}

	.more {
		margin-top: 32px;
		text-align: center;
	}

	.more a {
		display: inline-block;
		padding: 12px 22px;
		border: 2px solid var(--text);
		border-radius: var(--radius);
		font-weight: 800;
		text-decoration: none;
		letter-spacing: 0.04em;
	}

	.more a:hover,
	.more a:focus-visible {
		background: var(--accent);
		border-color: var(--accent);
		color: var(--accent-ink);
	}

	.empty {
		margin-top: 48px;
		color: var(--text-muted);
	}
</style>
