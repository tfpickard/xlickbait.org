# xlickbait.org

A straight-faced tabloid front page for arXiv preprints. Every headline is
technically true, seizes on some peripheral detail, and completely misses the
point of the paper it links to. It is satire, and **the site never says so** --
the deadpan is deliberate, and the footer plays it straight. The admission
lives here, in `README.md`, and in a comment in `src/lib/components/Footer.svelte`
that records which footer sentences are load-bearing and must not be trimmed.

The engineering constraint underneath the joke: **content must appear without a
rebuild**. A Python generator (Phase 2) runs on cron on a personal machine and
writes headlines straight into Neon Postgres. The site reads, renders per
request, and is held at Netlify's CDN behind a short TTL. There are no build
hooks and nothing DB-backed is prerendered.

## Commands

| Command                       | What it does                                     |
| ----------------------------- | ------------------------------------------------ |
| `npm run dev`                 | Vite dev server on :5173                         |
| `npx netlify dev --offline`   | Netlify proxy on :8888 (what to develop against) |
| `npx netlify serve --offline` | Builds, then serves the **real** SSR function    |
| `npm run build`               | Production build via `@sveltejs/adapter-netlify` |
| `npm run check`               | `svelte-kit sync` + `svelte-check`               |
| `npm run lint`                | `prettier --check` + `eslint`                    |
| `npm run format`              | Rewrite with prettier                            |
| `npm run test`                | Vitest (unit + DB integration)                   |
| `npm run test:built`          | Build, then assert headers on the built function |
| `npm run test:e2e`            | Playwright smoke against `netlify dev`           |
| `npm run db:generate`         | `drizzle-kit generate` from `schema.ts`          |
| `npm run db:check`            | `drizzle-kit check` — see Migrations             |
| `npm run db:migrate`          | Apply migrations to **dev**                      |
| `npm run db:seed`             | Load fixtures into dev (idempotent)              |
| `npm run db:reset-dev`        | Truncate dev and reseed                          |
| `npm run og:build`            | Regenerate the static OG image                   |

### Generator (Python)

| Command                                 | What it does                                                          |
| --------------------------------------- | --------------------------------------------------------------------- |
| `python -m generator run`               | Pick papers, write headlines, publish, purge                          |
| `python -m generator run --dry-run`     | Print what it would insert; writes **nothing at all**                 |
| `python -m generator hide <id>`         | Kill switch: hide one headline (there is no web admin); purges `site` |
| `bin/run.sh [args]`                     | Cron wrapper; loads env from outside the repo                         |
| `pytest`                                | The generator suite (arXiv and Anthropic mocked)                      |
| `ruff check . && ruff format --check .` | Lint                                                                  |
| `shellcheck bin/*.sh`                   | Shell lint                                                            |

`run` takes `--fresh N` (clamped 2-5), `--vintage M`, and `--stagger HOURS` to
spread `publish_at` randomly across the next N hours. `pytest` picks up extra
suites when `XLICKBAIT_TEST_DB_URL` (a throwaway Postgres with the migrations
applied) or `NEON_API_KEY` + `NEON_PROJECT_ID` are set; both skip cleanly
otherwise.

`npm run test` needs `DATABASE_URL`; the DB-backed suites skip cleanly without
one. `npm run test:e2e` needs a `netlify dev` it can reach, or
`PLAYWRIGHT_BASE_URL` pointed at a running server.

## Branches and environment

Two namespaces that are easy to confuse:

- **git**: default branch is `master`.
- **Neon**: `main` is production, `dev` is local development and Netlify deploy
  previews.

| Variable                        | Where it is set                                    | What it is                                                                                                                                                                |
| ------------------------------- | -------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `DATABASE_URL`                  | `.env` locally; Netlify, scoped per deploy context | **Pooled** (`-pooler`) URL. The only DB variable the web app reads. `main` branch URL for the production context, `dev` branch URL for deploy previews and branch deploys |
| `DATABASE_URL_UNPOOLED`         | `.env` locally only                                | Direct URL for `dev` migrations. **Never set on Netlify**                                                                                                                 |
| `DATABASE_URL_UNPOOLED_MAIN`    | your shell, when migrating production              | Direct URL for `main`. Never committed, never on Netlify                                                                                                                  |
| `XLICKBAIT_PROD_DB_HOST`        | `.env`, and the generator host                     | Hostname of the `main` endpoint. Seed and reset refuse to run against it                                                                                                  |
| `XLICKBAIT_ALLOW_NO_PROD_GUARD` | `.env`, temporarily                                | `1` acknowledges in writing that no production DB exists yet. Delete it once `XLICKBAIT_PROD_DB_HOST` is real                                                             |
| `PUBLIC_SITE_URL`               | `.env`                                             | Only used for local convenience; the feed derives its origin from the request                                                                                             |

