"""A layer's calibration and opacity (ADR 0361)."""

import pytest

from lorenzo_map import MAX_LAYERS, MapDocumentError, validate_calibration, validate_opacity


def anchors(*pairs):
    return {"anchors": [{"image": list(i), "at": list(a)} for i, a in pairs]}


TWO = anchors(((0.1, 0.2), (100, 50)), ((0.9, 0.8), (900, 650)))
THREE = anchors(((0, 0), (0, 0)), ((1, 0), (500, 0)), ((0, 1), (0, 300)))


def test_no_calibration_is_fit_the_sheet():
    assert validate_calibration(None) is None
    assert MAX_LAYERS == 8


@pytest.mark.parametrize("document", [TWO, THREE], ids=["two", "three"])
def test_two_or_three_anchors_are_a_fixed_point(document):
    stored = validate_calibration(document)
    assert stored is not None and validate_calibration(stored) == stored
    assert len(stored["anchors"]) == len(document["anchors"])


def test_numbers_are_stored_in_their_canonical_form():
    stored = validate_calibration(anchors(((0.0, 0.0), (10.0, 5.5)), ((1.0, 1.0), (20.0, 6))))
    assert stored["anchors"][0] == {"image": [0, 0], "at": [10, 5.5]}
    assert stored["anchors"][1]["image"] == [1, 1]


@pytest.mark.parametrize(
    "document",
    [
        {},
        {"anchors": []},
        {"anchors": [TWO["anchors"][0]]},
        {"anchors": TWO["anchors"] + THREE["anchors"]},
        {**TWO, "extra": 1},
        "fit",
        anchors(((0.1, 0.1), (1, 1)), ((0.1, 0.1), (5, 5))),
        anchors(((0.1, 0.1), (1, 1)), ((0.9, 0.9), (1, 1))),
        anchors(((0, 0), (0, 0)), ((1, 1), (5, 5)), ((0.5, 0.5), (9, 1))),
        anchors(((0, 0), (0, 0)), ((1, 0), (5, 5)), ((0.5, 0), (9, 1))),
        anchors(((0, 0), (0, 0)), ((1, 0), (5, 5)), ((0.5, 0.5), (10, 10))),
        anchors(((1.5, 0), (1, 1)), ((0.9, 0.9), (5, 5))),
        anchors(((-0.1, 0), (1, 1)), ((0.9, 0.9), (5, 5))),
        anchors(((0.1, 0.1), (1e9, 1)), ((0.9, 0.9), (5, 5))),
        anchors(((0.1, 0.1), (1, 1)), ((0.9, 0.9, 0.4), (5, 5))),
        {"anchors": [{"image": [0.1, 0.1]}, {"image": [0.9, 0.9], "at": [1, 2]}]},
        anchors(((0.1, 0.1), (1, 1)), ((0.9, 0.9), (True, 5))),
        anchors(((0.1, 0.1), (1, 1)), ((0.9, 0.0000001), (5, 5))),
    ],
)
def test_a_calibration_that_makes_no_sense_is_refused(document):
    with pytest.raises(MapDocumentError) as refused:
        validate_calibration(document)
    assert str(refused.value) == refused.value.reason


def test_opacity_is_none_or_from_zero_to_one():
    assert validate_opacity(None) is None
    assert validate_opacity(0) == 0 and validate_opacity(1) == 1
    assert validate_opacity(0.35) == 0.35
    for refused in (-0.1, 1.5, "half", True, float("nan"), 0.1234567):
        with pytest.raises(MapDocumentError):
            validate_opacity(refused)
