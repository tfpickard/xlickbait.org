<script lang="ts">
	import { page } from '$app/state';
	import { SITE_NAME } from '$lib/config';
	import { resolve } from '$app/paths';

	const headline = $derived(
		page.status === 404
			? 'This Page Does Not Exist And Scientists Cannot Explain Why'
			: 'Something Has Gone Catastrophically Wrong (It Is Probably Fine)'
	);
</script>

<svelte:head>
	<title>{page.status} — {SITE_NAME}</title>
	<meta name="robots" content="noindex" />
</svelte:head>

<div class="error">
	<p class="kicker">Error {page.status}</p>
	<h1>{headline}</h1>
	<p class="dek">
		{#if page.status === 404}
			We looked everywhere. Experts say the page may never have been here at all. What we found
			instead was nothing.
		{:else}
			{page.error?.message ?? 'An unknown error occurred.'}
		{/if}
	</p>
	<p><a class="cta" href={resolve('/')}>Back to the front page →</a></p>
</div>

<style>
	.error {
		max-width: var(--measure);
		margin: 64px 0 80px;
		display: grid;
		gap: 14px;
	}

	.kicker {
		font-size: 0.7rem;
		font-weight: 800;
		letter-spacing: 0.16em;
		text-transform: uppercase;
		color: var(--accent);
	}

	h1 {
		font-size: clamp(1.8rem, 6vw, 3.2rem);
		font-weight: 900;
		letter-spacing: -0.03em;
	}

	.dek {
		font-size: 1.05rem;
		color: var(--text-muted);
	}

	.cta {
		font-weight: 800;
		color: var(--accent);
	}
</style>
