"""Tests for download_papers(). No test uses the network: OpenAlex, the web and
tmsr-doi-downloader are replaced by fakes."""

import csv
import sys

import pytest

from theoryminer.download import fetch, papers, sources
from theoryminer.download.papers import _doi_list, _file_name, download_papers

PDF = b"%PDF-1.7 a small fake PDF"
LANDING = b'<html><head><meta content="/from-page.pdf" name="citation_pdf_url"></head></html>'

# The fake OpenAlex: {doi: (licence, pdf_urls, page_urls)}
WORKS = {
    "10.1/open": ("cc-by", ["https://good.org/open.pdf"], []),
    "10.1/nc": ("cc-by-nc", ["https://good.org/nc.pdf"], []),
    "10.1/blocked": ("cc-by", ["https://blocked.org/blocked.pdf"], []),
    "10.1/html": ("cc-by", ["https://good.org/page.html"], []),
    "10.1/landing": ("cc-by", [], ["https://good.org/landing.html"]),
}


def fake_work(doi, email):
    """Return an OpenAlex record with the licence and the links of WORKS."""
    if doi not in WORKS:
        return {}
    licence, pdf_urls, page_urls = WORKS[doi]
    locations = [{"pdf_url": url, "is_oa": True} for url in pdf_urls]
    locations += [{"landing_page_url": url, "is_oa": True} for url in page_urls]
    return {"best_oa_location": {"license": licence}, "locations": locations}


@pytest.fixture
def fake_web(monkeypatch):
    """Replace OpenAlex, every GET and robots.txt. Return the list of the urls that were fetched."""
    fetched = []

    def fake_get(url):
        fetched.append(url)
        if url.endswith(".pdf"):
            return PDF, url, ""
        if url.endswith("landing.html"):
            return LANDING, url, ""
        if url.endswith(".html"):
            return b"<html>not a PDF</html>", url, ""
        return b"", url, "HTTP 404"

    def fake_robots(url):
        return "blocked.org" not in url

    monkeypatch.setattr(papers, "openalex_work", fake_work)
    monkeypatch.setattr(fetch, "_get", fake_get)
    monkeypatch.setattr(sources, "_get", fake_get)
    monkeypatch.setattr(fetch, "_robots_allow", fake_robots)
    return fetched


@pytest.fixture
def fake_network(fake_web, monkeypatch):
    """fake_web, and a fake tmsr-doi-downloader that finds only 10.1/blocked."""
    def fake_tmsr(doi, path, email, core_api_key, serpapi_key):
        if doi == "10.1/blocked":
            with open(path, "wb") as fh:
                fh.write(PDF)
            return ""
        return "found no PDF"

    monkeypatch.setattr(papers, "_tmsr_download", fake_tmsr)
    return fake_web


def status_of(rows):
    return {row["doi"]: row["status"] for row in rows}


def test_each_doi_gets_its_status(tmp_path, fake_network):
    # "10.1/blocked" needs the opt-in tmsr source: the open sources are blocked by robots.txt.
    rows = download_papers(list(WORKS) + ["10.1/unknown"], str(tmp_path), licences=["cc-by"],
                           sources=papers.SOURCES + ["tmsr-doi-downloader"])
    assert status_of(rows) == {"10.1/open": "downloaded", "10.1/nc": "skipped_licence",
                               "10.1/blocked": "downloaded", "10.1/html": "not_found",
                               "10.1/landing": "downloaded", "10.1/unknown": "skipped_licence"}
    assert (tmp_path / "10_1_open.pdf").read_bytes().startswith(b"%PDF-")


def test_a_left_out_licence_is_never_downloaded(tmp_path, fake_network):
    download_papers(["10.1/nc"], str(tmp_path), licences=["cc-by"])
    assert fake_network == []


def test_robots_txt_is_obeyed_and_the_last_source_can_still_help(tmp_path, fake_network):
    rows = download_papers(["10.1/blocked"], str(tmp_path), licences=["cc-by"],
                           sources=["openalex", "tmsr-doi-downloader"])
    assert "https://blocked.org/blocked.pdf" not in fake_network
    assert rows[0]["source"] == "tmsr-doi-downloader"


def test_respect_robots_false_reads_a_blocked_site(tmp_path, fake_network):
    rows = download_papers(["10.1/blocked"], str(tmp_path), respect_robots=False)
    assert "https://blocked.org/blocked.pdf" in fake_network
    assert rows[0]["source"] == "openalex"


def test_a_page_that_is_not_a_pdf_is_not_kept(tmp_path, fake_network):
    rows = download_papers(["10.1/html"], str(tmp_path))
    assert rows[0]["status"] == "not_found"
    assert "not a PDF" in rows[0]["note"]
    assert not (tmp_path / "10_1_html.pdf").exists()


def test_the_pdf_link_of_a_landing_page_is_followed(tmp_path, fake_network):
    rows = download_papers(["10.1/landing"], str(tmp_path))
    assert rows[0]["status"] == "downloaded"
    assert "https://good.org/from-page.pdf" in fake_network


def test_only_the_chosen_sources_are_tried_in_their_order(tmp_path, fake_network):
    rows = download_papers(["10.1/blocked"], str(tmp_path), sources=["openalex"])
    assert rows[0]["status"] == "not_found"
    assert rows[0]["note"].startswith("openalex: ")
    assert "tmsr-doi-downloader" not in rows[0]["note"]


