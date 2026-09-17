<footer class="footer">
	<div class="shell">
		<h2>About this site</h2>
		<!--
			The deadpan is deliberate. The site never tells a reader it is satire; the
			joke only works if it never winks. The admission lives in README.md and
			CLAUDE.md instead.

			Two things below are NOT part of that admission and must not be trimmed as
			"more confession". The takedown offer in the second paragraph is the
			release valve for running real, named researchers under sensational
			headlines. The arXiv sentences further down are required verbatim -- see
			the comment above them.

			The first paragraph is the truth gate (generator/truth.py) restated as an
			editorial standard. Every sentence here is literally true.
		-->
		<p>
			xlickbait covers new and archival preprints. Every headline is built on a detail quoted
			verbatim from the paper's own title or abstract; that quote, and a plain summary of what the
			paper actually found, sit under the "Fact check" on each story.
		</p>
		<p>
			Headlines are written by a language model and are not reviewed by the authors. Every link goes
			to the paper itself. Nothing here is a claim about any author's work, competence, or conduct.
			Authors who would rather not be featured can say so and the headline comes down.
		</p>
		<p>
			This site is <strong>not affiliated with arXiv</strong> and is not endorsed or supported by
			arXiv in any way. It shows only descriptive metadata -- titles, abstracts, authors, categories
			and dates -- which arXiv makes available under the
			<a href="https://creativecommons.org/publicdomain/zero/1.0/" rel="noopener">CC0 1.0</a>
			public domain dedication. No full text or PDFs are fetched, stored, or served.
		</p>
		<!--
			Both sentences are required. arXiv's API landing page asks products to
			acknowledge data usage with the first; the brand guidelines specify the
			disclaimer that follows it for products that use the API. The disclaimer
			is doing real work here, given the section heading "FROM THE ARXIVE".
		-->
		<p class="thanks">
			Thank you to arXiv for use of its open access interoperability. This service was not reviewed
			or approved by, nor does it necessarily express or reflect the policies or opinions of, arXiv.
		</p>
		<p class="colophon">
			No analytics, no cookies, no trackers. All artwork is generated from the paper identifier.
		</p>
	</div>
</footer>

<style>
	.footer {
		margin-top: 72px;
		border-top: 1px solid var(--border);
		background: var(--surface-alt);
		padding-block: 28px 40px;
		font-size: 0.85rem;
		color: var(--text-muted);
	}

	h2 {
		font-size: 0.7rem;
		font-weight: 800;
		letter-spacing: 0.14em;
		text-transform: uppercase;
		margin-bottom: 12px;
		color: var(--text);
	}

	p {
		max-width: var(--measure);
		margin-bottom: 10px;
	}

	strong {
		color: var(--text);
	}

	.thanks {
		font-style: italic;
	}

	.colophon {
		margin-top: 16px;
		font-size: 0.78rem;
	}
</style>
