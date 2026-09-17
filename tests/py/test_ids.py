"""The identifier scheme, especially its one awkward boundary."""

from __future__ import annotations

import random

import pytest

from generator.arxiv import ids


class TestDigitWidth:
    def test_the_1412_to_1501_boundary(self):
        # The whole reason this module exists. One month apart, different widths,
        # and a mistake here produces identifiers that can never match anything --
        # indistinguishable from "that paper does not exist", forever.
        assert ids.digits_for(1412) == 4
        assert ids.digits_for(1501) == 5

    def test_the_start_of_the_scheme(self):
        assert ids.digits_for(704) == 4
        with pytest.raises(ValueError):
            ids.digits_for(703)  # old-style territory

    @pytest.mark.parametrize("yymm", [704, 1001, 1412])
    def test_four_digit_era(self, yymm):
        assert ids.digits_for(yymm) == 4

    @pytest.mark.parametrize("yymm", [1501, 2001, 2609])
    def test_five_digit_era(self, yymm):
        assert ids.digits_for(yymm) == 5


class TestFormatting:
    def test_pads_to_the_era_width(self):
        assert ids.format_id(1412, 1) == "1412.0001"
        assert ids.format_id(1501, 1) == "1501.00001"
        assert ids.format_id(2609, 12345) == "2609.12345"


class TestValidation:
    @pytest.mark.parametrize(
        "identifier",
        ["0704.0001", "1412.9999", "1501.00001", "2609.12345", "2401.01234v3"],
    )
    def test_accepts_well_formed(self, identifier):
        assert ids.is_valid_new_style(identifier)

    @pytest.mark.parametrize(
        ("identifier", "why"),
        [
            ("1412.00001", "five digits before the boundary"),
            ("1501.0001", "four digits after the boundary"),
            ("0703.0001", "predates the new scheme"),
            ("0700.0001", "month zero"),
            ("0713.0001", "month thirteen"),
            ("1501.00000", "sequence zero"),
            ("hep-th/9901001", "old style is a non-goal"),
            ("nonsense", "not an identifier"),
            ("", "empty"),
        ],
    )
    def test_rejects_malformed(self, identifier, why):
        # Local validation is the ONLY defence: a malformed id_list entry comes
        # back as HTTP 200 with an empty feed, shaped exactly like a real miss.
        assert not ids.is_valid_new_style(identifier), why


class TestSampling:
    def test_every_candidate_is_valid(self):
        rng = random.Random(1234)
        for candidate in ids.sample_candidates(500, 2609, rng):
            assert ids.is_valid_new_style(candidate), candidate

    def test_spans_both_eras(self):
        rng = random.Random(99)
        candidates = ids.sample_candidates(600, 2609, rng)
        widths = {len(c.split(".")[1]) for c in candidates}
        assert widths == {4, 5}

    def test_is_deterministic_for_a_seed(self):
        assert ids.sample_candidates(20, 2609, random.Random(7)) == ids.sample_candidates(
            20, 2609, random.Random(7)
        )

    def test_returns_no_duplicates(self):
        candidates = ids.sample_candidates(300, 2609, random.Random(3))
        assert len(set(candidates)) == len(candidates)

    def test_months_in_range_starts_at_the_scheme_boundary(self):
        months = ids.months_in_range(1502)
        assert months[0] == 704
        assert months[-1] == 1502
        assert 1412 in months and 1501 in months
        assert 1413 not in months  # no thirteenth month


class TestVersionSuffix:
    """A malformed id_list entry returns an empty feed, shaped exactly like a
    real miss -- so anything not rejected locally is invisible for the rest of
    the run."""

    def test_accepts_real_version_suffixes(self):
        assert ids.is_valid_new_style("2401.01234v1")
        assert ids.is_valid_new_style("2401.01234v7")

    def test_rejects_version_zero(self):
        # The suffix was captured by the regex and never validated, so this was
        # accepted and sent to arXiv, which cannot tell us it is malformed.
        assert not ids.is_valid_new_style("2401.01234v0")
        assert not ids.is_valid_new_style("2401.01234v00")
