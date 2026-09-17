"""The truth gate. The one thing in this project that must not be softened."""

from __future__ import annotations

import pytest

from generator.truth import anchor_is_supported, normalise

TITLE = "A Refined Upper Bound on Neutrino Mass"
ABSTRACT = (
    "We report a refined bound using three years of data from a bolometer array "
    "operated at 10 mK.\nThe detector was  calibrated   fortnightly."
)


class TestNormalisation:
    def test_collapses_whitespace_runs(self):
        assert normalise("a  b\n\tc") == "a b c"

    def test_folds_case(self):
        assert normalise("MiXeD") == "mixed"

    def test_strips_the_ends(self):
        assert normalise("  padded  ") == "padded"


class TestAcceptance:
    def test_accepts_an_exact_span(self):
        assert anchor_is_supported("a bolometer array operated at 10 mK", TITLE, ABSTRACT)

    def test_accepts_a_case_variant(self):
        assert anchor_is_supported("A BOLOMETER ARRAY OPERATED AT 10 MK", TITLE, ABSTRACT)

    def test_accepts_a_whitespace_variant(self):
        assert anchor_is_supported("a bolometer  array   operated at 10 mK", TITLE, ABSTRACT)

    def test_accepts_a_span_crossing_a_newline_in_the_source(self):
        assert anchor_is_supported("calibrated fortnightly", TITLE, ABSTRACT)

    def test_accepts_a_span_from_the_title(self):
        assert anchor_is_supported("Refined Upper Bound", TITLE, ABSTRACT)


class TestRejection:
    @pytest.mark.parametrize(
        ("anchor", "why"),
        [
            ("a bolometer array operated at 10 millikelvin", "expanded an abbreviation"),
            ("an array of bolometers at 10 mK", "reworded"),
            ("operated at 9 mK", "changed a number"),
            ("a bolometer array operated at 10 mK and calibrated", "stitched two spans"),
            ("", "empty"),
            ("   ", "whitespace only"),
        ],
    )
    def test_rejects_anything_not_verbatim(self, anchor, why):
        assert not anchor_is_supported(anchor, TITLE, ABSTRACT), why

    def test_rejects_a_straightened_curly_quote(self):
        # Deliberate. Normalising punctuation would let through a model that is
        # retyping rather than copying -- exactly the behaviour the gate exists to
        # catch. A rejection here is the gate working.
        title = "On the Detector’s Calibration"
        assert anchor_is_supported("Detector’s Calibration", title, "")
        assert not anchor_is_supported("Detector's Calibration", title, "")

    def test_rejects_an_en_dash_flattened_to_a_hyphen(self):
        abstract = "We observe a 10–20 percent improvement."
        assert anchor_is_supported("10–20 percent", "", abstract)
        assert not anchor_is_supported("10-20 percent", "", abstract)


class TestNormalisationIsNotFolding:
    """Regressions for two holes that made the gate looser than its docstring.

    Both were found in review of the Phase 2 PR.
    """

    def test_rejects_a_case_folded_sharp_s(self):
        # str.casefold() maps the German sharp s to "ss", so a gate built on it
        # accepted "STRASSE" as a verbatim copy of "Straße" -- a retyped anchor,
        # which is precisely what this gate exists to reject. str.lower() does not.
        title = "Verkehr auf der Straße"
        assert anchor_is_supported("der Straße", title, "")
        assert not anchor_is_supported("der STRASSE", title, "")
        assert not anchor_is_supported("der strasse", title, "")

    def test_plain_case_insensitivity_still_works(self):
        # The fix must not make the gate case-SENSITIVE; only fold-free.
        title = "A Refined Upper Bound"
        assert anchor_is_supported("REFINED UPPER BOUND", title, "")
        assert anchor_is_supported("refined upper bound", title, "")

    def test_rejects_an_anchor_straddling_title_and_abstract(self):
        # The fields used to be concatenated with a space before searching, which
        # invented an adjacency present in neither: the anchor below appears in
        # no single field, yet the joined haystack contained it.
        title = "A Refined Upper Bound on Neutrino Mass"
        abstract = "We report a bound using a bolometer array."
        assert anchor_is_supported("Neutrino Mass", title, abstract)
        assert anchor_is_supported("We report a bound", title, abstract)
        assert not anchor_is_supported("Neutrino Mass We report", title, abstract)
