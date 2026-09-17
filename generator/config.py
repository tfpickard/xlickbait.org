"""Every tunable in one place, with environment overrides.

Mirrors `src/lib/config.ts` on the TypeScript side for anything shared. The
cache tag vocabulary lives in `generator/tags.py` and is tested against the
TypeScript implementation directly, because a silent divergence there means
purges that match nothing.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

# arXiv asks for one request every three seconds across all the machines under
# your control, and returns no rate-limit headers. The client self-governs.
ARXIV_MIN_INTERVAL_SECONDS = 3.0
ARXIV_API_URL = "https://export.arxiv.org/api/query"

# Identifies the project and gives arXiv someone to contact instead of simply
# blocking us. No User-Agent is mandated, but an anonymous one is rude.
DEFAULT_USER_AGENT = (
    "xlickbait/0.1 (+https://xlickbait.org; satire site linking arXiv abstracts; "
    "contact: hello@xlickbait.org)"
)


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from exc


def _float_env(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number, got {raw!r}") from exc


def _positive(name: str, value: int) -> int:
    """Reject a non-positive count outright rather than hanging on it.

    A zero or negative id batch makes the vintage sampler draw nothing on every
    pass, which used to turn a cron run into a silent busy loop.
    """
    if value < 1:
        raise SystemExit(f"{name} must be a positive integer, got {value}")
    return value


def _list_env(name: str, default: list[str]) -> list[str]:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    return [part.strip() for part in raw.split(",") if part.strip()]


@dataclass(frozen=True)
class Config:
    """Resolved configuration for one run."""

    database_url: str
    anthropic_api_key: str
    model: str

    fresh_count: int
    vintage_count: int

    # Categories to draw fresh picks from. Empty means "all of arXiv".
    category_pool: list[str] = field(default_factory=list)

    user_agent: str = DEFAULT_USER_AGENT
    request_interval: float = ARXIV_MIN_INTERVAL_SECONDS
    max_retries: int = 3

    # How many sampled identifiers to verify in a single id_list request. The
    # API takes a comma-delimited list, so this is the difference between one
    # request and fifty under the three-second rule.
    id_batch_size: int = 50
    # Ceiling on sampling attempts before a vintage run fails loudly rather than
    # spinning forever against a sparse identifier space.
    max_vintage_attempts: int = 400

    # Truth-gate retries before a paper is abandoned and replaced.
    truth_gate_retries: int = 2

    netlify_purge_token: str | None = None
    netlify_site_id: str | None = None

    @property
    def can_purge(self) -> bool:
        return bool(self.netlify_purge_token and self.netlify_site_id)


# Fresh count is clamped: fewer than two is not a front page, and more than five
# in one run turns the site into a firehose.
FRESH_MIN = 2
FRESH_MAX = 5


def clamp_fresh(value: int) -> int:
    return max(FRESH_MIN, min(FRESH_MAX, value))


def load(
    *,
    fresh: int | None = None,
    vintage: int | None = None,
    require_api_key: bool = True,
) -> Config:
    """Build a Config from the environment, with explicit CLI overrides.

    `require_api_key=False` is for commands that never reach Anthropic. The kill
    switch is the one that matters: `hide` must work when the key is missing,
    expired, or mid-rotation, because that is exactly when someone is trying to
    take a headline down in a hurry.
    """
    database_url = os.environ.get("XLICKBAIT_DB_URL", "").strip()
    if not database_url:
        raise SystemExit(
            "XLICKBAIT_DB_URL is not set. It must be a write-capable connection "
            "string for the Neon branch this generator writes to."
        )

    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key and require_api_key:
        raise SystemExit("ANTHROPIC_API_KEY is not set.")

    return Config(
        database_url=database_url,
        anthropic_api_key=api_key,
        model=os.environ.get("XLICKBAIT_MODEL", "claude-sonnet-5").strip(),
        fresh_count=clamp_fresh(fresh if fresh is not None else _int_env("XLICKBAIT_FRESH", 3)),
        vintage_count=vintage if vintage is not None else _int_env("XLICKBAIT_VINTAGE", 4),
        category_pool=_list_env("XLICKBAIT_CATEGORIES", []),
        user_agent=os.environ.get("XLICKBAIT_USER_AGENT", DEFAULT_USER_AGENT),
        # Clamped, never merely defaulted: arXiv's three seconds is a condition
        # of use, so an override may slow the client down but never speed it up.
        request_interval=max(
            ARXIV_MIN_INTERVAL_SECONDS,
            _float_env("XLICKBAIT_ARXIV_INTERVAL", ARXIV_MIN_INTERVAL_SECONDS),
        ),
        max_retries=_int_env("XLICKBAIT_MAX_RETRIES", 3),
        id_batch_size=_positive("XLICKBAIT_ID_BATCH", _int_env("XLICKBAIT_ID_BATCH", 50)),
        max_vintage_attempts=_int_env("XLICKBAIT_MAX_VINTAGE_ATTEMPTS", 400),
        truth_gate_retries=_int_env("XLICKBAIT_TRUTH_RETRIES", 2),
        netlify_purge_token=os.environ.get("NETLIFY_PURGE_TOKEN") or None,
        netlify_site_id=os.environ.get("NETLIFY_SITE_ID") or None,
    )
