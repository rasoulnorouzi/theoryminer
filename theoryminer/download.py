"""download — download the open-access PDFs of a list of DOIs.

    from theoryminer import extract_references, download_papers, harvest
    refs = extract_references("seed_papers")                            # the DOIs that the seeds cite
    report = download_papers(refs, "round_2", licences=["cc-by"])       # the PDFs, one status row per DOI
    data = harvest("round_2")                                           # the next round

The sources, in this order:

1. OpenAlex (free, no key). It gives the licence of the best open-access copy
   and the PDF links of the paper. The licence check comes first, so a paper
   that the licences setting leaves out is never downloaded.
2. tmsr-doi-downloader. pip install theoryminer installs it on Python 3.11 or
   newer (since 0.2.1). On Python 3.10 the function uses OpenAlex only. It tries
   CORE (core_api_key=), Crossref, doi.org, Google Scholar (serpapi_key=, a paid
   service) and Unpaywall (email=). A key that you do not pass comes from its
   environment variable: CORE_API_KEY, SERPAPI_KEY or UNPAYWALL_EMAIL.

Not every paper can be downloaded: many publishers block robots. A failed DOI
does not stop the run. Each DOI gets one row with its status. A PDF that is
already in the folder is not downloaded again, so a stopped run can go on.
The function reads robots.txt and waits between requests.

tmsr-doi-downloader writes a cache (database.db) and a log (benchmark/) into
the working folder. So this module runs it inside CACHE_DIR, not in your folder.
"""

import contextlib
import csv
import io
import json
import os
import re
import time
import urllib.error
import urllib.request
import urllib.robotparser
from urllib.parse import quote, urlsplit

from .dois import _save_csv

OPENALEX_URL = "https://api.openalex.org/works/doi:{doi}"
USER_AGENT = "theoryminer (https://github.com/rasoulnorouzi/theoryminer)"
WAIT = 1.0              # seconds between two requests, as tmsr-doi-downloader waits
TIMEOUT = 30            # seconds before a request gives up
STATUSES = ["downloaded", "already_there", "skipped_licence", "not_found", "error"]
REPORT_CSV_NAME = "downloads.csv"     # the file name when save= gives a folder
REPORT_COLUMNS = ["doi", "status", "source", "licence", "file", "note"]
CACHE_DIR = os.path.join(os.environ.get("THEORYMINER_CACHE_DIR", os.path.expanduser("~/.cache/theoryminer")),
                         "downloader")

# A character that is not safe in a file name on every system. A DOI can hold "/", ":", "<", ">" and ";".
# Matches: "/" in "10.1093/pubmed"   No match: "fdy133"
RE_UNSAFE = re.compile(r"[^a-z0-9_-]", re.I)

_ROBOTS = {}            # {site: robots.txt parser}, read once per site and run


def _file_name(doi):
    """Return the PDF file name of a DOI: every unsafe character becomes "_".

    Example:
        >>> _file_name("10.1093/pubmed/fdy133")
        '10_1093_pubmed_fdy133.pdf'
    """
    return RE_UNSAFE.sub("_", doi) + ".pdf"


def _doi_list(dois):
    """Return the DOIs as a list of strings, in lowercase, without duplicates.

    Args:
        dois: the rows of extract_references() (dicts with a "doi" key), a list of DOI
            strings, or the path of a CSV file with a "doi" column.

    Example:
        >>> _doi_list([{"doi": "10.1/A"}, "10.1/a", "10.2/b"])
        ['10.1/a', '10.2/b']
    """
    if isinstance(dois, str):
        with open(dois, newline="", encoding="utf-8") as fh:
            dois = [row["doi"] for row in csv.DictReader(fh)]
    result = []
    for item in dois:
        doi = item["doi"] if isinstance(item, dict) else item
        doi = doi.strip().lower()
        if doi and doi not in result:
            result.append(doi)
    return result


def _row(doi, status, source="", licence="", file="", note=""):
    """Return one report row."""
    return {"doi": doi, "status": status, "source": source, "licence": licence, "file": file, "note": note}


# ---------------------------------------------------------------------------
# 1. The network: one GET, robots.txt, OpenAlex.
# ---------------------------------------------------------------------------

