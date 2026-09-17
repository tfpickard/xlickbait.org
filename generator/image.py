"""Illustrations for headlines, via OpenRouter's image API.

Decoration, not content. Every call here is allowed to fail: a headline with no
image falls back to the deterministic SVG the site has always drawn, so a model
being down, slow, rate limited or out of credit costs the run nothing. Callers
catch `ImageError` and carry on -- nothing in this module may abort a publish.

Three things are load-bearing and easy to get wrong:

1. **Transcoding is not optional.** The cheap models return PNG, and a 1024px
   PNG from an image model is commonly 1-2 MB. These bytes live in Postgres, so
   writing one straight from the API would put a megabyte per headline into the
   database -- roughly a gigabyte a year at this publishing rate. Pillow
   re-encodes to WebP, and `transcode` walks the quality down until the result
   is under `max_bytes` rather than storing whatever came back.

2. **The size ceiling rejects, it does not truncate.** An image that will not fit
   the budget is dropped and the headline keeps its SVG. Half an image is not an
   image.

3. **The spend ceiling is enforced here, per painter, not per call.** One painter
   instance is one run, so a misconfigured model slug cannot turn a cron job into
   an open-ended bill. OpenRouter reports actual cost in `usage.cost`; when it
   does not, `_reported_cost` bills the configured worst case instead of zero,
   because a budget that assumes free on missing data is not a budget.
"""

from __future__ import annotations

import base64
import binascii
import io
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import httpx
from PIL import Image, UnidentifiedImageError

IMAGE_URL = "https://openrouter.ai/api/v1/images"

PROMPT_DIR = Path(__file__).parent / "prompts"

# Which prose file drives which look.
#
# `terse` is the default, and it is the default because it is the only one with
# evidence behind it: it is, near enough verbatim, the one-line prompt that was
# observed producing exactly the front page this feature is modelled on. The
# temptation to replace it with something more thorough should be resisted until
# something more thorough has actually been run.
#
# That is not a style preference, it is how these models behave. A long brief
# dilutes the instruction, and a list of prohibitions is worse than useless --
# "no logos, no watermarks, no text" puts logos, watermarks and text into the
# conditioning, and they turn up in the output. The three guardrail sentences in
# `image_terse.md` are therefore phrased as things that ARE true of the scene
# rather than things that are forbidden.
#
# `tabloid` is the long-form brief, for when the terse one needs steering.
# `photo` renders the scene alone and asks for no lettering at all, for anyone
# who would rather not stake the joke on an image model's spelling.
STYLES: dict[str, str] = {
    "terse": "image_terse.md",
    "tabloid": "image_tabloid.md",
    "photo": "image_photo.md",
}

# Long inputs cost tokens and buy nothing: the art direction only needs the gist.
MAX_HEADLINE_CHARS = 240
MAX_DEK_CHARS = 400

_RETRY_STATUSES = frozenset({408, 409, 429, 500, 502, 503, 504})


class ImageError(RuntimeError):
    """An illustration could not be produced. Never fatal to a run."""


class TerminalImageError(ImageError):
    """This run will not produce any more images. Stop the loop.

    Still an `ImageError`, so it can never abort a publish -- `illustrate`
    catches it, records the reason and stops asking. The distinction matters
    because the alternative is one futile paid-endpoint request per headline
    for a condition that cannot improve within the run.
    """


class BudgetExhausted(TerminalImageError):
    """The run's image spend ceiling was reached. Stop asking for more."""


class ProviderRefused(TerminalImageError):
    """OpenRouter rejected the key or the account is out of credit.

    Terminal for the same reason the transport does not retry a 401: nothing
    about the next headline changes the answer. Raised as a plain `ImageError`
    it was caught per target and re-issued for every remaining headline in the
    batch -- the exact behaviour the "retrying cannot help" comment on the
    status handling was written to prevent, one level further out.
    """


@dataclass(frozen=True)
class RenderedImage:
    """A transcoded, size-checked image ready to be written to Postgres."""

    data: bytes
    mime: str
    width: int
    height: int
    model: str
    prompt: str
    cost_usd: float
    """What THIS image cost, not the run's running total."""


def load_style(style: str) -> str:
    """Read the art direction for `style` from disk.

    Prose in a file rather than a string literal, for the same reason
    `headline_system.md` is: it is the look of the site, and it should be
    reviewable as writing.
    """
    try:
        filename = STYLES[style]
    except KeyError:
        raise SystemExit(
            f"unknown image style {style!r}; expected one of {', '.join(sorted(STYLES))}"
        ) from None
    return (PROMPT_DIR / filename).read_text(encoding="utf-8")


