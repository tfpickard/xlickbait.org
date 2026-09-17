<script lang="ts">
	import Thumb from '$lib/components/Thumb.svelte';
	import FactCheck from '$lib/components/FactCheck.svelte';
	import Chumbox from '$lib/components/Chumbox.svelte';
	import { absUrl, SITE_NAME } from '$lib/config';
	import { resolve } from '$app/paths';
	import { relativeTime, splitDayKey, utcDayKey } from '$lib/time';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();
	const item = $derived(data.item);
</script>

<svelte:head>
	<title>{item.headline} — {SITE_NAME}</title>
	<meta name="description" content={item.dek} />
	<meta property="og:site_name" content={SITE_NAME} />
	<meta property="og:title" content={item.headline} />
	<meta property="og:description" content={item.dek} />
	<meta property="og:type" content="article" />
	<meta property="og:image" content={data.ogImage} />
	<meta property="article:published_time" content={item.publishAt} />
	<meta name="twitter:card" content="summary_large_image" />
	<meta name="twitter:title" content={item.headline} />
	<meta name="twitter:description" content={item.dek} />
	<meta name="twitter:image" content={data.ogImage} />
</svelte:head>

<article class="story">
	<div class="meta">
		<a
			class="tag"
			class:tag--vintage={item.kind === 'vintage'}
			href={resolve('/c/[category]', { category: item.primaryCategory })}
		>
			{item.primaryCategory}
		</a>
		<time datetime={item.publishAt}>{relativeTime(item.publishAt, new Date(data.now))}</time>
		<a
			class="day"
			href={resolve('/[yyyy=yyyy]/[mm=mm]/[dd=dd]', splitDayKey(utcDayKey(item.publishAt)))}
		>
			{utcDayKey(item.publishAt)}
		</a>
	</div>

	<h1>{item.headline}</h1>
	<p class="dek">{item.dek}</p>

	<!-- eslint-disable-next-line svelte/no-navigation-without-resolve -- outbound link to arxiv.org; absUrl() builds it from the identifier so a malformed abs_url column cannot redirect a reader somewhere unexpected -->
	<a class="thumb-link" href={absUrl(item.arxivId)} tabindex="-1" aria-hidden="true">
		<Thumb id={item.id} arxivId={item.arxivId} hasImage={item.hasImage} wide priority />
	</a>

	<FactCheck actualPoint={item.actualPoint} anchor={item.anchor} />

	<section class="source">
		<h2>The paper</h2>
		<p class="title">{item.title}</p>
		<p class="categories">
			{#each item.categories as category (category)}
				<a class="tag" href={resolve('/c/[category]', { category })}>{category}</a>
			{/each}
		</p>
		<!-- eslint-disable-next-line svelte/no-navigation-without-resolve -- outbound link to arxiv.org; absUrl() builds it from the identifier so a malformed abs_url column cannot redirect a reader somewhere unexpected -->
		<p><a class="cta" href={absUrl(item.arxivId)}>Read the actual preprint →</a></p>
	</section>
</article>

<Chumbox items={data.chumbox} />

<style>
	.story {
		max-width: var(--measure);
		margin-top: 28px;
		display: grid;
		gap: 14px;
	}

	.meta {
		display: flex;
		align-items: center;
		gap: 10px;
		flex-wrap: wrap;
		font-size: 0.75rem;
		color: var(--text-muted);
	}

	.day {
		color: inherit;
	}

	h1 {
		font-size: clamp(1.8rem, 5.5vw, 3rem);
		font-weight: 900;
		letter-spacing: -0.03em;
	}

	.dek {
		font-size: 1.1rem;
		color: var(--text-muted);
	}

	.source {
		margin-top: 12px;
		padding: 16px;
		border: 1px solid var(--border);
		border-radius: var(--radius);
		background: var(--surface-alt);
	}

	.source h2 {
		font-size: 0.68rem;
		font-weight: 800;
		letter-spacing: 0.14em;
		text-transform: uppercase;
		color: var(--text-muted);
		margin-bottom: 8px;
	}

	.title {
		font-weight: 700;
		margin-bottom: 10px;
	}

	.categories {
		display: flex;
		gap: 6px;
		flex-wrap: wrap;
		margin-bottom: 12px;
	}

	.cta {
		font-weight: 800;
		color: var(--accent);
	}
</style>
