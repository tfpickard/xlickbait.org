"""Illustrations: the transcode budget, the spend ceiling, and failing quietly.

Every test here runs against `httpx.MockTransport` and Pillow. Nothing reaches
OpenRouter, and no API key is needed.
"""

from __future__ import annotations

import base64
import io
import json
from collections.abc import Callable

import httpx
import pytest
from PIL import Image

from generator.image import (
    BudgetExhausted,
    ImageError,
    ImagePainter,
    ProviderRefused,
    TerminalImageError,
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
        "model": "microsoft/mai-image-2.6-flash",
        "style": "terse",
        "aspect_ratio": "3:2",
        "quality": "auto",
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

    @pytest.mark.parametrize("style", ["terse", "tabloid", "photo"])
    def test_every_style_file_exists_and_names_the_headline(self, style):
        assert "{{headline}}" in load_style(style)

    def test_the_default_style_stays_short(self):
        # The one prompt with evidence behind it is one line long, and that is
        # not incidental: a long brief dilutes the instruction. If someone grows
        # this into an essay, it should be a deliberate decision that also
        # updates this number, not a drift.
        assert len(load_style("terse").split()) < 60

    def test_the_default_style_states_its_guardrails_positively(self):
        """A prohibition conditions on the thing it forbids.

        This checks word-boundary negations rather than an allowlist of exact
        phrases. The allowlist version passed while the file said "cropped so no
        face is legible" and "invented props, not data" -- negating the two
        things the guardrails most wanted absent, which is the precise failure
        the rule exists to avoid, sitting inside the prompt that claims to
        follow it.
        """
        import re

        terse = load_style("terse").lower()
        found = re.findall(
            r"\b(no|not|never|without|avoid|avoids|exclude|excludes|omit|omits|nothing|none)\b",
            terse,
        )
        assert found == [], f"the default prompt negates rather than describes: {found}"

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
        assert image.model == "microsoft/mai-image-2.6-flash"
        assert "Baffled" in image.prompt

    def test_sends_the_configured_generation_parameters(self):
        seen: list[dict] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(json.loads(request.content))
            return httpx.Response(200, json=ok_body(png_bytes(600, 400)))

        with painter_for(handler, aspect_ratio="16:9", quality="medium") as painter:
            painter.paint(headline="H", dek="D", category="C")

        assert seen[0]["model"] == "microsoft/mai-image-2.6-flash"
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
        # This used to assert a SECOND call went through and left the run at
        # $0.10 against an $0.08 budget -- the ceiling overshooting because it
        # kept reserving the $0.01 assumption after the model had already
        # charged $0.05. Reserving the dearest call seen stops it at one.
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=ok_body(png_bytes(600, 400), cost=0.05))

        with painter_for(handler, budget_usd=0.08, assumed_cost_usd=0.01) as painter:
            painter.paint(headline="H", dek="D", category="C")
            assert painter.spent_usd == pytest.approx(0.05)
            with pytest.raises(BudgetExhausted):
                painter.paint(headline="H", dek="D", category="C")
            assert painter.spent_usd <= 0.08, "the ceiling must not be passed once it is known"

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


class TestTheBudgetCountsEveryBilledCall:
    """Regression: the spend was recorded after the response was decoded.

    A billed response carrying missing or malformed image data raised before
    `_spent` moved, and `illustrate` catches that and continues -- so a model
    reliably returning junk could be paid for once per headline while the
    ceiling stayed exactly where it started.
    """

    def _handler(self, body: dict) -> Callable[[httpx.Request], httpx.Response]:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=body)

        return handler

    @pytest.mark.parametrize(
        "body",
        [
            {"data": [], "usage": {"cost": 0.02}},
            {"data": [{"b64_json": ""}], "usage": {"cost": 0.02}},
            {"data": [{"b64_json": "not base64!!!"}], "usage": {"cost": 0.02}},
            {
                "data": [{"b64_json": base64.b64encode(b"not an image").decode()}],
                "usage": {"cost": 0.02},
            },
        ],
    )
    def test_a_billed_response_is_charged_even_when_it_cannot_be_used(self, body):
        with painter_for(self._handler(body)) as painter:
            with pytest.raises(ImageError):
                painter.paint(headline="H", dek="D", category="C")
            assert painter.spent_usd == pytest.approx(0.02), (
                "OpenRouter billed for this call; the ceiling has to know about it"
            )

    def test_repeated_junk_eventually_exhausts_the_budget(self):
        # The failure this ordering bug allowed: an unbounded number of paid
        # calls, because the loop that catches ImageError never saw the spend.
        body = {"data": [{"b64_json": "not base64!!!"}], "usage": {"cost": 0.02}}
        with painter_for(self._handler(body), budget_usd=0.05, assumed_cost_usd=0.01) as painter:
            for _ in range(3):
                with pytest.raises(ImageError):
                    painter.paint(headline="H", dek="D", category="C")
            with pytest.raises(BudgetExhausted):
                painter.paint(headline="H", dek="D", category="C")


class TestTerminalFailuresStopTheRun:
    """Regression: 401/402 were per-headline, so a bad key cost one call each.

    The transport already declines to retry them, on the reasoning that nothing
    about a rejected key changes. `illustrate` then caught the plain
    `ImageError` and moved to the next target, re-issuing the identical request
    for every headline in the batch — undoing that reasoning one level out.
    """

    @pytest.mark.parametrize("status", [401, 402])
    def test_a_refused_provider_is_terminal(self, status):
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(status)

        with painter_for(handler) as painter, pytest.raises(ProviderRefused):
            painter.paint(headline="H", dek="D", category="C")

    @pytest.mark.parametrize("status", [401, 402])
    def test_terminal_errors_are_still_image_errors(self, status):
        # They must never abort a publish: `illustrate` has to be able to catch
        # them, and a publish is already committed by the time it runs.
        assert issubclass(ProviderRefused, ImageError)
        assert issubclass(BudgetExhausted, TerminalImageError)
        assert issubclass(TerminalImageError, ImageError)
        del status

    def test_an_ordinary_failure_is_not_terminal(self):
        # A malformed body is this headline's problem, not the run's.
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"data": []})

        with painter_for(handler) as painter:
            try:
                painter.paint(headline="H", dek="D", category="C")
            except TerminalImageError:  # pragma: no cover - the failure case
                pytest.fail("a bad response body must not end the whole run")
            except ImageError:
                pass


class TestTheOvershootIsBounded:
    def test_reserves_the_dearest_call_seen_rather_than_the_assumption(self):
        # The ceiling is necessarily soft -- a call's price is only known once
        # it has been billed -- so a run can exceed the budget by the call in
        # flight. What it must not do is keep under-reserving after the model
        # has already proved the assumption wrong.
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=ok_body(png_bytes(600, 400), cost=0.12))

        with painter_for(handler, budget_usd=0.25, assumed_cost_usd=0.01) as painter:
            painter.paint(headline="H", dek="D", category="C")
            painter.paint(headline="H", dek="D", category="C")
            assert painter.spent_usd == pytest.approx(0.24)
            # Reserving 0.01 would admit a third call and land at 0.36, well past
            # the budget. Reserving the observed 0.12 stops here.
            with pytest.raises(BudgetExhausted, match="reserving"):
                painter.paint(headline="H", dek="D", category="C")
