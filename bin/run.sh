#!/usr/bin/env bash
#
# Cron wrapper for the headline generator.
#
#   0 */6 * * *  /path/to/xlickbait.org/bin/run.sh --stagger 6
#
# Environment lives OUTSIDE the repository, so a checkout never contains the
# Anthropic key or a write-capable connection string. Override the location with
# XLICKBAIT_ENV_FILE.
#
# Exits non-zero on any failure so cron mails you instead of failing silently.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

env_file="${XLICKBAIT_ENV_FILE:-$HOME/.config/xlickbait/env}"
if [ ! -f "$env_file" ]; then
	echo "missing environment file: $env_file" >&2
	echo "It should set XLICKBAIT_DB_URL, ANTHROPIC_API_KEY and optionally" >&2
	echo "NETLIFY_PURGE_TOKEN, NETLIFY_SITE_ID and OPENROUTER_API_KEY." >&2
	exit 1
fi

set -a
# shellcheck disable=SC1090
. "$env_file"
set +a

python="${XLICKBAIT_PYTHON:-$repo_root/.venv/bin/python}"
if [ ! -x "$python" ]; then
	echo "no interpreter at $python (set XLICKBAIT_PYTHON)" >&2
	exit 1
fi

exec "$python" -m generator run "$@"
