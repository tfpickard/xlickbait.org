"""The xlickbait headline generator.

Writes to Neon Postgres; the website only ever reads. Runs from cron on a
personal machine, never on Netlify -- the Anthropic key and the unpooled
connection strings must not exist there.
"""
