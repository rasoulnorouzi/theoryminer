"""Tests for the threshold of the ELSST functions. No test loads a model."""

import inspect

import numpy as np

from theoryminer import standardize_constructs, standardize_groups
from theoryminer.harmonizer.standardize import _score_summary, _top_matches

ENTRIES = [{"id": "c1", "leaf": "STRESS", "path": "STRESS"},
           {"id": "c2", "leaf": "HEALTH", "path": "HEALTH"},
           {"id": "c3", "leaf": "TRUST", "path": "TRUST"}]
SCORES = np.array([0.41, 0.62, 0.55])


def leaves(matches):
    return [m["leaf"] for m in matches]


def test_no_threshold_keeps_every_match_best_first():
    assert leaves(_top_matches(SCORES, ENTRIES, 5)) == ["HEALTH", "TRUST", "STRESS"]


def test_threshold_leaves_out_the_lower_matches():
    assert leaves(_top_matches(SCORES, ENTRIES, 5, threshold=0.5)) == ["HEALTH", "TRUST"]


def test_a_threshold_above_every_score_gives_no_concept():
    assert _top_matches(SCORES, ENTRIES, 5, threshold=0.9) == []


def test_top_still_limits_the_list():
    assert leaves(_top_matches(SCORES, ENTRIES, 1, threshold=0.4)) == ["HEALTH"]


def test_summary_counts_the_items_without_a_concept():
    assert _score_summary([0.6], 3, 0.5).endswith("no concept >= 0.5: 2 of 3")


def test_threshold_is_off_by_default():
    for function in [standardize_constructs, standardize_groups]:
        assert inspect.signature(function).parameters["threshold"].default is None
