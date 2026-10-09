# xlickbait.org

Sensational, technically true headlines about real arXiv preprints. Every one of
them misses the point.

It is satire, though the site itself never says so -- the deadpan is the point.
Every link goes to a real paper whose authors did nothing to deserve this, and
every headline carries a "Fact check" quoting the detail it ran with and saying
what the paper actually does. Not affiliated with arXiv.

```sh
npm install
cp .env.example .env     # add your Neon dev branch connection string
npm run db:migrate
npm run db:seed
npx netlify dev --offline
```

Headlines can carry a generated illustration, served from `/i/<id>`. It is
optional at every level: without an `OPENROUTER_API_KEY` the generator publishes
as normal and the site draws its own deterministic SVG thumbnails, which remain
the fallback for any headline whose image did not work out. `npm run db:seed`
loads fixture images so the path is exercised locally without a key.

See [CLAUDE.md](./CLAUDE.md) for commands, branch and environment layout, the
cache tag vocabulary, and the conventions this codebase relies on.
