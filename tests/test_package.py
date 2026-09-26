"""Tests for the installed package: the public names and the version. No model is loaded."""

import re

import theoryminer

PUBLIC_NAMES = ["harvest", "extract_dois", "causenet", "standardize_constructs", "standardize_groups",
                "pairwise_grouping", "clusterer", "label_groups", "DEFAULT_STEPS", "STEPS"]


def test_every_public_name_imports():
    for name in PUBLIC_NAMES:
        assert hasattr(theoryminer, name), f"theoryminer.{name} is missing"


def test_version_matches_pyproject():
    with open("pyproject.toml", encoding="utf-8") as fh:
        text = fh.read()
    version = re.search(r'^version = "([^"]+)"', text, re.M).group(1)
    assert theoryminer.__version__ == version
