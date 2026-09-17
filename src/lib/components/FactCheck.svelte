<script lang="ts">
	interface Props {
		actualPoint: string;
		anchor: string;
	}

	let { actualPoint, anchor }: Props = $props();
</script>

<!--
	A native <details>. No JavaScript, so it works with the bundle blocked, during
	hydration, and in a reader mode.
-->
<details class="fact-check">
	<summary>Fact check</summary>
	<div class="body">
		<p>{actualPoint}</p>
		<p class="detail-label">The detail we ran with:</p>
		<blockquote>{anchor}</blockquote>
	</div>
</details>

<style>
	.fact-check {
		margin-top: 12px;
		border-top: 1px solid var(--border);
		padding-top: 10px;
		font-size: 0.86rem;
	}

	summary {
		cursor: pointer;
		font-weight: 700;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		font-size: 0.68rem;
		color: var(--text-muted);
		list-style: none;
	}

	summary::-webkit-details-marker {
		display: none;
	}

	summary::before {
		content: '▸ ';
		display: inline-block;
		transition: transform 0.12s ease;
	}

	details[open] summary::before {
		content: '▾ ';
	}

	.body {
		margin-top: 8px;
		display: grid;
		gap: 6px;
		color: var(--text-muted);
	}

	.detail-label {
		font-weight: 700;
		color: var(--text);
	}

	blockquote {
		margin: 0;
		padding-left: 12px;
		border-left: 3px solid var(--accent);
		font-style: italic;
	}
</style>
