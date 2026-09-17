<script lang="ts">
	import { SITE_TAGLINE, SITE_WORDMARK } from '$lib/config';
	import { resolve } from '$app/paths';
</script>

<header class="masthead">
	<div class="shell inner">
		<!--
			The wordmark uses a Greek chi, so it reads "klickbait" -- the same joke as
			the X in arXiv. The aria-label keeps the ASCII name for screen readers,
			and every other surface (title, OG tags, feed) stays ASCII too, so search
			and copy-paste are unaffected.
		-->
		<a class="wordmark" href={resolve('/')} aria-label="xlickbait, home">
			<span aria-hidden="true">{SITE_WORDMARK}</span>
		</a>
		<p class="tagline">{SITE_TAGLINE}</p>
		<nav aria-label="Sections">
			<a href={resolve('/archive')}>Archive</a>
			<a href={resolve('/feed.xml')}>Feed</a>
		</nav>
	</div>
</header>

<style>
	.masthead {
		border-bottom: 3px solid var(--text);
		background: var(--surface);
		position: sticky;
		top: 0;
		z-index: 10;
	}

	.inner {
		display: grid;
		grid-template-columns: auto 1fr;
		grid-template-areas: 'wordmark nav' 'tagline tagline';
		align-items: center;
		gap: 4px 16px;
		padding-block: 10px;
	}

	.wordmark {
		grid-area: wordmark;
		font-size: clamp(1.4rem, 5.5vw, 2rem);
		font-weight: 900;
		letter-spacing: -0.04em;
		text-decoration: none;
		color: var(--text);
	}

	.tagline {
		grid-area: tagline;
		font-size: 0.6rem;
		font-weight: 800;
		letter-spacing: 0.22em;
		color: var(--text-muted);
	}

	nav {
		grid-area: nav;
		justify-self: end;
		display: flex;
		gap: 16px;
		font-size: 0.72rem;
		font-weight: 800;
		letter-spacing: 0.1em;
		text-transform: uppercase;
	}

	nav a {
		text-decoration: none;
		color: var(--text-muted);
	}

	nav a:hover,
	nav a:focus-visible {
		color: var(--accent);
	}
</style>
