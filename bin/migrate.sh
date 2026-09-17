#!/usr/bin/env bash
#
# Apply committed migrations to a Neon branch.
#
#   bin/migrate.sh dev
#   XLICKBAIT_CONFIRM_MAIN=yes bin/migrate.sh main
#
# Netlify never runs this. Production migrations are applied deliberately, by a
# human, before deploying code that depends on them.
set -euo pipefail

usage() {
	cat >&2 <<'USAGE'
usage: bin/migrate.sh <dev|main>

Environment:
  DATABASE_URL_UNPOOLED_DEV    direct (non-pooler) URL for the dev branch
                               falls back to DATABASE_URL_UNPOOLED
  DATABASE_URL_UNPOOLED_MAIN   direct URL for the main branch (no fallback)
  XLICKBAIT_CONFIRM_MAIN=yes   required to touch main
  MIGRATE_TRANSPORT=http       use the SQL-over-HTTP migrator (dev only)
USAGE
	exit 64
}

[ "$#" -eq 1 ] || usage
branch="$1"

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

# Load .env if present so the script works the same way as the npm scripts.
if [ -f .env ]; then
	set -a
	# shellcheck disable=SC1091
	. ./.env
	set +a
fi

case "$branch" in
dev)
	url="${DATABASE_URL_UNPOOLED_DEV:-${DATABASE_URL_UNPOOLED:-}}"
	;;
main)
	# No fallback to the dev variable on purpose: a typo must not be able to
	# resolve to a URL that happens to work.
	url="${DATABASE_URL_UNPOOLED_MAIN:-}"
	if [ "${XLICKBAIT_CONFIRM_MAIN:-}" != "yes" ]; then
		echo "refusing to migrate main without XLICKBAIT_CONFIRM_MAIN=yes" >&2
		exit 1
	fi
	;;
*)
	usage
	;;
esac

if [ -z "$url" ]; then
	echo "no unpooled connection string configured for branch '$branch'" >&2
	exit 1
fi

# Backstop against a class of drizzle-kit bug rather than one instance of it.
# Index predicates, check constraints and generated columns are rendered by
# serialising a SQL node; if any of them serialises to a bound parameter the
# emitted DDL contains `$1`, which Postgres rejects at apply time -- long after
# the migration was generated, reviewed and committed.
if grep -rn '\$[0-9]' drizzle/migrations/*/migration.sql 2>/dev/null; then
	echo "" >&2
	echo "refusing to apply: generated DDL above contains bound parameters (\$1, \$2, ...)." >&2
	echo "Rewrite the offending predicate as a raw sql template with literal values." >&2
	exit 1
fi

transport="${MIGRATE_TRANSPORT:-wire}"
if [ "$transport" = "http" ] && [ "$branch" = "main" ]; then
	# The HTTP driver cannot open a transaction, so a failure part-way through
	# leaves the schema half-migrated with no rollback. Acceptable on a branch
	# that can be reset; never on production.
	echo "refusing: MIGRATE_TRANSPORT=http is not permitted for main (no transactional DDL)" >&2
	exit 1
fi

echo "==> migrating '$branch' via $transport transport"
case "$transport" in
http)
	DATABASE_URL_UNPOOLED="$url" npx tsx scripts/migrate-http.ts
	;;
wire)
	DATABASE_URL_UNPOOLED="$url" npx drizzle-kit migrate
	;;
*)
	echo "unknown MIGRATE_TRANSPORT '$transport' (expected 'wire' or 'http')" >&2
	exit 1
	;;
esac
echo "==> done"
