<script lang="ts">
	import Card from '$lib/components/Card.svelte';
	import Chumbox from '$lib/components/Chumbox.svelte';
	import { SITE_NAME } from '$lib/config';
	import { resolve } from '$app/paths';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();
</script>

<svelte:head>
	<title>{data.category} — {SITE_NAME}</title>
	<meta name="description" content="Headlines filed under {data.category}." />
	<meta property="og:title" content="{data.category} — {SITE_NAME}" />
	<meta property="og:image" content="/og-default.png" />
	<meta name="twitter:card" content="summary_large_image" />
</svelte:head>

<h1>{data.category}</h1>
<p class="sub">Including papers cross-listed into this section.</p>

{#if data.page.items.length === 0}
	<p class="empty">Nothing filed under this section yet.</p>
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
			href="{resolve('/c/[category]', { category: data.category })}?cursor={encodeURIComponent(
				data.page.nextCursor
			)}">More in {data.category} →</a
		>
	</p>
{/if}

<Chumbox items={data.chumbox} />

<style>
	h1 {
		margin-top: 32px;
		font-size: clamp(1.6rem, 4.5vw, 2.4rem);
		font-weight: 900;
		font-family: ui-monospace, 'SF Mono', Menlo, Consolas, monospace;
	}

	.sub {
		color: var(--text-muted);
		font-size: 0.9rem;
		margin-bottom: 24px;
	}

	.grid {
		display: grid;
		gap: 20px;
		grid-template-columns: repeat(auto-fill, minmax(min(100%, 260px), 1fr));
	}

	.empty {
		color: var(--text-muted);
	}

	.more {
		margin-top: 28px;
	}
</style>
