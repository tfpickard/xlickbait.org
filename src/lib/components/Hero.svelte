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
	}

	let { item, now }: Props = $props();
</script>

<article class="hero">
	<!-- eslint-disable-next-line svelte/no-navigation-without-resolve -- outbound link to arxiv.org; absUrl() builds it from the identifier so a malformed abs_url column cannot redirect a reader somewhere unexpected -->
	<a class="thumb-link" href={absUrl(item.arxivId)} tabindex="-1" aria-hidden="true">
		<Thumb id={item.id} arxivId={item.arxivId} image={item.image} wide priority />
	</a>

	<div class="body">
		<div class="meta">
			<span class="tag tag--breaking">Breaking</span>
			<a class="tag" href={resolve('/c/[category]', { category: item.primaryCategory })}
				>{item.primaryCategory}</a
			>
			<time datetime={item.publishAt}>{relativeTime(item.publishAt, new Date(now))}</time>
		</div>

		<!-- eslint-disable-next-line svelte/no-navigation-without-resolve -- outbound link to arxiv.org; absUrl() builds it from the identifier so a malformed abs_url column cannot redirect a reader somewhere unexpected -->
		<h2 class="headline"><a href={absUrl(item.arxivId)}>{item.headline}</a></h2>
		<p class="dek">{item.dek}</p>
		<FactCheck actualPoint={item.actualPoint} anchor={item.anchor} />
		<a
			class="permalink"
			href={resolve('/h/[entry]', { entry: headlineEntry(item.id, item.headline) })}>Permalink</a
		>
	</div>
</article>

<style>
	.hero {
		display: grid;
		gap: 16px;
		margin-top: 24px;
	}

	.body {
		display: grid;
		gap: 10px;
	}

	.meta {
		display: flex;
		align-items: center;
		gap: 10px;
		flex-wrap: wrap;
		font-size: 0.75rem;
		color: var(--text-muted);
	}

	.headline {
		font-size: clamp(1.75rem, 5vw, 3rem);
		font-weight: 900;
		letter-spacing: -0.03em;
	}

	.headline a {
		text-decoration: none;
	}

	.headline a:hover,
	.headline a:focus-visible {
		color: var(--accent);
	}

	.dek {
		font-size: clamp(1rem, 2.2vw, 1.2rem);
		color: var(--text-muted);
		max-width: var(--measure);
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

	@media (min-width: 880px) {
		.hero {
			grid-template-columns: 1.3fr 1fr;
			gap: 28px;
			align-items: center;
		}
	}
</style>