def _get(url):
    """Return the body of a GET request, or None for an HTTP error. Wait WAIT seconds after it."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return response.read()
    except urllib.error.HTTPError:
        return None
    finally:
        time.sleep(WAIT)


def _robots_allow(url):
    """Return True when the robots.txt of the site allows a robot to read the url."""
    site = "{0.scheme}://{0.netloc}".format(urlsplit(url))
    if site not in _ROBOTS:
        parser = urllib.robotparser.RobotFileParser()
        try:
            body = _get(site + "/robots.txt") or b""
        except (urllib.error.URLError, OSError):
            body = b""
        parser.parse(body.decode("utf-8", "replace").splitlines())
        _ROBOTS[site] = parser
    return _ROBOTS[site].can_fetch("*", url)


def _openalex_work(doi, email):
    """Return (licence, pdf_urls) from OpenAlex. ("unknown", []) when OpenAlex does not know the DOI."""
    url = OPENALEX_URL.format(doi=quote(doi, safe="/"))
    if email:
        url += "?mailto=" + quote(email)
    body = _get(url)
    if body is None:
        return "unknown", []
    work = json.loads(body)
    best = work.get("best_oa_location") or {}
    urls = []
    for location in [best] + (work.get("locations") or []):
        pdf_url = location.get("pdf_url")
        if pdf_url and pdf_url not in urls:
            urls.append(pdf_url)
    return best.get("license") or "none", urls


def _fetch_pdf(urls, path):
    """Download the first url that robots.txt allows and that gives a real PDF. Return (saved, note)."""
    notes = []
    for url in urls:
        site = urlsplit(url).netloc
        if not _robots_allow(url):
            notes.append(f"{site}: robots.txt blocks it")
            continue
        try:
            body = _get(url)
        except (urllib.error.URLError, OSError) as error:
            notes.append(f"{site}: {type(error).__name__}")
            continue
        if not body or not body.startswith(b"%PDF-"):
            notes.append(f"{site}: not a PDF")
            continue
        with open(path, "wb") as fh:
            fh.write(body)
        return True, ""
    return False, "; ".join(notes)


# ---------------------------------------------------------------------------
# 2. tmsr-doi-downloader, when it is installed.
# ---------------------------------------------------------------------------

def _set_keys(email, core_api_key, serpapi_key):
    """Give the keys to the sources of tmsr-doi-downloader. A key that is None is not changed.

    The sources read their keys once, at import, from the environment variables. So a key
    that you pass must be set on the source module. A key that you do not pass keeps the
    value of its environment variable.
    """
    from doi_downloader.plugins import coreacuk, googlescholar, unpaywall

    if email is not None:
        unpaywall.UNPAYWALL_EMAIL = email
    if core_api_key is not None:
        coreacuk.CORE_API_KEY = core_api_key
    if serpapi_key is not None:
        googlescholar.SERPAPI_KEY = serpapi_key


def _tmsr_download(doi, path, email, core_api_key, serpapi_key):
    """Try tmsr-doi-downloader. Return (saved, note). It runs in CACHE_DIR, and its output is silenced."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    folder = os.path.dirname(os.path.abspath(path))
    here = os.getcwd()
    os.chdir(CACHE_DIR)                               # its cache and its log go here, not into your folder
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            from doi_downloader import doi_downloader as ddl
            _set_keys(email, core_api_key, serpapi_key)
            saved = ddl.download(doi, output_dir=folder, enable_benchmark=False)
    except ImportError:
        return False, "tmsr-doi-downloader is not installed (it needs Python 3.11 or newer)"
    except Exception as error:                        # one failed source must not stop the run
        return False, f"tmsr-doi-downloader: {type(error).__name__}"
    finally:
        os.chdir(here)
    if not saved:
        return False, "tmsr-doi-downloader found no PDF"
    os.replace(saved, path)                           # its file name differs from ours
    return True, ""


# ---------------------------------------------------------------------------
# 3. The public function.
# ---------------------------------------------------------------------------

