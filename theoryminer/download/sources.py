"""sources — where the downloader looks for the PDF of a DOI.

Each finder has the same form: finder(doi, work, email) -> (urls, note).
    doi    the DOI, in lowercase
    work   the OpenAlex record of the paper ({} when OpenAlex does not know the DOI)
    email  your email address, or None
    urls   the links to try, best first: a PDF or a page with a citation_pdf_url meta tag
    note   why the source gives no link, else ""

The sources (all free; only Unpaywall needs an email address):
    openalex          the PDF links and the repository pages of the open-access copies in OpenAlex
    publisher         the publisher's direct PDF link, from a per-publisher plugin (publishers.py)
    pmc               the PDF in the open-access data of PubMed Central (NCBI, on AWS)
    europe_pmc        the PDF links that Europe PMC lists for the paper
    unpaywall         the PDF links of Unpaywall
    semantic_scholar  the open-access PDF link of Semantic Scholar
    crossref          the PDF links that the publisher gives to Crossref
    preprint          the open preprint of the paper (OSF and other preprint servers)
    landing_page      the page that doi.org opens, and its citation_pdf_url meta tag
"""

import re
from urllib.parse import quote

from .fetch import _get, _get_json
from .publishers import direct_pdf_urls

OPENALEX_URL = "https://api.openalex.org/works/doi:{doi}"
UNPAYWALL_URL = "https://api.unpaywall.org/v2/{doi}?email={email}"
SEMANTIC_SCHOLAR_URL = "https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}?fields=openAccessPdf"
CROSSREF_URL = "https://api.crossref.org/works/{doi}"
EUROPE_PMC_URL = ("https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=DOI:%22{doi}%22"
                  "&resultType=core&format=json")
OSF_DOWNLOAD_URL = "https://osf.io/{osf_id}/download"
PMC_BUCKET = "https://pmc-oa-opendata.s3.amazonaws.com/"     # PMC Open Access data on AWS (NCBI)
PMC_LIST_URL = PMC_BUCKET + "?list-type=2&prefix={pmcid}."
DOI_URL = "https://doi.org/{doi}"

# Crossref links that give no PDF without a key of the publisher (a text-mining token).
KEY_HOSTS = ["api.elsevier.com", "api.wiley.com"]
# The Crossref content types of a link that can be a PDF ("unspecified" is often a PDF).
PDF_TYPES = ["application/pdf", "unspecified"]

# A PMCID at the end of a PMC url. Matches ".../pmc/articles/PMC7444250"; not ".../pubmed/32831064".
PMCID = re.compile(r"(PMC\d+)/?$")
# An OSF id inside a preprint DOI. Matches "10.31234/osf.io/nrdv7"; not "10.1037/a0024780".
OSF_ID = re.compile(r"osf\.io/([a-z0-9]+)", re.IGNORECASE)


def _quoted(doi):
    """Return the DOI with the characters that a url cannot hold in quoted form ("/" stays)."""
    return quote(doi, safe="/")


def openalex_work(doi, email):
    """Return the OpenAlex record of a DOI, or {} when OpenAlex does not know it."""
    url = OPENALEX_URL.format(doi=_quoted(doi))
    if email:
        url += "?mailto=" + quote(email)
    work, _ = _get_json(url)
    return work or {}


def openalex_licence(work):
    """Return the licence of the best open-access copy: an OpenAlex licence, "none" or "unknown".

    Example:
        >>> openalex_licence({"best_oa_location": {"license": "cc-by"}}), openalex_licence({})
        ('cc-by', 'unknown')
    """
    if not work:
        return "unknown"
    best = work.get("best_oa_location") or {}
    return best.get("license") or "none"


def _add(urls, url):
    """Add a url to the list when it is new and not empty."""
    if url and url not in urls:
        urls.append(url)


def openalex_urls(doi, work, email):
    """Return the PDF links of the open-access copies, then the pages of those copies.

    The pages come last: a repository page often has a citation_pdf_url meta tag when OpenAlex
    has no PDF link for it.
    """
    if not work:
        return [], "OpenAlex does not know the DOI"
    locations = [work.get("best_oa_location") or {}] + (work.get("locations") or [])
    urls = []
    for location in locations:
        _add(urls, location.get("pdf_url"))
    for location in locations:
        if location.get("is_oa"):
            _add(urls, location.get("landing_page_url"))
    if not urls:
        return [], "no open-access copy"
    return urls, ""


def _pmcid(doi, work):
    """Return the PMCID of the paper ("PMC7444250"), or "" when it is not in PubMed Central.

    OpenAlex gives the PMCID of many papers. Europe PMC gives it for the others.
    """
    pmc_url = (work.get("ids") or {}).get("pmcid") or ""
    match = PMCID.search(pmc_url)
    if match:
        return match.group(1)
    data, _ = _get_json(EUROPE_PMC_URL.format(doi=quote(doi, safe="")))
    results = ((data or {}).get("resultList") or {}).get("result") or []
    for result in results:
        if result.get("pmcid") and (result.get("doi") or "").lower() == doi:
            return result["pmcid"]
    return ""


