"""Slow tests: they load the real models (SocioCausaNet and all-mpnet-base-v2).

The first run downloads about 1 GB and embeds the ELSST thesaurus once.
Run them with:  pytest -m slow
"""

import pytest

from theoryminer import (causenet, clusterer, label_groups, pairwise_grouping, standardize_constructs,
                         standardize_groups)

pytestmark = pytest.mark.slow

SENTENCES = ["Smoking causes lung cancer and heart disease",
             "Exercise improves physical health and mental well-being",
             "This is a non-causal sentence about weather"]

# Spans with clear near neighbours, so that grouping and clustering have something to find.
SPANS = ["loneliness", "feelings of loneliness", "social isolation",
         "job insecurity", "perceived job insecurity", "fear of job loss",
         "mental health", "poor mental health", "mental health problems",
         "intrinsic motivation", "autonomous motivation", "income inequality"]


def test_causenet_finds_the_relations_of_the_toy_sentences():
    relations = causenet(SENTENCES, device="cpu")
    pairs = {(r["cause"], r["effect"]) for r in relations}
    assert ("smoking", "lung cancer") in pairs
    assert ("exercise", "physical health") in pairs
    for relation in relations:
        assert relation["sent_id"] != "s0002"          # the weather sentence is not causal


def test_standardize_constructs_returns_top_concepts():
    matches = standardize_constructs(["loneliness", "social trust"], top=3)
    assert matches["loneliness"][0]["leaf"] == "LONELINESS"
    for span in matches:
        assert len(matches[span]) == 3
        assert 0.0 < matches[span][0]["score"] <= 1.0


def test_grouping_clustering_and_naming_cover_every_span():
    groups = pairwise_grouping(SPANS, threshold=0.69)
    clusters = clusterer(SPANS)
    assert set(groups) == set(SPANS)
    assert set(clusters) == set(SPANS)
    assert groups["loneliness"]["group"] == groups["feelings of loneliness"]["group"]

    named = standardize_groups(clusters, top=1)
    labelled = label_groups(clusters)
    total = 0
    for row in labelled.values():
        total = total + row["size"]
    assert total == len(SPANS)
    assert set(named) == set(labelled)