On Netlify, `DATABASE_URL` must be scoped so **functions** can read it at
runtime, not only builds. The app reads `$env/dynamic/private`, so a
build-only variable is invisible to it.

### Things that must not happen

- **Never install `@netlify/database`** or any Netlify DB extension. Their
  presence makes Netlify auto-provision its own database. This project uses a
  standalone Neon account.
- **Never run `drizzle-kit push` against `main`**, and never hand-apply DDL to
  it. Schema changes reach production only as committed migrations.
- **Never edit a migration after it is committed.** Add a new one.
- Prefer additive migrations: land the column before the code that needs it.
- Nothing generator-related runs on Netlify. The Anthropic key and the unpooled
  URLs never go there.

## Migrations

```sh
npm run db:generate                             # schema.ts -> drizzle/migrations/
npm run db:migrate                              # apply to dev
XLICKBAIT_CONFIRM_MAIN=yes \
  DATABASE_URL_UNPOOLED_MAIN=... bin/migrate.sh main
```

`bin/migrate.sh` greps generated SQL for `$1`-style placeholders and refuses to
apply if it finds any. That is not paranoia: drizzle-kit renders index
predicates by serialising a SQL node, and an `eq()` in a partial index emits
`WHERE "status" = $1`, which is invalid DDL that fails at _migrate_ time — long
after the migration was generated, reviewed and committed. Write such predicates
as raw `sql` templates with literal values.

`bin/migrate.sh` also runs the shared host guard in both directions: `dev` must
not resolve to the production host, and `main` must not resolve to anything else
— an empty `DATABASE_URL_UNPOOLED_MAIN` silently falling back would otherwise
apply production migrations to dev.

Run `npm run db:check` after generating. drizzle-kit's applied-migrations gate
reads only the newest row (`order by created_at desc limit 1`), so a migration
generated on a branch off an older snapshot is skipped **permanently and
silently** — no error, nothing in the database to notice. `db:check` is what
catches that.

`MIGRATE_TRANSPORT=http` routes migrations through Neon's SQL-over-HTTP endpoint
instead of the wire protocol, for networks that block 5432. It is **permitted
for `dev` only** — the HTTP driver has no transactions, so a failure halfway
leaves the schema partly applied with no rollback.

## Layout

```
src/lib/server/db/schema.ts   source of truth for BOTH languages
src/lib/server/db/client.ts   read-only handle; the raw driver stays private here
src/lib/server/db/queries.ts  every SELECT the site makes
src/lib/server/db/cursor.ts   opaque (publish_at, id) pagination cursor
src/lib/server/db/guard.ts    production-host guard for destructive scripts
src/lib/cache.ts              cache tag vocabulary + the header helper
src/lib/thumb.ts              deterministic SVG thumbnails
src/lib/{rng,slug,time,feed,config}.ts
src/hooks.server.ts           applies cache headers to every response
src/params/                   route matchers (yyyy, mm, dd)
scripts/                      seed, reset, http migrate, OG image (may write)
bin/migrate.sh                migration wrapper
drizzle/migrations/           generated SQL — committed, never edited
```

## The read-only guarantee

The web app issues only SELECTs, enforced four independent ways:

0. **A read-only Postgres role.** Migration `..._readonly_role` creates
   `xlickbait_read` with `SELECT` and nothing else, plus default privileges so
   later tables inherit it. Netlify's `DATABASE_URL` uses that role. This is the
   outermost layer and the only one that does not live in the repository — the
   three below are all bypassed by a compromised build or a dependency
   postinstall script; a role without `INSERT`/`UPDATE`/`DELETE` is not.
   The role is created `NOLOGIN`, because a committed migration must not carry a
   password. Grant one out of band:
   `ALTER ROLE xlickbait_read WITH LOGIN PASSWORD '<generated>';`

The three in-repo layers:

1. **Types.** `client.ts` keeps the Drizzle instance module-private and exports
   a handle narrowed to the select side, so `db.insert(...)` does not compile.
2. **ESLint.** `no-restricted-syntax` bans `.insert(`/`.update(`/`.delete(`/
   `.execute(` under `src/`, and `no-restricted-imports` stops anything but
   `client.ts` reaching for the driver.