def _clip(value: str, limit: int) -> str:
    collapsed = " ".join(value.split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: limit - 1].rstrip() + "…"


def build_prompt(template: str, *, headline: str, dek: str, category: str) -> str:
    """Fill the art direction in.

    Token substitution rather than `str.format` or `string.Template`: the
    templates are English prose about typography and lighting, and both of those
    mechanisms assign meaning to characters -- `{`, `}`, `$` -- that prose is
    entitled to contain. A literal three-token replace cannot misfire on a brace
    someone types into a sentence about a bracketed caption.
    """
    return (
        template.replace("{{headline}}", _clip(headline, MAX_HEADLINE_CHARS))
        .replace("{{dek}}", _clip(dek, MAX_DEK_CHARS))
        .replace("{{category}}", _clip(category, 40))
    )


def transcode(
    raw: bytes,
    *,
    max_width: int,
    max_bytes: int,
    quality: int,
    min_quality: int = 45,
) -> tuple[bytes, int, int]:
    """Re-encode to WebP, downscaling and then dropping quality until it fits.

    Returns `(bytes, width, height)`. Raises `ImageError` if the floor quality
    still will not fit the budget, because storing an oversized blob "just this
    once" is how a database fills up.
    """
    try:
        with Image.open(io.BytesIO(raw)) as opened:
            opened.load()
            # Flatten to RGB: the models return RGBA often enough, and an alpha
            # channel behind an opaque tabloid graphic is pure bytes.
            image = opened.convert("RGB")
    except (UnidentifiedImageError, OSError) as exc:
        raise ImageError(f"the model returned something Pillow cannot read: {exc}") from exc

    if image.width > max_width:
        height = max(1, round(image.height * max_width / image.width))
        image = image.resize((max_width, height), Image.LANCZOS)

    # Clamped both ends, and the step is clamped too, so `min_quality` is always
    # the last value actually tried rather than a value the loop steps past on
    # its way to something lower.
    attempt = max(min_quality, quality)
    while True:
        buffer = io.BytesIO()
        # method=6 is the slow, small end of libwebp's speed/size dial. This runs
        # a handful of times a day on a personal machine; the seconds are free
        # and the bytes are not.
        image.save(buffer, format="WEBP", quality=attempt, method=6)
        encoded = buffer.getvalue()
        if len(encoded) <= max_bytes:
            return encoded, image.width, image.height
        if attempt == min_quality:
            raise ImageError(
                f"could not fit the image under {max_bytes} bytes "
                f"(still {len(encoded)} at quality {attempt})"
            )
        attempt = max(min_quality, attempt - 10)


