"""Illustrations: the transcode budget, the spend ceiling, and failing quietly.

Every test here runs against `httpx.MockTransport` and Pillow. Nothing reaches
OpenRouter, and no API key is needed.
"""

from __future__ import annotations

import base64
import io
import json

import httpx
import pytest
from PIL import Image

from generator.image import (
    BudgetExhausted,
    ImageError,
    ImagePainter,
    build_prompt,
    load_style,
    transcode,
)


def png_bytes(width: int = 1600, height: int = 1067, *, noisy: bool = False) -> bytes:
    """A PNG of the rough shape an image model returns."""
    image = Image.new("RGB", (width, height), (30, 20, 60))
    if noisy:
        # Flat colour compresses to almost nothing, which would make every
        # size-ceiling test below vacuous. A gradient with grain compresses
        # roughly the way a photograph does, which is what the ceiling is
        # actually sized against.
        import random

        rng = random.Random(7)
        pixels = image.load()
        assert pixels is not None
        for y in range(height):
            base = (40 + 180 * y // height, 60 + 120 * y // height, 200 - 120 * y // height)
            for x in range(width):
                shade = 60 * x // width
                pixels[x, y] = tuple(
                    max(0, min(255, channel + shade + rng.randrange(-28, 29))) for channel in base
                )
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def ok_body(raw: bytes, *, cost: float | None = 0.002) -> dict:
    body: dict = {
        "created": 1,
        "data": [{"b64_json": base64.b64encode(raw).decode(), "media_type": "image/png"}],
    }
    if cost is not None:
        body["usage"] = {"prompt_tokens": 0, "completion_tokens": 272, "cost": cost}
    return body


def painter_for(handler, **overrides) -> ImagePainter:
    settings: dict = {
        "api_key": "test-key",
        "model": "openai/gpt-image-1-mini",
        "style": "tabloid",
        "aspect_ratio": "3:2",
        "quality": "low",
        "max_width": 1200,
        "max_bytes": 400_000,
        "webp_quality": 82,
        "budget_usd": 0.25,
        "assumed_cost_usd": 0.01,
        # Nothing here may actually sleep: a retry test that waits six seconds is
        # a test nobody runs.
        "sleep": lambda _seconds: None,
    }
    settings.update(overrides)
    return ImagePainter(client=httpx.Client(transport=httpx.MockTransport(handler)), **settings)


class TestPromptBuilding:
    def test_substitutes_the_three_tokens(self):
        template = "H: {{headline}} / D: {{dek}} / C: {{category}}"
        out = build_prompt(template, headline="Baffled", dek="Utterly.", category="hep-ex")
        assert out == "H: Baffled / D: Utterly. / C: hep-ex"

    def test_braces_and_dollars_in_the_prose_survive(self):
        # The reason this is a literal replace rather than str.format or
        # string.Template: the art direction is English about typography, and
        # both of those mechanisms assign meaning to characters prose contains.
        template = "Set {a caption} in $20 type. {{headline}}"
        out = build_prompt(template, headline="X", dek="Y", category="Z")
        assert out == "Set {a caption} in $20 type. X"

    def test_collapses_whitespace_and_clips_long_input(self):
        out = build_prompt("{{headline}}", headline="a\n\n  b" + "c" * 500, dek="", category="")
        assert out.startswith("a bc")
        assert "\n" not in out
        assert len(out) <= 240

    def test_unknown_style_is_a_startup_failure_not_a_silent_default(self):
        with pytest.raises(SystemExit):
            load_style("nonexistent")

    @pytest.mark.parametrize("style", ["tabloid", "photo"])
    def test_every_style_file_exists_and_carries_all_three_tokens(self, style):
        template = load_style(style)
        for token in ("{{headline}}", "{{dek}}", "{{category}}"):
            assert token in template

    def test_the_photo_style_forbids_lettering(self):
        # The whole reason that style exists. If this instruction is ever edited
        # away the style is just a worse tabloid.
        assert "NO TEXT AT ALL" in load_style("photo")


class TestTranscode:
    def test_re_encodes_to_webp_and_downscales(self):
        data, width, height = transcode(
            png_bytes(1600, 1067), max_width=1200, max_bytes=400_000, quality=82
        )
        assert data[:4] == b"RIFF" and data[8:12] == b"WEBP"
        assert width == 1200
        # Aspect ratio preserved, give or take the rounding.
        assert abs(height - 800) <= 2

    def test_leaves_an_already_small_image_at_its_own_size(self):
        _, width, height = transcode(
            png_bytes(600, 400), max_width=1200, max_bytes=400_000, quality=82
        )
        assert (width, height) == (600, 400)

    def test_walks_quality_down_to_meet_the_ceiling(self):
        # Stated as a comparison rather than against a fixed byte count, so the
        # test says "a tighter ceiling really does cost quality" instead of
        # pinning whatever libwebp happens to emit this version.
        raw = png_bytes(1200, 800, noisy=True)
        generous, _, _ = transcode(raw, max_width=1200, max_bytes=400_000, quality=95)
        tight, _, _ = transcode(raw, max_width=1200, max_bytes=150_000, quality=95)

        assert len(generous) > 150_000, "fixture is too compressible to exercise the walk"
        assert len(tight) <= 150_000
        assert len(tight) < len(generous)

    def test_rejects_rather_than_storing_something_oversized(self):
        # The database is the reason. "Just this once" is how it fills up.
        with pytest.raises(ImageError, match="could not fit"):
            transcode(png_bytes(1200, 800, noisy=True), max_width=1200, max_bytes=2_000, quality=90)

    def test_rejects_bytes_that_are_not_an_image(self):
        with pytest.raises(ImageError, match="Pillow cannot read"):
            transcode(b"this is not a png", max_width=1200, max_bytes=400_000, quality=82)


class TestPainting:
    def test_returns_webp_whatever_the_model_sent(self):
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=ok_body(png_bytes()))

        with painter_for(handler) as painter:
            image = painter.paint(headline="Baffled", dek="Utterly.", category="hep-ex")

        assert image.mime == "image/webp"
        assert image.data[8:12] == b"WEBP"
        assert image.width == 1200
        assert image.model == "openai/gpt-image-1-mini"
        assert "Baffled" in image.prompt

    def test_sends_the_configured_generation_parameters(self):
        seen: list[dict] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(json.loads(request.content))
            return httpx.Response(200, json=ok_body(png_bytes(600, 400)))

        with painter_for(handler, aspect_ratio="16:9", quality="medium") as painter:
            painter.paint(headline="H", dek="D", category="C")

        assert seen[0]["model"] == "openai/gpt-image-1-mini"
        assert seen[0]["aspect_ratio"] == "16:9"
        assert seen[0]["quality"] == "medium"
        assert seen[0]["n"] == 1

    def test_quality_auto_sends_no_quality_field(self):
        seen: list[dict] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(json.loads(request.content))
            return httpx.Response(200, json=ok_body(png_bytes(600, 400)))

        with painter_for(handler, quality="auto") as painter:
            painter.paint(headline="H", dek="D", category="C")

        assert "quality" not in seen[0]

    def test_authorises_with_the_key(self):
        seen: list[httpx.Headers] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request.headers)
            return httpx.Response(200, json=ok_body(png_bytes(600, 400)))

        with painter_for(handler) as painter:
            painter.paint(headline="H", dek="D", category="C")

        assert seen[0]["authorization"] == "Bearer test-key"