3. **A source scan** in `tests/unit/no-writes.test.ts`, which is the only layer
   that catches a write smuggled through a raw SQL template string.

All three in-repo layers are verified to fire against a deliberate violation. Do
not weaken any of them to make a change pass.

## Caching

One helper builds the headers; `hooks.server.ts` applies them in exactly one
place, because SvelteKit throws if the same header is set twice in one request
(including across a layout load and a page load).

Responses carry **both** spellings on purpose:

- `Netlify-CDN-Cache-Control` / `Netlify-Cache-Tag` — read and then **stripped**
  by Netlify before the response reaches the client.
- `CDN-Cache-Control` / `Cache-Tag` — always passed downstream.

Emitting only the Netlify pair gives a curl check that passes locally (no CDN to
strip anything) and fails in production. `durable` goes only on the Netlify
header; it is a Netlify extension and has no effect on Edge Functions, which is
one reason SSR is pinned to a Node function (`edge: false`, passed explicitly —
the default reads `NETLIFY_SVELTEKIT_USE_EDGE` from the environment).

### Cache tag vocabulary

The Phase 2 generator purges by these exact strings. Keep the two in sync.

| Tag                | On                                                |
| ------------------ | ------------------------------------------------- |
| `site`             | every cacheable response                          |
| `list`             | front page, day pages, category pages, pagination |
| `feed`             | `/feed.xml`                                       |
| `archive`          | `/archive`                                        |
| `h:<id>`           | one headline's permalink                          |
| `day:<YYYY-MM-DD>` | one UTC day page                                  |
| `cat:<category>`   | one category page                                 |

Purge: `POST https://api.netlify.com/api/v1/purge` with
`Authorization: Bearer <token>` and `{"site_id": "...", "cache_tags": [...]}`.
Rate limited to two purges per tag per five seconds.

## Conventions worth knowing

- **Days are UTC**, everywhere: day pages, archive grouping, displayed dates.
- **Cursors are `(publish_at, id)`**, never `publish_at` alone — the generator
  writes batches, so identical timestamps are normal, and a non-unique sort key
  duplicates or skips rows at page boundaries.
- **The chumbox is deterministic**, seeded from the route plus a time bucket.
  `ORDER BY random()` behind a CDN would be frozen for the whole cache window
  anyway, while costing a full scan and nondeterministic tests.
- **Thumbnails must stay byte-identical** for a given arXiv id — they are inlined
  into cached HTML. No `Math.random`, no clock, no locale formatting.
- **Internal links go through `resolve()`** from `$app/paths`; outbound links go
  through `absUrl()` so a malformed `abs_url` column cannot redirect a reader.
- `arxiv` appears in no URL path or asset name, there is no arXiv branding, and
  nothing implies affiliation.

## Verification, and its honest limits

Three tiers, because they prove different things:

1. `netlify dev` — a Vite proxy. Proves routes and markup. **It deletes
   `.netlify/functions-internal/`**, so never chain `npm run build && netlify dev`
   and expect the built function to survive.
2. `netlify serve` — the real `sveltekit-render` function. Where the curl header
   demonstration belongs.
3. `npm run test:built` — invokes the built handler in a separate Node process
   (importing it into Vitest puts it back through Vite's transform pipeline and
   changes its behaviour).

**What none of this proves:** that Netlify's CDN acts on the headers. There is no
CDN locally — no cache, so never a HIT, no `Cache-Status`, no
stale-while-revalidate, no durable tier, and no tag purge to exercise. That is a
post-deploy check: curl production twice and assert `Cache-Status` moves from
`"Netlify Edge"; fwd=miss` to `"Netlify Edge"; hit`.

## arXiv

Metadata only — title, abstract, authors, categories, dates. Never PDFs or full
text. arXiv's API terms require **no** attribution (metadata is CC0 1.0) and
forbid implying endorsement. Attribution **is** expected, though: the API landing
page asks products to acknowledge data usage, and the brand guidelines give the
required form for products using the API. The footer carries **both** sentences,
verbatim:

> Thank you to arXiv for use of its open access interoperability. This service
> was not reviewed or approved by, nor does it necessarily express or reflect the
> policies or opinions of, arXiv.

The disclaimer is load-bearing given the "FROM THE ARχIVE" section heading — the
rule is not to brand a project in a way implying endorsement. The rate limit is one request every three seconds on a single
connection — that governs Phase 2.

