<script lang="ts">
	import { absUrl } from '$lib/config';
	import Thumb from './Thumb.svelte';
	import type { HeadlineCard } from '$lib/server/db/queries';

	interface Props {
		items: HeadlineCard[];
	}

	let { items }: Props = $props();
</script>

{#if items.length > 0}
	<aside class="chumbox" aria-labelledby="chumbox-heading">
		<h2 id="chumbox-heading" class="section-heading">Around the Preprint Web</h2>
		<ul>
			{#each items as item (item.id)}
				<li>
					<!-- eslint-disable-next-line svelte/no-navigation-without-resolve -- outbound link to arxiv.org; absUrl() builds it from the identifier so a malformed abs_url column cannot redirect a reader somewhere unexpected -->
					<a href={absUrl(item.arxivId)}>
						<Thumb arxivId={item.arxivId} />
						<span class="headline">{item.headline}</span>
						<span class="source">{item.primaryCategory}</span>
					</a>
				</li>
			{/each}
		</ul>
	</aside>
{/if}

<style>
	.chumbox {
		margin-top: 56px;
	}

	ul {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		gap: 14px;
		grid-template-columns: repeat(2, minmax(0, 1fr));
	}

	@media (min-width: 620px) {
		ul {
			grid-template-columns: repeat(3, minmax(0, 1fr));
		}
	}

	li a {
		display: grid;
		gap: 6px;
		text-decoration: none;
		color: inherit;
	}

	.headline {
		font-size: 0.84rem;
		font-weight: 700;
		line-height: 1.3;
	}

	li a:hover .headline,
	li a:focus-visible .headline {
		color: var(--accent);
	}

	.source {
		font-size: 0.66rem;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		color: var(--text-muted);
	}
</style>
