"""Tests for the packaged ELSST thesaurus and the strategy texts. No model is loaded."""

import pytest

from theoryminer.harmonizer.taxonomy import (DEFAULT_FILES, STRATEGIES, _read_text, load_taxonomy,
                                             strategy_text)


def test_the_package_holds_the_elsst_file():
    assert DEFAULT_FILES["elsst"].endswith("ELSST_R5.rdf.gz")
    assert _read_text(DEFAULT_FILES["elsst"]).startswith("<?xml")


def test_elsst_gives_the_known_counts():
    assert len(load_taxonomy("elsst", leaves_only=True)) == 2661
    assert len(load_taxonomy("elsst", leaves_only=False)) == 3739


def test_every_entry_has_the_same_shape():
    for entry in load_taxonomy("elsst", leaves_only=True):
        assert set(entry) == {"id", "leaf", "path", "parents", "alt", "note"}


def test_the_six_strategies_on_self_esteem():
    entry = None
    for candidate in load_taxonomy("elsst", leaves_only=True):
        if candidate["path"] == "IDENTITY > PERSONAL IDENTITY > SELF-ESTEEM":
            entry = candidate
    assert strategy_text(entry, "leaf") == "self-esteem"
    assert strategy_text(entry, "path") == "identity > personal identity > self-esteem"
    assert strategy_text(entry, "bracket") == "self-esteem (personal identity, identity)"
    assert strategy_text(entry, "enriched").startswith("self-esteem. ")
    assert len(STRATEGIES) == 6


def test_unknown_strategy_raises():
    entry = load_taxonomy("elsst", leaves_only=True)[0]
    with pytest.raises(ValueError, match="unknown strategy 'leafs'"):
        strategy_text(entry, "leafs")


def test_unknown_taxonomy_raises():
    with pytest.raises(ValueError, match="unknown taxonomy 'apa'"):
        load_taxonomy("apa")
