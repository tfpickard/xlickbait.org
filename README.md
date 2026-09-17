# xlickbait.org

Sensational, technically true headlines about real arXiv preprints. Every one of
them misses the point.

It is satire. Every link goes to a real paper whose authors did nothing to
deserve this, and every headline carries a "Fact check" saying what the paper
actually does. Not affiliated with arXiv.

```sh
npm install
cp .env.example .env     # add your Neon dev branch connection string
npm run db:migrate
npm run db:seed
npx netlify dev --offline
```

See [CLAUDE.md](./CLAUDE.md) for commands, branch and environment layout, the
cache tag vocabulary, and the conventions this codebase relies on.