## Stack notes

`drizzle-orm` and `drizzle-kit` are pinned to **`1.0.0-rc.4`**, not `latest`.
The docs site documents v1 while npm `latest` is still 0.45.x, so docs snippets
do not compile against `latest`. On v1 the `schema` config key is gone in favour
of a `relations` API — this project sidesteps that entirely by using the core
query builder with explicit `innerJoin`s rather than `db.query.*`.

`pg` and `sharp` are devDependencies and never reach a function: `pg` exists so
drizzle-kit selects the wire protocol for migrations, and `sharp` only rasterises
the OG image in `npm run og:build`.

## The generator (Phase 2)

Lives in `generator/`, runs from cron on a personal machine, and is the only
writer in the system. Nothing generator-related runs on Netlify: the Anthropic
key and the write-capable connection string must not exist there.

```
generator/config.py        every tunable, env-overridable
generator/tags.py          cache tag vocabulary -- MUST match src/lib/cache.ts
generator/arxiv/client.py  the one polite HTTP client
generator/arxiv/ids.py     identifier scheme and sampling
generator/arxiv/atom.py    parsing, withdrawal heuristics, miss reconciliation
generator/arxiv/select.py  fresh and vintage picking
generator/truth.py         the truth gate
generator/llm.py           Anthropic call with structured output
generator/db.py            psycopg 3 writes + the schema assertion
generator/purge.py         Netlify cache-tag purge
generator/prompts/headline_system.md   the style guide, loaded at runtime
```

### Rate limiting

`XLICKBAIT_ARXIV_INTERVAL` is **clamped, not merely defaulted**: an override may
slow the client down but can never take it below three seconds, because that
interval is a condition of use rather than a preference.

arXiv: _"make no more than one request every three seconds, and limit requests
to a single connection at a time"_ -- and that limit applies to **all machines
under your control as a whole**, not per process. There are no rate-limit
headers to react to, so `RateLimiter` self-governs on a monotonic clock, and the
transport is capped at one connection so the rule is a property of the client
rather than a promise in a comment.

Do not enable robots.txt handling anywhere near this: `export.arxiv.org`
serves `Disallow: /`, aimed at crawlers, while the Terms of Use explicitly
permit programmatic API use.

Vintage identifiers are verified in **batches** through `id_list`, which is
comma-delimited -- fifty candidates cost one request rather than fifty, which
under the three-second rule is 3 seconds instead of 150. Two traps come with it:

- **A partial miss is silent.** Absent identifiers are not mentioned anywhere;
  `totalResults` just drops. `reconcile()` compares against what was requested.
- **A malformed identifier is indistinguishable from a real miss** -- HTTP 200,
  empty feed. Candidates are validated locally first, because arXiv will not
  tell us.

### The truth gate

`anchor` must appear verbatim in the title or abstract after whitespace and case
normalisation **and nothing else**. Not unicode folding, not punctuation
normalisation. A model that straightens a curly quote while "copying" is
retyping, and that is exactly what this catches.

Two details that are easy to get wrong, and were:

- **`str.lower()`, never `str.casefold()`.** Case folding is a Unicode
  transformation rather than a case change -- it maps `Straße` to `strasse`, so
  a gate built on it accepts an anchor that was retyped rather than copied.
- **Each field is searched separately.** Concatenating title and abstract before
  searching invents an adjacency present in neither, so an anchor spanning the
  seam ("`...Mass`" + "`We...`" -> "`Mass We`") matched although nobody wrote it. On a miss it regenerates twice
  with the rejected anchor quoted back, then drops the paper and picks another.
  Rejections are counted in `generator_runs`.

Structured output (`messages.parse` with a Pydantic model) guarantees the JSON
_shape_; it says nothing about whether the anchor is real. The two checks are
separate and the gate is never relaxed to let a headline through.

### Purging

`purge.py` exists as its own module for one reason. From Netlify's docs: _"If
you don't specify a list of cache_tags, the entire site will be purged. However,
if you specify an empty list of cache_tags, no purge will be applied."_ So a run
that published nothing must send **no request at all** -- the difference between
a no-op and invalidating the whole site is whether a key is present in a JSON
body. A 404 means a wrong site id and is a hard error, never a retry.

`generator/tags.py` and `src/lib/cache.ts` must agree exactly. A test executes
both and compares, because this is the one contract in the project that fails
silently: a drifted spelling means purges that match nothing, content that never
updates, and `202 Accepted` every time.
