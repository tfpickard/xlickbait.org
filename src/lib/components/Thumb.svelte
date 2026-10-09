<script lang="ts">
	import { thumbnailFor } from '$lib/thumb';
	import { resolve } from '$app/paths';

	interface Props {
		/** Headline id, for the `/i/<id>` image URL. */
		id: number;
		/** Seeds the SVG fallback. */
		arxivId: string;
		/** Dimensions of the generated illustration, or null when there is none. */
		image: { width: number; height: number } | null;
		/** Hero thumbnails get a wider aspect ratio than grid cards. */
		wide?: boolean;
		/** The hero image is the page's LCP element; everything else waits. */
		priority?: boolean;
	}

	let { id, arxivId, image, wide = false, priority = false }: Props = $props();

	// Only paid for when it is actually going to be rendered. The SVG is a couple
	// of kilobytes of markup inlined into the page, so building one for every card
	// that has a real picture would be a wasted cost on the common path.
	const thumb = $derived(image ? null : thumbnailFor(arxivId));

	// The box takes the picture's own shape rather than the card's.
	//
	// A tabloid illustration carries the headline typeset across the top of the
	// frame, and `object-fit: cover` into a 16/10 box crops whatever does not fit
	// -- which is the headline. Letting the image state its own ratio means
	// nothing is ever cropped, and since every generated image is requested at the
	// same aspect, the grid stays even anyway.
	const ratio = $derived(image ? `${image.width} / ${image.height}` : null);
</script>

<div class="thumb" class:wide style={ratio ? `aspect-ratio: ${ratio}` : undefined}>
	{#if image}
		<!--
			`alt=""` on purpose. The link around this is already aria-hidden with
			tabindex -1, because the headline immediately below it points at the same
			place; announcing a decorative illustration of a headline that is about to
			be read out is noise. The image carries no information the text does not.
		-->
		<img
			src={resolve('/i/[id=id]', { id: String(id) })}
			alt=""
			width={image.width}
			height={image.height}
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
