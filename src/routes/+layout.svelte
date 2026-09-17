<script lang="ts">
	import '../app.css';
	import favicon from '$lib/assets/favicon.svg';
	import Masthead from '$lib/components/Masthead.svelte';
	import Footer from '$lib/components/Footer.svelte';

	let { children } = $props();
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
</svelte:head>

<a class="skip-link" href="#main">Skip to content</a>
<Masthead />
<main id="main" class="shell">
	{@render children()}
</main>
<Footer />
