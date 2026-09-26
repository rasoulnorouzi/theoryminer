"""Tests for label_groups(). It needs no model, so hand-made groups are enough."""

import pytest

from theoryminer.harmonizer import label_groups

# Two groups and one noise span, in the shape that clusterer() returns.
GROUPS = {
    "increased well-being": {"group": 0, "central": "increased well-being"},
    "higher well-being": {"group": 0, "central": "increased well-being"},
    "well-being and health": {"group": 0, "central": "increased well-being"},
    "job insecurity": {"group": 1, "central": "job insecurity"},
    "perceived job insecurity": {"group": 1, "central": "job insecurity"},
    "social trust": {"group": -1, "central": "social trust"},
}


def test_labels_by_medoid_keywords_and_both():
    medoid = label_groups(GROUPS, by="medoid")
    keywords = label_groups(GROUPS, by="keywords", top=1)
    both = label_groups(GROUPS, by="both", top=1)
    assert medoid[0]["name"] == "increased well-being"
    assert keywords[0]["name"] == "well-being"
    assert keywords[1]["name"] == "insecurity" or keywords[1]["name"] == "job"
    assert both[0]["name"] == "increased well-being | well-being"


def test_a_noise_span_is_a_group_of_one_named_by_itself():
    labelled = label_groups(GROUPS)
    assert labelled["social trust"]["size"] == 1
    assert labelled["social trust"]["name"] == "social trust"


def test_every_group_keeps_its_members():
    labelled = label_groups(GROUPS)
    assert labelled[0]["size"] == 3
    assert labelled[1]["members"] == ["job insecurity", "perceived job insecurity"]


def test_unknown_rule_raises():
    with pytest.raises(ValueError, match="unknown by 'words'"):
        label_groups(GROUPS, by="words")