def _download_one(doi, output_dir, licences, email, core_api_key, serpapi_key):
    """Download one DOI. Return its report row."""
    path = os.path.join(output_dir, _file_name(doi))
    if os.path.exists(path):
        return _row(doi, "already_there", file=os.path.basename(path))

    # 1. The licence first: a paper that the setting leaves out is never downloaded.
    licence, urls = _openalex_work(doi, email)
    if licences is not None and licence not in licences:
        return _row(doi, "skipped_licence", licence=licence, note=f"the licence is not in {licences}")

    # 2. OpenAlex links, then tmsr-doi-downloader.
    saved, note = _fetch_pdf(urls, path)
    if saved:
        return _row(doi, "downloaded", "openalex", licence, os.path.basename(path))
    saved, tmsr_note = _tmsr_download(doi, path, email, core_api_key, serpapi_key)
    if saved:
        return _row(doi, "downloaded", "tmsr-doi-downloader", licence, os.path.basename(path))
    notes = [text for text in [note or "no open-access PDF link in OpenAlex", tmsr_note] if text]
    return _row(doi, "not_found", licence=licence, note="; ".join(notes))


def download_papers(dois, output_dir, licences=None, email=None, core_api_key=None, serpapi_key=None,
                    save=None):
    """Download the open-access PDFs of the DOIs into a folder. Return one status row per DOI.

    The function asks OpenAlex for the licence and the PDF links of each paper. With
    `licences`, it downloads only the papers with one of those licences. Then it tries the
    OpenAlex links, then tmsr-doi-downloader (installed with the package on Python 3.11 or
    newer). It reads robots.txt,
    waits WAIT seconds between requests, and keeps a file only when it is a real PDF.
    A PDF that is already in the folder is not downloaded again. The function writes the
    PDFs into output_dir.

    Args:
        dois: the rows of extract_references(), a list of DOI strings, or the path of a CSV
            file with a "doi" column.
        output_dir: the folder for the PDFs. A missing folder is made. The file name is the
            DOI with "_" for each unsafe character, so harvest() gives the DOI as the doc_id.
        licences: None downloads every open-access paper. A list, for example ["cc-by"],
            downloads only the papers whose OpenAlex licence is in the list. The values are
            "cc-by", "cc-by-sa", "cc-by-nc", "cc-by-nd", "cc-by-nc-sa", "cc-by-nc-nd",
            "public-domain", "other-oa", "publisher-specific-oa", "none" and "unknown".
        email: your email address, for Unpaywall in tmsr-doi-downloader (it refuses a
            made-up address). OpenAlex also gets it, for its faster "polite pool".
            None keeps the environment variable UNPAYWALL_EMAIL, when it is set.
        core_api_key: a free key from core.ac.uk, for CORE in tmsr-doi-downloader.
            None keeps the environment variable CORE_API_KEY.
        serpapi_key: a key of SerpAPI (a paid service), for Google Scholar in tmsr-doi-downloader.
            None keeps the environment variable SERPAPI_KEY.
        save: None writes no report file. A path that ends with ".csv", or a folder
            (then <folder>/downloads.csv), gets the report rows.

    Returns:
        A list of dicts, one per DOI, with the keys doi, status, source, licence, file, note.
        status is one of STATUSES. source is "openalex" or "tmsr-doi-downloader".

    Example:
        >>> refs = extract_references("sample_files")                                   # doctest: +SKIP
        >>> report = download_papers(refs, "outputs/round_2", licences=["cc-by"])       # doctest: +SKIP
    """
    doi_list = _doi_list(dois)
    os.makedirs(output_dir, exist_ok=True)
    rows = []
    start = time.time()
    for i, doi in enumerate(doi_list):
        print(f"\r  downloading {i + 1} of {len(doi_list)}", end="")
        try:
            rows.append(_download_one(doi, output_dir, licences, email, core_api_key, serpapi_key))
        except (urllib.error.URLError, OSError, ValueError) as error:
            rows.append(_row(doi, "error", note=f"{type(error).__name__}: {error}"[:200]))
    print()

    saved_to = ""
    if save:
        saved_to = _save_csv(rows, save, REPORT_CSV_NAME, REPORT_COLUMNS)
    _print_summary(output_dir, rows, time.time() - start, saved_to)
    return rows


def _print_summary(output_dir, rows, seconds, saved_to):
    """Print one short summary of a download_papers() run."""
    counts = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    by_source = {}
    for row in rows:
        if row["status"] == "downloaded":
            by_source[row["source"]] = by_source.get(row["source"], 0) + 1
    parts = [f"{status}: {counts[status]}" for status in STATUSES if status in counts]
    print(f"download: {len(rows)} DOIs -> {output_dir} in {seconds / 60:.1f} min")
    print(f"  {' | '.join(parts)}")
    if by_source:
        print(f"  downloaded from: {by_source}")
    if saved_to:
        print(f"  saved: {saved_to}")
