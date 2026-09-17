"""The truth gate.

Every headline claims a span of the paper -- the `anchor` -- and the whole
conceit depends on that span being real. The headline's inference is absurd; its
facts are not. If the anchor is paraphrased, the joke stops being technically
true and becomes a lie about someone's work.

So: the anchor must appear VERBATIM in the title or abstract, compared after
whitespace and case normalisation and NOTHING ELSE.

That "nothing else" is deliberate and is not a detail to soften later. Folding
curly quotes to straight ones, or en dashes to hyphens, would let a model that
silently "tidied" a quotation through the gate -- and a model that tidies
punctuation is a model that is retyping rather than copying, which is exactly
the behaviour this exists to catch. A rejection here is the gate working. The
rejection counter in `generator_runs` is how we find out if it happens often.
"""

from __future__ import annotations

import re

_WHITESPACE = re.compile(r"\s+")


def normalise(text: str) -> str:
    """Collapse whitespace runs and case-fold. Nothing else."""
    return _WHITESPACE.sub(" ", text).strip().casefold()


def anchor_is_supported(anchor: str, title: str, abstract: str) -> bool:
    """True when `anchor` appears verbatim in the title or abstract."""
    needle = normalise(anchor)
    if not needle:
        return False
    haystack = f"{normalise(title)} {normalise(abstract)}"
    return needle in haystack
