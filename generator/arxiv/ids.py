"""The new-style arXiv identifier scheme.

    YYMM.NNNN    for 0704 through 1412   (four digits)
    YYMM.NNNNN   from 1501 onward        (five digits)

Old-style identifiers (`hep-th/9901001`) are a non-goal.

The boundary matters: 1412 and 1501 are one month apart and have different digit
counts, so an off-by-one there produces identifiers that are always invalid --
and because the API returns an empty feed rather than an error for a malformed
id, the failure would look exactly like "that paper does not exist" forever.
"""

from __future__ import annotations

import random
import re

# First month of the new scheme.
FIRST_YYMM = 704
# Last month using four digits. From 1501 on, five.
LAST_FOUR_DIGIT_YYMM = 1412
FIRST_FIVE_DIGIT_YYMM = 1501

_NEW_STYLE = re.compile(r"^(\d{2})(\d{2})\.(\d{4,5})(v\d+)?$")


def digits_for(yymm: int) -> int:
    """How many digits the sequence number has for a given YYMM."""
    if yymm < FIRST_YYMM:
        raise ValueError(f"{yymm:04d} predates the new identifier scheme (starts 0704)")
    return 4 if yymm <= LAST_FOUR_DIGIT_YYMM else 5


def is_valid_new_style(identifier: str) -> bool:
    """Validate locally, because arXiv will not tell us.

    A malformed `id_list` entry returns HTTP 200 with an empty feed -- shaped
    identically to a well-formed identifier that simply does not exist. Anything
    not caught here is indistinguishable from a miss for the rest of the run.
    """
    match = _NEW_STYLE.match(identifier)
    if not match:
        return False
    year, month, sequence = match.group(1), match.group(2), match.group(3)
    if not 1 <= int(month) <= 12:
        return False
    yymm = int(year) * 100 + int(month)
    if yymm < FIRST_YYMM:
        return False
    if len(sequence) != digits_for(yymm):
        return False
    # The version suffix was captured and never checked, so "2401.01234v0" was
    # accepted. arXiv versions start at v1, so v0 is malformed -- and a malformed
    # entry in id_list comes back as an empty feed, shaped exactly like a real
    # miss. Catching it here is the whole reason this function exists.
    version = match.group(4)
    if version is not None and int(version[1:]) < 1:
        return False
    return int(sequence) >= 1


def format_id(yymm: int, sequence: int) -> str:
    width = digits_for(yymm)
    return f"{yymm:04d}.{sequence:0{width}d}"


def months_in_range(newest_yymm: int) -> list[int]:
    """Every valid YYMM from 0704 up to and including `newest_yymm`."""
    months: list[int] = []
    year, month = FIRST_YYMM // 100, FIRST_YYMM % 100
    while year * 100 + month <= newest_yymm:
        months.append(year * 100 + month)
        month += 1
        if month > 12:
            year, month = year + 1, 1
    return months


def sample_candidates(
    count: int,
    newest_yymm: int,
    rng: random.Random,
    *,
    max_sequence_four: int = 2000,
    max_sequence_five: int = 12000,
) -> list[str]:
    """Sample plausible identifiers uniformly across months.

    The sequence ceilings are deliberately conservative. arXiv's monthly volume
    has grown by more than an order of magnitude since 2007, so sampling
    uniformly over the full five-digit space would miss on almost every draw for
    older months. Guessing low costs a few extra misses; guessing high wastes
    most of the sampling budget. Every candidate is verified against the API
    regardless -- these bounds only decide how often a draw is worth spending a
    request on.
    """
    months = months_in_range(newest_yymm)
    if not months:
        raise ValueError(f"no valid months up to {newest_yymm}")

    seen: set[str] = set()
    out: list[str] = []
    while len(out) < count:
        yymm = rng.choice(months)
        ceiling = max_sequence_four if digits_for(yymm) == 4 else max_sequence_five
        candidate = format_id(yymm, rng.randint(1, ceiling))
        if candidate in seen:
            continue
        seen.add(candidate)
        out.append(candidate)
    return out