def pmc_urls(doi, work, email):
    """Return the link of the PDF in the PMC Open Access data (the newest version of the article).

    The files of an article are in the folder <PMCID>.<version>/ of the bucket. The PDF of the
    article is <PMCID>.<version>.pdf. The other PDFs in the folder are supplements.
    """
    pmcid = _pmcid(doi, work)
    if not pmcid:
        return [], "not in PubMed Central"
    body, _, note = _get(PMC_LIST_URL.format(pmcid=pmcid))
    if note:
        return [], note
    # The key of the article PDF. Matches "<Key>PMC7444250.1/PMC7444250.1.pdf</Key>";
    # not "<Key>PMC7444250.1/12888_2020_2818_MOESM1_ESM.pdf</Key>" (a supplement).
    article_pdf = re.compile(rf"<Key>({pmcid}\.(\d+)/{pmcid}\.\2\.pdf)</Key>")
    versions = {}
    for key, version in article_pdf.findall(body.decode("utf-8", "replace")):
        versions[int(version)] = key
    if not versions:
        return [], f"{pmcid} is not in the open-access data"
    return [PMC_BUCKET + versions[max(versions)]], ""


def _europe_pmc_result(doi):
    """Return the Europe PMC record of a DOI, or {} when Europe PMC does not have it."""
    data, _ = _get_json(EUROPE_PMC_URL.format(doi=quote(doi, safe="")))
    results = ((data or {}).get("resultList") or {}).get("result") or []
    for result in results:
        if (result.get("doi") or "").lower() == doi:
            return result
    return results[0] if results else {}


def europe_pmc_urls(doi, work, email):
    """Return the free PDF links that Europe PMC lists for the paper.

    Europe PMC holds the full text of many open papers of BMC, Springer and the life sciences.
    """
    result = _europe_pmc_result(doi)
    if not result:
        return [], "not in Europe PMC"
    urls = []
    for link in ((result.get("fullTextUrlList") or {}).get("fullTextUrl") or []):
        if link.get("documentStyle") == "pdf" and link.get("availability") == "Free":
            _add(urls, link.get("url"))
    if not urls:
        return [], "no free PDF link"
    return urls, ""


def preprint_urls(doi, work, email):
    """Return the download link of the open preprint of the paper (an OSF preprint).

    A published paper often has a free preprint on OSF. Crossref names it in the "has-preprint"
    relation. Many psychology papers behind a paywall are readable this way.
    """
    url = CROSSREF_URL.format(doi=_quoted(doi))
    if email:
        url += "?mailto=" + quote(email)
    data, note = _get_json(url)
    if data is None:
        return [], note
    relations = (data.get("message") or {}).get("relation") or {}
    urls = []
    for relation in relations.get("has-preprint") or []:
        match = OSF_ID.search(relation.get("id") or "")
        if match:
            _add(urls, OSF_DOWNLOAD_URL.format(osf_id=match.group(1)))
    if not urls:
        return [], "no OSF preprint"
    return urls, ""


def unpaywall_urls(doi, work, email):
    """Return the PDF links of the open-access copies in Unpaywall. Unpaywall needs an email address."""
    if not email:
        return [], "no email address (Unpaywall needs one)"
    data, note = _get_json(UNPAYWALL_URL.format(doi=_quoted(doi), email=quote(email)))
    if data is None:
        return [], note
    urls = []
    for location in data.get("oa_locations") or []:
        _add(urls, location.get("url_for_pdf"))
    if not urls:
        return [], "no PDF link"
    return urls, ""


def semantic_scholar_urls(doi, work, email):
    """Return the open-access PDF link of Semantic Scholar.

    Without a key, Semantic Scholar shares a small request limit between all users. A busy
    service answers "HTTP 429"; the step then goes on to the next source.
    """
    data, note = _get_json(SEMANTIC_SCHOLAR_URL.format(doi=_quoted(doi)))
    if data is None:
        return [], note
    url = (data.get("openAccessPdf") or {}).get("url")
    if not url:
        return [], "no PDF link"
    return [url], ""


def crossref_urls(doi, work, email):
    """Return the links that the publisher gives to Crossref and that can be a PDF.

    The step leaves out the text-mining services that need a key of the publisher (KEY_HOSTS).
    """
    url = CROSSREF_URL.format(doi=_quoted(doi))
    if email:
        url += "?mailto=" + quote(email)
    data, note = _get_json(url)
    if data is None:
        return [], note
    urls = []
    for link in (data.get("message") or {}).get("link") or []:
        link_url = link.get("URL") or ""
        if link.get("content-type") not in PDF_TYPES:
            continue
        if any(host in link_url for host in KEY_HOSTS):
            continue
        _add(urls, link_url)
    if not urls:
        return [], "no PDF link"
    return urls, ""


def publisher_urls(doi, work, email):
    """Return the publisher's direct PDF link, from a plugin in publishers.py."""
    urls = direct_pdf_urls(doi, work)
    if not urls:
        return [], "no publisher plugin"
    return urls, ""


def landing_page_urls(doi, work, email):
    """Return the doi.org link of the paper. Its page can have a citation_pdf_url meta tag."""
    return [DOI_URL.format(doi=_quoted(doi))], ""


FINDERS = {
    "openalex": openalex_urls,
    "publisher": publisher_urls,
    "pmc": pmc_urls,
    "europe_pmc": europe_pmc_urls,
    "unpaywall": unpaywall_urls,
    "semantic_scholar": semantic_scholar_urls,
    "crossref": crossref_urls,
    "preprint": preprint_urls,
    "landing_page": landing_page_urls,
}