class ImagePainter:
    """One run's worth of image generation, against one model, under one budget."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        style: str,
        aspect_ratio: str,
        quality: str,
        max_width: int,
        max_bytes: int,
        webp_quality: int,
        budget_usd: float,
        assumed_cost_usd: float,
        timeout: float = 180.0,
        max_retries: int = 2,
        referer: str = "https://xlickbait.org",
        title: str = "xlickbait",
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._model = model
        self._template = load_style(style)
        self._aspect_ratio = aspect_ratio
        self._quality = quality
        self._max_width = max_width
        self._max_bytes = max_bytes
        self._webp_quality = webp_quality
        self._budget_usd = budget_usd
        self._assumed_cost_usd = assumed_cost_usd
        self._max_retries = max_retries
        self._sleep = sleep
        self._spent = 0.0
        self._dearest_call = 0.0

        self._owns_client = client is None
        self._http = client or httpx.Client(timeout=httpx.Timeout(timeout))
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            # OpenRouter uses these for its public app leaderboard. Optional, but
            # identifying the caller is the same courtesy the arXiv client pays.
            "HTTP-Referer": referer,
            "X-Title": title,
        }

    def __enter__(self) -> ImagePainter:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        if self._owns_client:
            self._http.close()

    @property
    def spent_usd(self) -> float:
        return self._spent

    def paint(self, *, headline: str, dek: str, category: str) -> RenderedImage:
        """Generate one illustration. Raises `ImageError` on any failure."""
        # Reserve the dearest call seen so far, not merely the configured
        # assumption. The ceiling can only ever be a soft one -- the price is
        # not known until the call has happened and been billed -- so a run can
        # overshoot by at most the cost of the call in flight. Reserving the
        # observed maximum means that after the first surprise the overshoot is
        # bounded by what this model really charges, instead of by an assumption
        # that a misconfigured slug has already proved wrong.
        reserve = max(self._assumed_cost_usd, self._dearest_call)
        remaining = self._budget_usd - self._spent
        if remaining < reserve:
            raise BudgetExhausted(
                f"image budget of ${self._budget_usd:.4f} is spent "
                f"(${self._spent:.4f} so far, reserving ${reserve:.4f} per call); "
                "skipping the rest"
            )

        prompt = build_prompt(self._template, headline=headline, dek=dek, category=category)
        payload: dict[str, object] = {
            "model": self._model,
            "prompt": prompt,
            "n": 1,
            "aspect_ratio": self._aspect_ratio,
        }
        # Only the OpenAI image endpoints take a quality tier. Models without the
        # knob ignore it per OpenRouter's docs, but sending `auto` says nothing
        # and is one less field to be wrong about.
        if self._quality != "auto":
            payload["quality"] = self._quality

        body = self._post(payload)
        # Billed here, before anything is parsed out of the body. The call has
        # already happened and is already on the invoice, so every path from
        # this point on must be a path that charged for it.
        #
        # This used to sit after `_decode_first_image`, which meant a billed
        # response carrying missing or malformed image data raised before the
        # spend was recorded. `illustrate` catches that and moves to the next
        # headline, so a model reliably returning junk could be paid for once
        # per headline while the ceiling never moved -- the budget silently not
        # counting exactly the failure it exists to bound.
        cost = _reported_cost(body, fallback=self._assumed_cost_usd)
        self._spent += cost
        self._dearest_call = max(self._dearest_call, cost)

        raw, media_type = _decode_first_image(body)

        data, width, height = transcode(
            raw,
            max_width=self._max_width,
            max_bytes=self._max_bytes,
            quality=self._webp_quality,
        )
        del media_type  # what came in; what goes to Postgres is always WebP now
        return RenderedImage(
            data=data,
            mime="image/webp",
            width=width,
            height=height,
            model=self._model,
            prompt=prompt,
            cost_usd=cost,
        )

    def _post(self, payload: dict[str, object]) -> dict:
        last: Exception | None = None
        for attempt in range(self._max_retries + 1):
            if attempt:
                self._sleep(2.0**attempt)
            try:
                response = self._http.post(IMAGE_URL, headers=self._headers, json=payload)
            except httpx.HTTPError as exc:
                last = ImageError(f"request to OpenRouter failed: {exc}")
                continue

            if response.status_code in _RETRY_STATUSES:
                last = ImageError(
                    f"OpenRouter returned HTTP {response.status_code}: {response.text[:200]}"
                )
                continue
            if response.status_code == 401:
                # Terminal, not merely un-retried: neither this transport's
                # retry loop nor the next headline can make a rejected key work.
                raise ProviderRefused("OpenRouter rejected the API key (401)")
            if response.status_code == 402:
                raise ProviderRefused("OpenRouter reports insufficient credit (402)")
            if response.status_code >= 400:
                raise ImageError(
                    f"OpenRouter returned HTTP {response.status_code}: {response.text[:200]}"
                )

            try:
                body = response.json()
            except ValueError as exc:
                last = ImageError(f"OpenRouter returned a non-JSON body: {exc}")
                continue

            # A 200 can still carry an error object rather than an image.
            error = body.get("error") if isinstance(body, dict) else None
            if error:
                message = error.get("message") if isinstance(error, dict) else str(error)
                raise ImageError(f"OpenRouter returned an error: {message}")
            if not isinstance(body, dict):
                last = ImageError("OpenRouter returned a body that is not an object")
                continue
            return body

        assert last is not None
        raise last


def _decode_first_image(body: dict) -> tuple[bytes, str | None]:
    data = body.get("data")
    if not isinstance(data, list) or not data:
        raise ImageError("OpenRouter returned no images")
    first = data[0]
    if not isinstance(first, dict):
        raise ImageError("OpenRouter returned a malformed image entry")

    encoded = first.get("b64_json")
    if not isinstance(encoded, str) or not encoded:
        raise ImageError("OpenRouter returned an image with no b64_json payload")
    try:
        # validate=True so stray characters are an error rather than silently
        # discarded bytes that Pillow then fails to open with a worse message.
        raw = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ImageError(f"could not decode the returned image: {exc}") from exc
    if not raw:
        raise ImageError("OpenRouter returned an empty image")

    media_type = first.get("media_type")
    return raw, media_type if isinstance(media_type, str) else None


def _reported_cost(body: dict, *, fallback: float) -> float:
    """What this call actually cost, or the configured worst case.

    Falling back to `0.0` on a missing or unparseable `usage.cost` would make the
    budget stop counting at exactly the moment it stopped being able to see the
    bill -- which is the wrong direction to fail in.
    """
    usage = body.get("usage")
    if isinstance(usage, dict):
        cost = usage.get("cost")
        if isinstance(cost, int | float) and cost >= 0:
            return float(cost)
    return fallback
