"""Tests for download_papers(). No test uses the network: OpenAlex, the PDF links and
tmsr-doi-downloader are replaced by fakes."""

import csv

import pytest

from theoryminer import download
from theoryminer.download import _doi_list, _file_name, download_papers

PDF = b"%PDF-1.7 a small fake PDF"

# The fake OpenAlex: {doi: (licence, pdf_urls)}
WORKS = {
    "10.1/open": ("cc-by", ["https://good.org/open.pdf"]),
    "10.1/nc": ("cc-by-nc", ["https://good.org/nc.pdf"]),
    "10.1/blocked": ("cc-by", ["https://blocked.org/blocked.pdf"]),
    "10.1/html": ("cc-by", ["https://good.org/page.html"]),
}


@pytest.fixture
def fake_network(monkeypatch):
    """Replace every network call. Return the list of the urls that were fetched."""
    fetched = []

    def fake_openalex(doi, email):
        return WORKS.get(doi, ("unknown", []))

    def fake_get(url):
        fetched.append(url)
        if url.endswith(".pdf"):
            return PDF
        return b"<html>not a PDF</html>"

    def fake_robots(url):
        return "blocked.org" not in url

    def fake_tmsr(doi, path, email, core_api_key, serpapi_key):
        if doi == "10.1/blocked":
            with open(path, "wb") as fh:
                fh.write(PDF)
            return True, ""
        return False, "tmsr-doi-downloader found no PDF"

    monkeypatch.setattr(download, "_openalex_work", fake_openalex)
    monkeypatch.setattr(download, "_get", fake_get)
    monkeypatch.setattr(download, "_robots_allow", fake_robots)
    monkeypatch.setattr(download, "_tmsr_download", fake_tmsr)
    return fetched


def status_of(rows):
    return {row["doi"]: row["status"] for row in rows}


def test_each_doi_gets_its_status(tmp_path, fake_network):
    rows = download_papers(list(WORKS) + ["10.1/unknown"], str(tmp_path), licences=["cc-by"])
    assert status_of(rows) == {"10.1/open": "downloaded", "10.1/nc": "skipped_licence",
                               "10.1/blocked": "downloaded", "10.1/html": "not_found",
                               "10.1/unknown": "skipped_licence"}
    assert (tmp_path / "10_1_open.pdf").read_bytes().startswith(b"%PDF-")


def test_a_left_out_licence_is_never_downloaded(tmp_path, fake_network):
    download_papers(["10.1/nc"], str(tmp_path), licences=["cc-by"])
    assert fake_network == []


def test_robots_txt_is_obeyed_and_the_downloader_is_the_second_source(tmp_path, fake_network):
    rows = download_papers(["10.1/blocked"], str(tmp_path), licences=["cc-by"])
    assert "https://blocked.org/blocked.pdf" not in fake_network
    assert rows[0]["source"] == "tmsr-doi-downloader"


def test_a_page_that_is_not_a_pdf_is_not_kept(tmp_path, fake_network):
    rows = download_papers(["10.1/html"], str(tmp_path))
    assert rows[0]["status"] == "not_found"
    assert "not a PDF" in rows[0]["note"]
    assert not (tmp_path / "10_1_html.pdf").exists()


def test_without_licences_every_open_paper_is_tried(tmp_path, fake_network):
    rows = download_papers(["10.1/nc"], str(tmp_path))
    assert rows[0]["status"] == "downloaded"


def test_a_second_run_does_not_download_again(tmp_path, fake_network):
    download_papers(["10.1/open"], str(tmp_path))
    rows = download_papers(["10.1/open"], str(tmp_path))
    assert rows[0]["status"] == "already_there"


def test_the_input_can_be_rows_strings_or_a_csv_file(tmp_path):
    path = tmp_path / "references.csv"
    path.write_text("doi,n_seeds,cited_by\n10.1/A,2,x | y\n10.1/b,1,x\n")
    assert _doi_list(str(path)) == ["10.1/a", "10.1/b"]
    assert _doi_list([{"doi": "10.1/a", "n_seeds": 1}, "10.1/A "]) == ["10.1/a"]


def test_the_file_name_is_safe_on_every_system():
    assert _file_name("10.1002/1098-237x(200011)84:6<740::aid-sce4>3.0.co;2-3") == \
        "10_1002_1098-237x_200011_84_6_740__aid-sce4_3_0_co_2-3.pdf"


def test_the_report_is_saved(tmp_path, fake_network):
    download_papers(["10.1/open", "10.1/nc"], str(tmp_path / "pdfs"), licences=["cc-by"], save=str(tmp_path))
    with open(tmp_path / "downloads.csv", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert [row["status"] for row in rows] == ["downloaded", "skipped_licence"]


def test_without_the_downloader_the_function_still_works(tmp_path, monkeypatch):
    # tmsr-doi-downloader is an optional extra. Its absence is a note, not an error.
    monkeypatch.setattr(download, "_openalex_work", lambda doi, email: ("cc-by", []))
    monkeypatch.setattr("builtins.__import__", _no_doi_downloader(__import__))
    rows = download_papers(["10.1/x"], str(tmp_path))
    assert rows[0]["status"] == "not_found"
    assert "not installed" in rows[0]["note"]


def _no_doi_downloader(real_import):
    """Return an import function that fails for doi_downloader only."""
    def fake_import(name, *args, **kwargs):
        if name.startswith("doi_downloader"):
            raise ImportError(name)
        return real_import(name, *args, **kwargs)
    return fake_import