class TestFailureModes:
    def test_a_200_carrying_an_error_object_is_an_error(self):
        # OpenRouter can answer 200 with an error body rather than an image.
        # Treating that as success means base64-decoding None.
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"error": {"code": 400, "message": "bad prompt"}})

        with painter_for(handler) as painter, pytest.raises(ImageError, match="bad prompt"):
            painter.paint(headline="H", dek="D", category="C")

    def test_no_images_in_the_response(self):
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"created": 1, "data": []})

        with painter_for(handler) as painter, pytest.raises(ImageError, match="no images"):
            painter.paint(headline="H", dek="D", category="C")

    def test_undecodable_base64(self):
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"data": [{"b64_json": "not base64!!!"}]})

        with painter_for(handler) as painter, pytest.raises(ImageError, match="could not decode"):
            painter.paint(headline="H", dek="D", category="C")

    def test_a_rejected_key_is_not_retried(self):
        # Retrying a 401 cannot help and burns the retry budget discovering that
        # once per headline.
        calls = []

        def handler(_request: httpx.Request) -> httpx.Response:
            calls.append(1)
            return httpx.Response(401, json={"error": {"message": "no"}})

        with painter_for(handler) as painter, pytest.raises(ImageError, match="401"):
            painter.paint(headline="H", dek="D", category="C")
        assert len(calls) == 1

    def test_insufficient_credit_is_not_retried(self):
        calls = []

        def handler(_request: httpx.Request) -> httpx.Response:
            calls.append(1)
            return httpx.Response(402)

        with painter_for(handler) as painter, pytest.raises(ImageError, match="402"):
            painter.paint(headline="H", dek="D", category="C")
        assert len(calls) == 1

    def test_a_429_is_retried_and_can_succeed(self):
        calls = []

        def handler(_request: httpx.Request) -> httpx.Response:
            calls.append(1)
            if len(calls) == 1:
                return httpx.Response(429)
            return httpx.Response(200, json=ok_body(png_bytes(600, 400)))

        with painter_for(handler) as painter:
            image = painter.paint(headline="H", dek="D", category="C")
        assert len(calls) == 2
        assert image.mime == "image/webp"

    def test_gives_up_after_the_retry_budget(self):
        calls = []

        def handler(_request: httpx.Request) -> httpx.Response:
            calls.append(1)
            return httpx.Response(503)

        with painter_for(handler, max_retries=2) as painter, pytest.raises(ImageError):
            painter.paint(headline="H", dek="D", category="C")
        assert len(calls) == 3


class TestTheSpendCeiling:
    def test_stops_once_the_budget_is_gone(self):
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=ok_body(png_bytes(600, 400), cost=0.05))

        with painter_for(handler, budget_usd=0.08, assumed_cost_usd=0.01) as painter:
            painter.paint(headline="H", dek="D", category="C")
            painter.paint(headline="H", dek="D", category="C")
            assert painter.spent_usd == pytest.approx(0.10)
            with pytest.raises(BudgetExhausted):
                painter.paint(headline="H", dek="D", category="C")

    def test_a_missing_cost_bills_the_assumed_worst_case_not_zero(self):
        # A budget that assumes free whenever it cannot see the bill is not a
        # budget; it is an unbounded loop with a number attached.
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=ok_body(png_bytes(600, 400), cost=None))

        with painter_for(handler, budget_usd=0.05, assumed_cost_usd=0.02) as painter:
            painter.paint(headline="H", dek="D", category="C")
            assert painter.spent_usd == pytest.approx(0.02)

    def test_a_zero_budget_never_calls_the_api_at_all(self):
        calls = []

        def handler(_request: httpx.Request) -> httpx.Response:
            calls.append(1)
            return httpx.Response(200, json=ok_body(png_bytes(600, 400)))

        with painter_for(handler, budget_usd=0.0) as painter, pytest.raises(BudgetExhausted):
            painter.paint(headline="H", dek="D", category="C")
        assert calls == []
