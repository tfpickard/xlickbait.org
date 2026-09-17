"""Purge Netlify's CDN cache by tag after a successful run.

The single most dangerous call in this codebase, for a reason that is not
obvious from the endpoint's shape. Netlify's documentation, verbatim:

    "If you don't specify a list of cache_tags, the entire site will be purged.
     However, if you specify an empty list of cache_tags, no purge will be
     applied."

So the difference between "this run published nothing, do nothing" and
"invalidate the entire site" is whether a key is present in a JSON object. A run
whose tag set computes to empty must therefore not send a request at all -- the
guard is `if not tags: return`, and it is the reason this module exists rather
than the three lines it would otherwise be.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable

import httpx

PURGE_URL = "https://api.netlify.com/api/v1/purge"

# "Each cache tag or site can only be purged twice every 5 seconds."
_BATCH_PAUSE_SECONDS = 3.0
_MAX_TAGS_PER_REQUEST = 100


class PurgeError(RuntimeError):
    """A purge failed in a way that needs a human."""


def purge(
    tags: Iterable[str],
    *,
    token: str,
    site_id: str,
    client: httpx.Client | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    """Purge the given cache tags. Returns the number of requests made.

    Never sends a request with no tags: an absent `cache_tags` key purges the
    whole site, and this function must not be one typo away from that.
    """
    unique = sorted({tag for tag in tags if tag})
    if not unique:
        # Nothing published, nothing to invalidate. Emphatically not "purge all".
        return 0

    owned = client is None
    http = client or httpx.Client(timeout=httpx.Timeout(30.0))
    requests_made = 0
    try:
        batches = [
            unique[i : i + _MAX_TAGS_PER_REQUEST]
            for i in range(0, len(unique), _MAX_TAGS_PER_REQUEST)
        ]
        for index, batch in enumerate(batches):
            if index:
                sleep(_BATCH_PAUSE_SECONDS)
            response = http.post(
                PURGE_URL,
                headers={"Authorization": f"Bearer {token}"},
                json={"site_id": site_id, "cache_tags": batch},
            )
            requests_made += 1

            if response.status_code == 404:
                # A wrong site id. Retrying cannot help, and silently continuing
                # would mean content that never updates with no error anywhere.
                raise PurgeError(
                    f"Netlify returned 404 for site_id {site_id!r}. Check NETLIFY_SITE_ID -- "
                    "this is a configuration error, not a transient failure."
                )
            if response.status_code == 401:
                raise PurgeError(
                    "Netlify rejected the purge token (401). Personal access tokens are "
                    "invalidated by a password reset."
                )
            if response.status_code >= 400:
                raise PurgeError(
                    f"purge failed: HTTP {response.status_code}: {response.text[:300]}"
                )
    finally:
        if owned:
            http.close()

    return requests_made
