# xlickbait.org

A straight-faced tabloid front page for arXiv preprints. Every headline is
technically true, seizes on some peripheral detail, and completely misses the
point of the paper it links to. It is satire, and the footer says so.

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
| `npm run db:migrate`          | Apply migrations to **dev**                      |
| `npm run db:seed`             | Load fixtures into dev (idempotent)              |
| `npm run db:reset-dev`        | Truncate dev and reseed                          |
| `npm run og:build`            | Regenerate the static OG image                   |

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

The web app issues only SELECTs, enforced three independent ways:

1. **Types.** `client.ts` keeps the Drizzle instance module-private and exports
   a handle narrowed to the select side, so `db.insert(...)` does not compile.
2. **ESLint.** `no-restricted-syntax` bans `.insert(`/`.update(`/`.delete(`/
   `.execute(` under `src/`, and `no-restricted-imports` stops anything but
   `client.ts` reaching for the driver.
3. **A source scan** in `tests/unit/no-writes.test.ts`, which is the only layer
   that catches a write smuggled through a raw SQL template string.

All three are verified to fire. Do not weaken any of them to make a change pass.

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
forbid implying endorsement; they _request_ the acknowledgement
"Thank you to arXiv for use of its open access interoperability", which the
footer carries. The rate limit is one request every three seconds on a single
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
