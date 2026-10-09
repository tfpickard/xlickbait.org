"""Every tunable in one place, with environment overrides.

Mirrors `src/lib/config.ts` on the TypeScript side for anything shared. The
cache tag vocabulary lives in `generator/tags.py` and is tested against the
TypeScript implementation directly, because a silent divergence there means
purges that match nothing.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass, field

from generator import image as image_module

# What OpenRouter's image endpoint accepts for `quality`. Models without the knob
# ignore it; `auto` means "send nothing and let the provider decide".
IMAGE_QUALITIES = frozenset({"auto", "low", "medium", "high"})

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


# Illustrations go through OpenRouter's dedicated image endpoint. Swap the model
# with XLICKBAIT_IMAGE_MODEL; anything on
# https://openrouter.ai/api/v1/images/models works.
#
# This default is not the cheapest slug on that endpoint. It is the one that was
# actually watched producing a usable tabloid front page -- legible headline
# type, correct spelling, the handwritten marginalia -- at a measured $0.02 and
# twelve seconds an image. That is about $50 a year at this publishing rate,
# which for the thing readers actually look at is not the place to save $45.
#
# `openai/gpt-image-1-mini` at XLICKBAIT_IMAGE_QUALITY=low is roughly ten times
# cheaper (~$0.002) and worth trying, but nobody here has seen its output yet.
# It is the only listed model with a `quality` knob; the default below has none,
# which is why XLICKBAIT_IMAGE_QUALITY defaults to `auto` and sends no such
# field.
DEFAULT_IMAGE_MODEL = "microsoft/mai-image-2.6-flash"


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
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number, got {raw!r}") from exc
    # `float()` accepts "nan" and "inf", and EVERY comparison against nan is
    # False -- including the `remaining < reserve` test the image spend ceiling
    # is built on. `XLICKBAIT_IMAGE_BUDGET_USD=nan` would therefore read as a
    # configured budget and then never bind, letting every headline in a large
    # `images --limit` reach the paid endpoint. `inf` does the same thing more
    # honestly. Neither is a number anyone means to type, and both are rejected
    # here rather than at each use, so no later float setting can inherit the
    # hole.
    if not math.isfinite(value):
        raise SystemExit(f"{name} must be a finite number, got {raw!r}")
    return value


def _positive(name: str, value: int) -> int:
    """Reject a non-positive count outright rather than hanging on it.

    A zero or negative id batch makes the vintage sampler draw nothing on every
    pass, which used to turn a cron run into a silent busy loop.
    """
    if value < 1:
        raise SystemExit(f"{name} must be a positive integer, got {value}")
    return value


def _non_negative(name: str, value: int) -> int:
    """Reject a negative count rather than quietly shrinking the run.

    Zero is a meaningful setting -- it disables vintage picks. A negative value
    is truthy, so it reached `pick_vintage`, whose loop and shortage check both
    pass immediately; the run was then recorded as a success having published
    fewer headlines than asked for, with nothing to indicate why.
    """
    if value < 0:
        raise SystemExit(f"{name} must be zero or greater, got {value}")
    return value


def _bool_env(name: str, default: bool) -> bool:
    """A switch, read the way people actually type switches.

    Anything unrecognised is an error rather than a silent `False`: the one that
    matters is XLICKBAIT_IMAGES, and "I set it and nothing happened" is a much
    worse afternoon than "it refused to start".
    """
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise SystemExit(f"{name} must be a boolean (1/0, true/false, yes/no, on/off), got {raw!r}")


def _in_range(name: str, value: int, *, low: int, high: int) -> int:
    if not low <= value <= high:
        raise SystemExit(f"{name} must be between {low} and {high}, got {value}")
    return value


def _non_negative_float(name: str, value: float) -> float:
    if value < 0:
        raise SystemExit(f"{name} must be zero or greater, got {value}")
    return value


def _positive_float(name: str, value: float) -> float:
    """Strictly positive, unlike `_non_negative_float`.

    For the assumed image cost specifically. Zero passes a non-negative check
    and then disables the spend ceiling outright: when OpenRouter omits
    `usage.cost`, every call adds zero to the running total, so the pre-call
    `remaining < assumed` test never becomes true and the budget never binds --
    on precisely the missing-cost path it exists to guard, and worst of all
    under a large `images --limit`. A zero overall BUDGET is still allowed; that
    is the off switch, and it stops the first call rather than none of them.
    """
    if value <= 0:
        raise SystemExit(f"{name} must be greater than zero, got {value}")
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

    # ---- illustrations, via OpenRouter -----------------------------------
    # All optional. Without a key the generator publishes exactly as it always
    # has and the site draws its deterministic SVG thumbnails instead, which is
    # why none of these can fail a run.
    openrouter_api_key: str | None = None
    images_enabled: bool = True
    image_model: str = DEFAULT_IMAGE_MODEL
    image_style: str = "terse"
    image_aspect_ratio: str = "3:2"
    image_quality: str = "auto"
    image_max_width: int = 1200
    image_max_bytes: int = 400_000
    image_webp_quality: int = 82
    image_budget_usd: float = 0.25
    image_assumed_cost_usd: float = 0.01
    image_timeout: float = 180.0

    @property
    def can_purge(self) -> bool:
        return bool(self.netlify_purge_token and self.netlify_site_id)

    @property
    def can_illustrate(self) -> bool:
        return self.illustration_blocker is None

    @property
    def illustration_blocker(self) -> str | None:
        """Why illustrations are off this run, or None when they are on.

        The purge requirement is the non-obvious one, and it is a takedown
        guarantee rather than a convenience.

        `/i/<id>` is held by the CDN for a YEAR -- that long TTL is what makes
        serving image bytes out of Postgres affordable at all. `hide` without
        purge credentials only flips the database row and relies on the cached
        response expiring, which for every HTML page is about an hour. For an
        image it is twelve months: the CDN never re-runs `getHeadlineImage`, so
        the visibility rule never gets a chance to fire and the illustration of
        a taken-down headline stays publicly reachable at a guessable URL long
        after the headline itself is gone.

        With credentials there is no hole, because `hide` purges the blunt
        `site` tag and every cacheable response -- the image route included --
        carries it.

        So images require a working purge path. This returns a reason rather
        than raising: illustrations are decoration, and nothing about them may
        stop a run from publishing headlines.
        """
        if not self.images_enabled:
            return "XLICKBAIT_IMAGES is off"
        if not self.openrouter_api_key:
            return "no OPENROUTER_API_KEY"
        if not self.can_purge:
            return (
                "images need NETLIFY_PURGE_TOKEN and NETLIFY_SITE_ID: /i/<id> is cached "
                "for a year, so without a purge `hide` would take a headline down and "
                "leave its illustration served from the CDN"
            )
        return None


# Fresh count is clamped: fewer than two is not a front page, and more than five
# in one run turns the site into a firehose.
FRESH_MIN = 2
FRESH_MAX = 5


def clamp_fresh(value: int) -> int:
    return max(FRESH_MIN, min(FRESH_MAX, value))


def _database_url() -> str:
    url = os.environ.get("XLICKBAIT_DB_URL", "").strip()
    if not url:
        raise SystemExit(
            "XLICKBAIT_DB_URL is not set. It must be a write-capable connection "
            "string for the Neon branch this generator writes to."
        )
    return url


def load_for_hide() -> Config:
    """Configuration for the kill switch: database and purge, nothing else.

    This deliberately does not read -- let alone validate -- a single generation
    setting. `hide` calls neither Anthropic nor arXiv, so an absent API key, a
    malformed XLICKBAIT_ARXIV_INTERVAL or an XLICKBAIT_ID_BATCH of 0 must not be
    able to stop a takedown. Routing this through the full loader meant a bad
    cron tuning value could disable the only mechanism for removing a headline,
    and the moment you need it is exactly the moment something else is wrong.

    The generation fields below are inert placeholders, never used on this path.
    """
    return Config(
        database_url=_database_url(),
        anthropic_api_key="",
        model="",
        fresh_count=0,
        vintage_count=0,
        netlify_purge_token=os.environ.get("NETLIFY_PURGE_TOKEN") or None,
        netlify_site_id=os.environ.get("NETLIFY_SITE_ID") or None,
    )


def load_for_images() -> Config:
    """Configuration for the image backfill: database, purge and the image knobs.

    Same reasoning as `load_for_hide`. Backfilling pictures for headlines that
    already exist calls neither arXiv nor Anthropic, so a missing
    ANTHROPIC_API_KEY or a mistyped XLICKBAIT_ID_BATCH must not be able to stop
    it. The generation fields below are inert placeholders on this path.
    """
    return Config(
        database_url=_database_url(),
        anthropic_api_key="",
        model="",
        fresh_count=0,
        vintage_count=0,
        netlify_purge_token=os.environ.get("NETLIFY_PURGE_TOKEN") or None,
        netlify_site_id=os.environ.get("NETLIFY_SITE_ID") or None,
        **image_settings(),
    )


def load(
    *,
    fresh: int | None = None,
    vintage: int | None = None,
) -> Config:
    """Build a Config for a generation run, with explicit CLI overrides."""
    database_url = _database_url()

    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("ANTHROPIC_API_KEY is not set.")

    return Config(
        database_url=database_url,
        anthropic_api_key=api_key,
        model=os.environ.get("XLICKBAIT_MODEL", "claude-sonnet-5").strip(),
        fresh_count=clamp_fresh(fresh if fresh is not None else _int_env("XLICKBAIT_FRESH", 3)),
        vintage_count=_non_negative(
            "XLICKBAIT_VINTAGE",
            vintage if vintage is not None else _int_env("XLICKBAIT_VINTAGE", 4),
        ),
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
        **image_settings(),
    )


def image_settings() -> dict[str, object]:
    """The illustration knobs, resolved and validated.

    Split out because `images` (the backfill command) needs exactly these and
    none of the arXiv or Anthropic settings -- backfilling pictures for headlines
    that already exist must not be blocked by a malformed XLICKBAIT_ID_BATCH, for
    the same reason `load_for_hide` exists.
    """
    style = os.environ.get("XLICKBAIT_IMAGE_STYLE", "terse").strip() or "terse"
    if style not in image_module.STYLES:
        raise SystemExit(
            f"XLICKBAIT_IMAGE_STYLE must be one of "
            f"{', '.join(sorted(image_module.STYLES))}, got {style!r}"
        )
    quality = os.environ.get("XLICKBAIT_IMAGE_QUALITY", "auto").strip() or "auto"
    if quality not in IMAGE_QUALITIES:
        raise SystemExit(
            f"XLICKBAIT_IMAGE_QUALITY must be one of "
            f"{', '.join(sorted(IMAGE_QUALITIES))}, got {quality!r}"
        )

    return {
        "openrouter_api_key": os.environ.get("OPENROUTER_API_KEY", "").strip() or None,
        "images_enabled": _bool_env("XLICKBAIT_IMAGES", True),
        "image_model": os.environ.get("XLICKBAIT_IMAGE_MODEL", DEFAULT_IMAGE_MODEL).strip()
        or DEFAULT_IMAGE_MODEL,
        "image_style": style,
        "image_aspect_ratio": os.environ.get("XLICKBAIT_IMAGE_ASPECT", "3:2").strip() or "3:2",
        "image_quality": quality,
        "image_max_width": _positive(
            "XLICKBAIT_IMAGE_MAX_WIDTH", _int_env("XLICKBAIT_IMAGE_MAX_WIDTH", 1200)
        ),
        "image_max_bytes": _positive(
            "XLICKBAIT_IMAGE_MAX_BYTES", _int_env("XLICKBAIT_IMAGE_MAX_BYTES", 400_000)
        ),
        "image_webp_quality": _in_range(
            "XLICKBAIT_IMAGE_WEBP_QUALITY",
            _int_env("XLICKBAIT_IMAGE_WEBP_QUALITY", 82),
            low=1,
            high=100,
        ),
        # A ceiling on one run's image spend, not a target. It exists so a typo in
        # XLICKBAIT_IMAGE_MODEL -- say, a slug that bills $0.12 an image instead
        # of $0.002 -- costs pennies rather than running unattended on cron.
        "image_budget_usd": _non_negative_float(
            "XLICKBAIT_IMAGE_BUDGET_USD", _float_env("XLICKBAIT_IMAGE_BUDGET_USD", 0.25)
        ),
        # The measured cost of the default model is $0.02, so an assumed worst
        # case of $0.01 would UNDER-bill exactly when the bill is invisible.
        # Rounded up rather than to the observed figure: this number only gets
        # used when OpenRouter did not say, which is not the moment to be
        # optimistic.
        "image_assumed_cost_usd": _positive_float(
            "XLICKBAIT_IMAGE_ASSUMED_COST_USD",
            _float_env("XLICKBAIT_IMAGE_ASSUMED_COST_USD", 0.03),
        ),
        "image_timeout": _float_env("XLICKBAIT_IMAGE_TIMEOUT", 180.0),
    }
