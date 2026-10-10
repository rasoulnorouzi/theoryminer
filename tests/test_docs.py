"""Tests for the documentation book (docs/). No model is loaded, and no file is written.

docs/make_api.py writes the reference pages from the docstrings. These tests check that it finds
every public function, that the book lists each one, and that each page has its main parts.
"""

import importlib.util
import inspect

import theoryminer

spec = importlib.util.spec_from_file_location("make_api", "docs/make_api.py")
make_api = importlib.util.module_from_spec(spec)
spec.loader.exec_module(make_api)

PUBLIC_FUNCTIONS = [name for name in theoryminer.__all__ if inspect.isfunction(getattr(theoryminer, name))]


def test_the_generator_finds_every_public_function_in_the_code():
    for name in PUBLIC_FUNCTIONS:
        assert make_api.find_function(make_api.PACKAGE_INIT, name) is not None, name


def test_every_public_function_has_a_stage_and_a_line_in_the_book():
    make_api.check_book(PUBLIC_FUNCTIONS)          # raises a ValueError when one is missing


def test_each_page_has_the_signature_and_the_sections():
    for name in PUBLIC_FUNCTIONS:
        node, path = make_api.find_function(make_api.PACKAGE_INIT, name)
        page = make_api.page_text(name, node, path)
        assert page.startswith(f"# {name}()"), name
        assert f"{name}(\n" in page, f"{name}: no signature"
        assert "## Arguments" in page and "## Returns" in page, f"{name}: a section is missing"


def test_an_aligned_key_list_becomes_a_table():
    lines = ["    A list of dicts, with the keys", "        doi       the DOI", "        sent_id, page   from the row"]
    table = make_api.render_returns(lines)
    assert "| `doi` | the DOI |" in table
    assert "| `sent_id, page` | from the row |" in table


def test_a_default_with_a_value_is_shown_as_code():
    assert make_api.render_item("Default None: read every page.") == "**Default** `None`: read every page."
    assert make_api.render_item("Values: True or False.") == "**Values:** True or False."
