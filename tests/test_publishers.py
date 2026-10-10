"""Tests for the publisher plugins (publishers.py). No test uses the network."""

from theoryminer.download import publishers


def test_the_doi_prefix_picks_the_right_plugin():
    assert publishers.plugin_for("10.3389/feduc.2021.618655")["name"] == "Frontiers"
    assert publishers.plugin_for("10.1007/s00103-023-03728-x")["name"] == "Springer"
    assert publishers.plugin_for("10.1186/s12888-020-02818-3")["name"] == "Springer"     # BMC
    assert publishers.plugin_for("10.9999/unknown") is None


def test_a_plugin_builds_the_direct_pdf_link():
    assert publishers.direct_pdf_urls("10.1186/s12888-020-02818-3", {}) == \
        ["https://link.springer.com/content/pdf/10.1186/s12888-020-02818-3.pdf"]
    assert publishers.direct_pdf_urls("10.3389/feduc.2021.618655", {}) == \
        ["https://www.frontiersin.org/articles/10.3389/feduc.2021.618655/pdf"]


def test_a_doi_without_a_plugin_gives_no_link():
    assert publishers.direct_pdf_urls("10.9999/x", {}) == []
    # Wiley serves its PDFs only to a browser that passes its bot check, so it has no plugin.
    assert publishers.direct_pdf_urls("10.1111/pops.12105", {}) == []
