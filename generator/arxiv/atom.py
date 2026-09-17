"""Parse arXiv's Atom responses.

Uses the standard library rather than a dependency. The feed is a fixed shape
and the only tricky parts are arXiv-specific: identifiers carry versions,
withdrawal is not a structured field, and a partial miss in a batched `id_list`
is completely silent.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from xml.etree import ElementTree

ATOM = "http://www.w3.org/2005/Atom"
ARXIV = "http://arxiv.org/schemas/atom"
OPENSEARCH = "http://a9.com/-/spec/opensearch/1.1/"

_NS = {"a": ATOM, "arxiv": ARXIV, "os": OPENSEARCH}

# Matches the identifier and optional version in an entry <id> such as
# http://arxiv.org/abs/2608.21129v2
_ENTRY_ID = re.compile(r"/abs/(?P<id>[^v\s]+(?:/\d+)?)(?:v(?P<version>\d+))?$")


class AtomError(RuntimeError):
    """arXiv returned an error feed."""


@dataclass(frozen=True)
class Paper:
    arxiv_id: str
    version: int
    title: str
    abstract: str
    authors: list[str]
    primary_category: str
    categories: list[str]
    published_at: datetime
    abs_url: str
    comment: str | None

    @property
    def is_withdrawn(self) -> bool:
        return looks_withdrawn(self.comment, self.version)


def _text(node: ElementTree.Element | None) -> str:
    return " ".join((node.text or "").split()) if node is not None else ""


def _parse_timestamp(raw: str) -> datetime:
    # Live responses use the Z form (2026-09-15T17:55:28Z); the documentation
    # shows an offset form. Accept both.
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))


# Withdrawal has no structured field anywhere in the API -- the only signal is
# free text in <arxiv:comment>, and the wording is not standardised.
_WITHDRAWAL = re.compile(
    r"^(?:(?:this|the|our|my)\s+)?"
    r"(?:paper|manuscript|submission|article|work|preprint|entry|version|draft)?\s*"
    r"(?:(?:has|have)\s+been\s+|is\s+|was\s+|been\s+)?"
    r"withdrawn\b",
    re.IGNORECASE,
)


def looks_withdrawn(comment: str | None, version: int) -> bool:
    """Best-effort withdrawal detection. Deliberately conservative.

    Two rules, both earning their place:

    * Version must be at least 2. A withdrawal is always a new version, so a v1
      cannot be withdrawn.
    * The phrase must appear at the START of the comment. Anchoring is what
      excludes the real false positive in the corpus -- "This manuscript
      supersedes arXiv:2510.26642, which has been withdrawn with the agreement
      of all its authors." describes a *different* paper's withdrawal, and a
      substring search would wrongly discard a perfectly live one.
    """
    if version < 2 or not comment:
        return False
    return _WITHDRAWAL.match(comment.strip()) is not None


def parse_feed(xml: str) -> list[Paper]:
    """Parse a feed into papers, raising on an arXiv error entry."""
    root = ElementTree.fromstring(xml)

    papers: list[Paper] = []
    for entry in root.findall("a:entry", _NS):
        raw_id = _text(entry.find("a:id", _NS))

        # An error is delivered as a normal-looking entry whose id points at
        # /api/errors -- HTTP status alone does not tell you.
        if "/api/errors" in raw_id:
            raise AtomError(_text(entry.find("a:summary", _NS)) or "arXiv returned an error entry")

        match = _ENTRY_ID.search(raw_id)
        if not match:
            continue
        arxiv_id = match.group("id")
        version = int(match.group("version") or 1)

        primary = entry.find("arxiv:primary_category", _NS)
        # Live responses emit only term=, with no scheme=, contrary to the docs.
        primary_category = primary.get("term", "") if primary is not None else ""
        categories = [c.get("term", "") for c in entry.findall("a:category", _NS) if c.get("term")]

        abs_url = f"https://arxiv.org/abs/{arxiv_id}"
        for link in entry.findall("a:link", _NS):
            if link.get("rel") == "alternate" and link.get("href"):
                abs_url = link.get("href", abs_url).replace("http://", "https://")

        comment_node = entry.find("arxiv:comment", _NS)
        papers.append(
            Paper(
                arxiv_id=arxiv_id,
                version=version,
                title=_text(entry.find("a:title", _NS)),
                abstract=_text(entry.find("a:summary", _NS)),
                authors=[_text(a.find("a:name", _NS)) for a in entry.findall("a:author", _NS)],
                primary_category=primary_category or (categories[0] if categories else ""),
                categories=categories or ([primary_category] if primary_category else []),
                published_at=_parse_timestamp(_text(entry.find("a:published", _NS))),
                abs_url=abs_url,
                comment=_text(comment_node) or None if comment_node is not None else None,
            )
        )
    return papers


def reconcile(requested: list[str], returned: list[Paper]) -> tuple[list[Paper], list[str]]:
    """Split a batched id_list response into hits and misses.

    Necessary because a partial miss is SILENT: `totalResults` simply drops and
    the absent identifiers are not mentioned anywhere in the response. Without
    reconciling against what was asked for, a run cannot tell forty-nine hits
    from fifty.

    Version suffixes are stripped for comparison, since a request for `2401.1`
    comes back as `2401.1v3`.
    """
    found = {paper.arxiv_id: paper for paper in returned}
    hits = [found[identifier] for identifier in requested if identifier in found]
    misses = [identifier for identifier in requested if identifier not in found]
    return hits, misses
