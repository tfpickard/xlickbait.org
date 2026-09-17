<script lang="ts">
	import Thumb from './Thumb.svelte';
	import FactCheck from './FactCheck.svelte';
	import { resolve } from '$app/paths';
	import { headlineEntry } from '$lib/slug';
	import { absUrl } from '$lib/config';
	import { relativeTime } from '$lib/time';
	import type { HeadlineCard } from '$lib/server/db/queries';

	interface Props {
		item: HeadlineCard;
		now: string;
		/** Compact cards drop the fact check and the dek. */
		compact?: boolean;
		headingLevel?: 2 | 3;
	}

	let { item, now, compact = false, headingLevel = 3 }: Props = $props();
</script>

<article class="card" class:compact>
	<!-- eslint-disable-next-line svelte/no-navigation-without-resolve -- outbound link to arxiv.org; absUrl() builds it from the identifier so a malformed abs_url column cannot redirect a reader somewhere unexpected -->
	<a class="thumb-link" href={absUrl(item.arxivId)} tabindex="-1" aria-hidden="true">
		<Thumb id={item.id} arxivId={item.arxivId} hasImage={item.hasImage} />
	</a>

	<div class="body">
		<div class="meta">
			<a
				class="tag"
				class:tag--vintage={item.kind === 'vintage'}
				href={resolve('/c/[category]', { category: item.primaryCategory })}
			>
				{item.primaryCategory}
			</a>
			<time datetime={item.publishAt}>{relativeTime(item.publishAt, new Date(now))}</time>
		</div>

		<!--
			The headline links to the paper, because the joke only works if the link
			is real. The permalink is a separate, quieter affordance.
		-->
		<svelte:element this={headingLevel === 2 ? 'h2' : 'h3'} class="headline">
			<!-- eslint-disable-next-line svelte/no-navigation-without-resolve -- outbound link to arxiv.org; absUrl() builds it from the identifier so a malformed abs_url column cannot redirect a reader somewhere unexpected -->
			<a href={absUrl(item.arxivId)}>{item.headline}</a>
		</svelte:element>

		{#if !compact}
			<p class="dek">{item.dek}</p>
			<FactCheck actualPoint={item.actualPoint} anchor={item.anchor} />
			<a
				class="permalink"
				href={resolve('/h/[entry]', { entry: headlineEntry(item.id, item.headline) })}>Permalink</a
			>
		{/if}
	</div>
</article>

<style>
	.card {
		display: grid;
		gap: 12px;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: var(--radius);
		overflow: hidden;
		box-shadow: var(--shadow);
	}

	.thumb-link {
		display: block;
	}

	.body {
		display: grid;
		gap: 8px;
		padding: 0 14px 14px;
	}

	.meta {
		display: flex;
		align-items: center;
		gap: 10px;
		font-size: 0.72rem;
		color: var(--text-muted);
	}

	.headline {
		font-size: 1.12rem;
		font-weight: 800;
	}

	.compact .headline {
		font-size: 0.98rem;
	}

	.headline a {
		text-decoration: none;
	}

	.headline a:hover,
	.headline a:focus-visible {
		color: var(--accent);
	}

	.dek {
		color: var(--text-muted);
		font-size: 0.92rem;
	}

	.permalink {
		justify-self: start;
		font-size: 0.7rem;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--text-muted);
		text-decoration: none;
		font-weight: 700;
	}

	.permalink:hover {
		color: var(--accent);
	}
</style>
