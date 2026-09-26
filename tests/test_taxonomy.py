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


def test_the_cache_folder_follows_the_environment_variable(monkeypatch, tmp_path):
    from theoryminer.harmonizer.taxonomy import _cache_dir
    monkeypatch.setenv("THEORYMINER_CACHE_DIR", str(tmp_path))
    assert _cache_dir() == str(tmp_path)


def test_the_default_cache_folder_is_outside_the_package(monkeypatch):
    import os
    import theoryminer
    from theoryminer.harmonizer.taxonomy import _cache_dir
    monkeypatch.delenv("THEORYMINER_CACHE_DIR", raising=False)
    folder = _cache_dir()
    assert folder.endswith(os.path.join(".cache", "theoryminer", "taxonomy"))
    assert not folder.startswith(os.path.dirname(theoryminer.__file__))


def test_the_cache_saves_the_vectors_and_the_entries(tmp_path):
    import numpy as np
    from theoryminer.harmonizer.taxonomy import _save_cache
    ok = _save_cache(str(tmp_path / "new" / "v.npy"), np.ones((2, 3)), str(tmp_path / "new" / "e.json"), [{"leaf": "A"}])
    assert ok
    assert np.load(tmp_path / "new" / "v.npy").shape == (2, 3)
    assert (tmp_path / "new" / "e.json").read_text(encoding="utf-8") == '[{"leaf": "A"}]'


def test_a_cache_folder_that_cannot_be_written_does_not_stop_the_run(tmp_path):
    import numpy as np
    from theoryminer.harmonizer.taxonomy import _save_cache
    blocker = tmp_path / "a_file"
    blocker.write_text("a file, so no folder can be made below it")
    ok = _save_cache(str(blocker / "sub" / "v.npy"), np.ones((2, 3)), str(blocker / "sub" / "e.json"), [])
    assert ok is False