def test_an_unknown_source_is_refused(tmp_path):
    with pytest.raises(ValueError, match="unknown sources"):
        download_papers(["10.1/open"], str(tmp_path), sources=["scihub"])
    with pytest.raises(ValueError):
        download_papers(["10.1/open"], str(tmp_path), sources=[])


def test_a_url_is_tried_once_per_doi(tmp_path, fake_network):
    # landing_page gives https://doi.org/10.1/html; no other source may fetch it again.
    download_papers(["10.1/html"], str(tmp_path), sources=["landing_page", "landing_page", "openalex"])
    assert fake_network.count("https://doi.org/10.1/html") == 1


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


def test_without_the_downloader_the_function_still_works(tmp_path, fake_web, monkeypatch):
    # tmsr-doi-downloader needs Python 3.11. Its absence is a note, not an error.
    monkeypatch.setattr("builtins.__import__", _no_doi_downloader(__import__))
    rows = download_papers(["10.1/html"], str(tmp_path), sources=["openalex", "tmsr-doi-downloader"])
    assert rows[0]["status"] == "not_found"
    assert "not installed" in rows[0]["note"]


def _no_doi_downloader(real_import):
    """Return an import function that fails for doi_downloader only."""
    def fake_import(name, *args, **kwargs):
        if name.startswith("doi_downloader"):
            raise ImportError(name)
        return real_import(name, *args, **kwargs)
    return fake_import


@pytest.mark.skipif(sys.version_info < (3, 11), reason="tmsr-doi-downloader needs Python 3.11")
def test_a_key_that_is_not_passed_keeps_its_environment_value(tmp_path, monkeypatch):
    from theoryminer.download import tmsr
    monkeypatch.chdir(tmp_path)
    from doi_downloader.plugins import coreacuk, unpaywall
    monkeypatch.setattr(unpaywall, "UNPAYWALL_EMAIL", "from-the-environment@lab.org")
    monkeypatch.setattr(coreacuk, "CORE_API_KEY", "key-from-the-environment")
    tmsr._set_keys(email=None, core_api_key="passed-key", serpapi_key=None)
    assert unpaywall.UNPAYWALL_EMAIL == "from-the-environment@lab.org"
    assert coreacuk.CORE_API_KEY == "passed-key"


def test_the_log_in_the_pdf_folder_keeps_earlier_runs(tmp_path, fake_network):
    download_papers(["10.1/open"], str(tmp_path), licences=["cc-by"])
    download_papers(["10.1/nc"], str(tmp_path), licences=["cc-by"])
    with open(tmp_path / "downloads.csv", newline="") as fh:
        rows = {row["doi"]: row for row in csv.DictReader(fh)}
    assert set(rows) == {"10.1/open", "10.1/nc"}
    assert rows["10.1/open"]["file"].endswith("10_1_open.pdf")


# --- the parts: the meta tag, the wait per site, and three sources ---------------------------

def test_the_pdf_link_of_a_page_is_found_in_either_attribute_order():
    page = b'<meta name="citation_pdf_url" content="https://a.org/x.pdf">'
    swapped = b"<meta content='/y.pdf' name='citation_pdf_url'>"
    assert fetch._pdf_link_in_page(page, "https://a.org/p") == "https://a.org/x.pdf"
    assert fetch._pdf_link_in_page(swapped, "https://b.org/p/q") == "https://b.org/y.pdf"
    assert fetch._pdf_link_in_page(b'<meta name="citation_title" content="x">', "https://a.org") == ""


def test_the_wait_is_per_site(monkeypatch):
    pauses = []
    monkeypatch.setattr(fetch.time, "sleep", pauses.append)
    monkeypatch.setattr(fetch, "_LAST_REQUEST", {"https://a.org": fetch.time.time()})
    fetch._wait_for("https://b.org")
    assert pauses == []
    fetch._wait_for("https://a.org")
    assert len(pauses) == 1 and 0 < pauses[0] <= fetch.WAIT


def test_pmc_gives_the_newest_article_pdf_and_not_a_supplement(monkeypatch):
    listing = (b"<Key>PMC7.1/PMC7.1.pdf</Key><Key>PMC7.2/PMC7.2.pdf</Key>"
               b"<Key>PMC7.2/12888_MOESM1_ESM.pdf</Key><Key>PMC7.2/PMC7.2.xml</Key>")
    monkeypatch.setattr(sources, "_get", lambda url: (listing, url, ""))
    work = {"ids": {"pmcid": "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7"}}
    urls, note = sources.pmc_urls("10.1/x", work, None)
    assert urls == [sources.PMC_BUCKET + "PMC7.2/PMC7.2.pdf"]


def test_unpaywall_is_skipped_without_an_email(fake_web):
    urls, note = sources.unpaywall_urls("10.1/x", {}, None)
    assert urls == [] and "email" in note
    assert fake_web == []


def test_crossref_leaves_out_the_links_that_need_a_key(monkeypatch):
    links = [{"URL": "https://api.wiley.com/tdm/x", "content-type": "unspecified"},
             {"URL": "https://pub.org/x.pdf", "content-type": "application/pdf"},
             {"URL": "https://pub.org/x.xml", "content-type": "text/xml"}]
    monkeypatch.setattr(sources, "_get_json", lambda url: ({"message": {"link": links}}, ""))
    urls, note = sources.crossref_urls("10.1/x", {}, None)
    assert urls == ["https://pub.org/x.pdf"]
