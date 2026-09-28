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


# --- tmsr-doi-downloader: a normal dependency since 0.2.1, on Python 3.11 or newer --------------

import importlib.metadata
import importlib.util
import sys

import pytest

NEEDS_3_11 = pytest.mark.skipif(sys.version_info < (3, 11), reason="tmsr-doi-downloader needs Python 3.11")


def test_the_downloader_is_declared_for_python_3_11_and_newer():
    requires = importlib.metadata.requires("theoryminer")
    declared = [text for text in requires if text.startswith("tmsr-doi-downloader") and "extra" not in text]
    assert declared, "tmsr-doi-downloader is not a normal dependency"
    assert 'python_version >= "3.11"' in declared[0]


@NEEDS_3_11
def test_the_downloader_is_installed_with_the_package():
    assert importlib.util.find_spec("doi_downloader") is not None


@NEEDS_3_11
def test_the_downloader_imports_on_this_system(tmp_path, monkeypatch):
    # The import writes database.db into the working folder, so it runs in a temporary folder.
    monkeypatch.chdir(tmp_path)
    from doi_downloader import doi_downloader
    from doi_downloader.plugins import coreacuk, googlescholar, unpaywall
    assert callable(doi_downloader.download)
