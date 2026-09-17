<script lang="ts">
	import { thumbnailFor } from '$lib/thumb';
	import { resolve } from '$app/paths';

	interface Props {
		/** Headline id, for the `/i/<id>` image URL. */
		id: number;
		/** Seeds the SVG fallback. */
		arxivId: string;
		/** Whether the generator managed to produce an illustration for this one. */
		hasImage: boolean;
		/** Hero thumbnails get a wider aspect ratio than grid cards. */
		wide?: boolean;
		/** The hero image is the page's LCP element; everything else waits. */
		priority?: boolean;
	}

	let { id, arxivId, hasImage, wide = false, priority = false }: Props = $props();

	// Only paid for when it is actually going to be rendered. The SVG is a couple
	// of kilobytes of markup inlined into the page, so building one for every card
	// that has a real picture would be a wasted cost on the common path.
	const thumb = $derived(hasImage ? null : thumbnailFor(arxivId));
</script>

<div class="thumb" class:wide>
	{#if hasImage}
		<!--
			`alt=""` on purpose. The link around this is already aria-hidden with
			tabindex -1, because the headline immediately below it points at the same
			place; announcing a decorative illustration of a headline that is about to
			be read out is noise. The image carries no information the text does not.
		-->
		<img
			src={resolve('/i/[id=id]', { id: String(id) })}
			alt=""
			loading={priority ? 'eager' : 'lazy'}
			fetchpriority={priority ? 'high' : 'auto'}
			decoding="async"
		/>
	{:else}
		<!--
			Safe to inline: the SVG is generated from a numeric seed, and no string from
			the database is ever interpolated into it.
		-->
		<!-- eslint-disable-next-line svelte/no-at-html-tags -->
		{@html thumb!.svg}
	{/if}
</div>

<style>
	.thumb {
		position: relative;
		aspect-ratio: 16 / 10;
		overflow: hidden;
		border-radius: var(--radius);
		background: var(--surface-alt);
	}

	.thumb.wide {
		aspect-ratio: 16 / 9;
	}

	.thumb :global(svg),
	.thumb img {
		display: block;
		width: 100%;
		height: 100%;
		object-fit: cover;
	}
</style>
