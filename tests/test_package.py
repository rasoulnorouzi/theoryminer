"""Tests for the installed package: the public names and the version. No model is loaded."""

import re

import theoryminer

PUBLIC_NAMES = ["harvest", "extract_dois", "extract_references", "causenet", "standardize_constructs", "standardize_groups",
                "pairwise_grouping", "clusterer", "label_groups", "causal_map", "draw_map", "save_map", "download_papers",
                "DEFAULT_STEPS", "STEPS"]


def test_every_public_name_imports():
    for name in PUBLIC_NAMES:
        assert hasattr(theoryminer, name), f"theoryminer.{name} is missing"


def test_version_matches_pyproject():
    with open("pyproject.toml", encoding="utf-8") as fh:
        text = fh.read()
    version = re.search(r'^version = "([^"]+)"', text, re.M).group(1)
    assert theoryminer.__version__ == version


def test_umap_is_installed_by_default():
    import umap
    assert hasattr(umap, "UMAP")
