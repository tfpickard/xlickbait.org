"""Cache purging, and the one-character difference that would nuke the site."""

from __future__ import annotations

import httpx
import pytest

from generator.purge import PurgeError, purge


def recorder():
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        seen.append(json.loads(request.content))
        return httpx.Response(202)

    return seen, handler


def client_for(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


class TestTheEmptyTagsFootgun:
    def test_no_tags_sends_NO_REQUEST_AT_ALL(self):
        # Netlify: omitting cache_tags purges the ENTIRE SITE; an empty list
        # purges nothing. A run that published nothing must therefore not make a
        # request, because the safe and the catastrophic call differ only by
        # whether a key is present.
        seen, handler = recorder()
        made = purge([], token="t", site_id="s", client=client_for(handler))
        assert made == 0
        assert seen == []

    def test_tags_that_are_all_empty_strings_also_send_nothing(self):
        seen, handler = recorder()
        made = purge(["", "  ".strip(), ""], token="t", site_id="s", client=client_for(handler))
        assert made == 0
        assert seen == []

    def test_a_real_purge_always_includes_the_cache_tags_key(self):
        seen, handler = recorder()
        purge(["list", "feed"], token="t", site_id="s", client=client_for(handler))
        assert len(seen) == 1
        assert "cache_tags" in seen[0], "a body without cache_tags purges the whole site"
        assert seen[0]["cache_tags"] == ["feed", "list"]
        assert seen[0]["site_id"] == "s"


class TestBehaviour:
    def test_deduplicates_and_sorts(self):
        seen, handler = recorder()
        purge(["list", "feed", "list"], token="t", site_id="s", client=client_for(handler))
        assert seen[0]["cache_tags"] == ["feed", "list"]

    def test_sends_the_bearer_token(self):
        headers: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            headers.append(request.headers.get("authorization", ""))
            return httpx.Response(202)

        purge(["list"], token="secret", site_id="s", client=client_for(handler))
        assert headers == ["Bearer secret"]

    def test_batches_large_tag_sets_and_paces_them(self):
        # "Each cache tag or site can only be purged twice every 5 seconds."
        seen, handler = recorder()
        slept: list[float] = []
        tags = [f"h:{i}" for i in range(250)]
        made = purge(tags, token="t", site_id="s", client=client_for(handler), sleep=slept.append)
        assert made == 3
        assert sum(len(body["cache_tags"]) for body in seen) == 250
        assert len(slept) == 2 and all(s > 0 for s in slept)


class TestFailures:
    def test_404_is_a_configuration_error_not_a_retry(self):
        # A wrong site id. Retrying cannot fix it, and continuing quietly would
        # mean content that never updates with nothing in the logs.
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, text="Not Found")

        with pytest.raises(PurgeError, match="NETLIFY_SITE_ID"):
            purge(["list"], token="t", site_id="wrong", client=client_for(handler))

    def test_401_names_the_likely_cause(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, text="Unauthorized")

        with pytest.raises(PurgeError, match="password reset"):
            purge(["list"], token="stale", site_id="s", client=client_for(handler))

    def test_other_errors_surface_the_body(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, text="slow down")

        with pytest.raises(PurgeError, match="slow down"):
            purge(["list"], token="t", site_id="s", client=client_for(handler))
