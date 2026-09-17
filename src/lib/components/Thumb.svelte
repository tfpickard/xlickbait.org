<script lang="ts">
	import { thumbnailFor } from '$lib/thumb';

	interface Props {
		arxivId: string;
		/** Hero thumbnails get a wider aspect ratio than grid cards. */
		wide?: boolean;
	}

	let { arxivId, wide = false }: Props = $props();

	// Deterministic: the same id always produces the same markup, which matters
	// because this is inlined into CDN-cached HTML.
	const thumb = $derived(thumbnailFor(arxivId));
</script>

<div class="thumb" class:wide>
	<!--
		Safe to inline: the SVG is generated from a numeric seed, and no string from
		the database is ever interpolated into it.
	-->
	<!-- eslint-disable-next-line svelte/no-at-html-tags -->
	{@html thumb.svg}
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

	.thumb :global(svg) {
		width: 100%;
		height: 100%;
		object-fit: cover;
	}
</style>
