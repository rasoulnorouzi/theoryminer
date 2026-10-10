"""download — download the open-access PDFs of a list of DOIs.

    from theoryminer import extract_references, download_papers, harvest
    refs = extract_references("seed_papers")                            # the DOIs that the seeds cite
    report = download_papers(refs, "round_2", licences=["cc-by"])       # the PDFs, one status row per DOI
    data = harvest("round_2")                                           # the next round

The function asks OpenAlex for the licence first, so a paper that the licences setting
leaves out is never downloaded. Then it tries the sources in turn (SOURCES) until one gives
a real PDF. sources.py tells what each source does; tmsr.py wraps tmsr-doi-downloader.

Not every paper can be downloaded: many publishers block robots. A failed DOI does not stop
the run. Each DOI gets one row with its status. A PDF that is already in the folder is not
downloaded again, so a stopped run can go on. The function reads robots.txt and waits
between two requests to the same site.
"""

import csv
import os
import time
import urllib.error

from ..prepare.dois import _save_csv
from ..prepare.pdf import _safe_name
from .fetch import _fetch_pdf
from .sources import FINDERS, openalex_licence, openalex_work
from .tmsr import _tmsr_download

# The sources of the default, in order. They are the free, open-access sources and the per-publisher
# plugins. They need no key and no login. On the benchmark they beat tmsr-doi-downloader (they
# replace it), so tmsr is not in the default. It is available with sources=:
#   "tmsr-doi-downloader"  the package tmsr-doi-downloader (Crossref, CORE, Google Scholar, Unpaywall)
# The downloader gets open-access copies only. A browser source with an institution login was tried
# and left out on purpose (2026-10-10): the package does not log in to publisher sites.
SOURCES = ["openalex", "publisher", "pmc", "europe_pmc", "unpaywall", "semantic_scholar", "crossref",
           "preprint", "landing_page"]
ALL_SOURCES = SOURCES + ["tmsr-doi-downloader"]     # every source name that sources= accepts
STATUSES = ["downloaded", "already_there", "skipped_licence", "not_found", "error"]
REPORT_CSV_NAME = "downloads.csv"     # the file name when save= gives a folder
REPORT_COLUMNS = ["doi", "status", "source", "licence", "file", "note"]


def _file_name(doi):
    """Return the PDF file name of a DOI: every unsafe character becomes "_".

    Example:
        >>> _file_name("10.1093/pubmed/fdy133")
        '10_1093_pubmed_fdy133.pdf'
    """
    return _safe_name(doi) + ".pdf"


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


def _check_sources(sources):
    """Return the list of sources to try. Raise a ValueError for an unknown source or an empty list."""
    if sources is None:
        return list(SOURCES)
    if isinstance(sources, str):
        sources = [sources]
    unknown = [source for source in sources if source not in ALL_SOURCES]
    if unknown or not sources:
        raise ValueError(f"unknown sources {unknown or sources}; choose one or more of {ALL_SOURCES}")
    return list(sources)


def _try_source(source, doi, work, path, settings, tried):
    """Try one source for one DOI. Return "" when it saved the PDF into path, else why not."""
    if source == "tmsr-doi-downloader":
        return _tmsr_download(doi, path, settings["email"], settings["core_api_key"], settings["serpapi_key"])
    urls, note = FINDERS[source](doi, work, settings["email"])
    if not urls:
        return note
    return _fetch_pdf(urls, path, settings["respect_robots"], tried)


def _download_one(doi, output_dir, licences, sources, settings):
    """Download one DOI. Return its report row.

    Args:
        settings: {"email", "core_api_key", "serpapi_key", "respect_robots"} of download_papers().
    """
    path = os.path.join(output_dir, _file_name(doi))
    if os.path.exists(path):
        return _row(doi, "already_there", file=os.path.basename(path))

    # 1. The licence first: a paper that the setting leaves out is never downloaded.
    work = openalex_work(doi, settings["email"])
    licence = openalex_licence(work)
    if licences is not None and licence not in licences:
        return _row(doi, "skipped_licence", licence=licence, note=f"the licence is not in {licences}")

    # 2. The sources in turn. A url that one source tried is not tried again by the next one.
    tried = set()
    notes = []
    for source in sources:
        note = _try_source(source, doi, work, path, settings, tried)
        if not note:
            return _row(doi, "downloaded", source, licence, os.path.basename(path))
        notes.append(f"{source}: {note}")
    return _row(doi, "not_found", licence=licence, note="; ".join(notes))


def download_papers(dois: list | str, output_dir: str, licences: list[str] | None = None,
                    email: str | None = None, sources: list[str] | None = None,
                    respect_robots: bool = True, core_api_key: str | None = None,
                    serpapi_key: str | None = None, save: str | None = None) -> list[dict]:
    """Download the open-access PDFs of the DOIs into a folder. Return one status row per DOI.

    The function asks OpenAlex for the licence of each paper. With `licences`, it downloads
    only the papers with one of those licences. Then it tries the sources in turn until one
    gives a real PDF. A link can give the PDF or a page; for a page, the function follows its
    citation_pdf_url meta tag once. It waits 1 second between two requests to the same site.
    A PDF that is already in the folder is not downloaded again, so a stopped run can go on.
    A failed DOI does not stop the run. The function writes the PDFs and the log downloads.csv
    into output_dir (the log keeps the rows of earlier runs, and harvest() reads it to know the
    DOI of each file), and a report file when you give `save`. It gets open-access copies only:
    it does not log in to a publisher site.

    Args:
        dois: The papers to download.
            Values: the rows of extract_references() (dicts with a "doi" key), a list of DOI
            strings, or the path of a CSV file with a "doi" column. A text is always read as
            the path of a CSV file, not as one DOI.
            Default: none. Give the DOIs.
        output_dir: The folder for the PDFs.
            Values: the path of a folder. A missing folder is made. The file name is the DOI
            with "_" for each unsafe character.
            Default: none. Give a folder.
        licences: The licences to download.
            Values: None, or a list of OpenAlex licences: "cc-by", "cc-by-sa", "cc-by-nc",
            "cc-by-nd", "cc-by-nc-sa", "cc-by-nc-nd", "public-domain", "other-oa",
            "publisher-specific-oa", "none" and "unknown".
            Default None: download every paper that has an open-access copy, whatever its licence.
        email: Your email address. OpenAlex and Crossref answer faster with it ("polite pool"),
            and Unpaywall needs it.
            Values: None, or a real email address (Unpaywall refuses a made-up address).
            Default None: no email. The function skips Unpaywall, and tmsr-doi-downloader uses
            the environment variable UNPAYWALL_EMAIL when it is set.
        sources: The sources to try, in this order.
            Values: a list of one or more of
            "openalex" (the PDF links and repository pages of the open-access copies in OpenAlex),
            "publisher" (the publisher's direct PDF link, from a per-publisher plugin),
            "pmc" (the PDF in the PubMed Central open-access data of NCBI),
            "europe_pmc" (the free PDF links that Europe PMC lists),
            "unpaywall" (the PDF links of Unpaywall; it needs `email`),
            "semantic_scholar" (the open-access PDF link of Semantic Scholar),
            "crossref" (the PDF links that the publisher gives to Crossref),
            "preprint" (the open OSF preprint of the paper, from the Crossref relation),
            "landing_page" (the page that doi.org opens, and its PDF link),
            "tmsr-doi-downloader" (the package tmsr-doi-downloader; Python 3.11 or newer).
            Default None: the nine open sources above, from "openalex" to "landing_page", in that
            order. The default leaves out "tmsr-doi-downloader". Add it with this setting when the
            open sources miss a paper.
        respect_robots: Whether to obey the robots.txt file of each site.
            Values: True or False. Set False only when you have the right to download from the
            sites, for example by an agreement of your institution. The wait between requests
            stays. tmsr-doi-downloader always obeys robots.txt.
            Default True: skip every link that robots.txt does not allow.
        core_api_key: A free key from core.ac.uk, for CORE in tmsr-doi-downloader.
            Values: None, or the key as text.
            Default None: use the environment variable CORE_API_KEY when it is set, else skip CORE.
        serpapi_key: A key of SerpAPI (a paid service), for Google Scholar in tmsr-doi-downloader.
            Values: None, or the key as text.
            Default None: use the environment variable SERPAPI_KEY when it is set, else skip
            Google Scholar.
        save: Where to write the report rows as a CSV file.
            Values: None, a path that ends with ".csv", or a folder (then <folder>/downloads.csv).
            Default None: write no report file.

    Returns:
        A list of dicts, one per DOI, with the keys
            doi      the DOI, in lowercase
            status   "downloaded", "already_there", "skipped_licence", "not_found" or "error"
            source   for a download, the source that gave the PDF (a value of `sources`), else ""
            licence  the OpenAlex licence, "none" (no open-access copy) or "unknown" (OpenAlex
                     does not know the DOI); "" for "already_there" and "error"
            file     the file name of the PDF, or "" when there is no PDF
            note     why a DOI has no PDF ("<source>: <reason>" for each source), else ""

    Raises:
        ValueError: when `sources` is empty or holds a name that is not one of the sources above.

    Example:
        >>> refs = extract_references("sample_files")                                   # doctest: +SKIP
        >>> report = download_papers(refs, "outputs/round_2", licences=["cc-by"])       # doctest: +SKIP
        >>> report[0]["status"], report[0]["source"]                                     # doctest: +SKIP
        ('downloaded', 'openalex')
    """
    source_list = _check_sources(sources)
    settings = {"email": email, "core_api_key": core_api_key, "serpapi_key": serpapi_key,
                "respect_robots": respect_robots}
    doi_list = _doi_list(dois)
    os.makedirs(output_dir, exist_ok=True)
    rows = []
    start = time.time()
    for i, doi in enumerate(doi_list):
        print(f"\r  downloading {i + 1} of {len(doi_list)}", end="")
        try:
            rows.append(_download_one(doi, output_dir, licences, source_list, settings))
        except (urllib.error.URLError, OSError, ValueError) as error:
            rows.append(_row(doi, "error", note=f"{type(error).__name__}: {error}"[:200]))
    print()

    # The log in the PDF folder tells harvest() the DOI of each file, also when the PDF does not print it.
    _update_log(output_dir, rows)
    saved_to = ""
    if save:
        saved_to = _save_csv(rows, save, REPORT_CSV_NAME, REPORT_COLUMNS)
    _print_summary(output_dir, rows, time.time() - start, saved_to, source_list, respect_robots)
    return rows


def _update_log(output_dir, rows):
    """Write the report rows into <output_dir>/downloads.csv. Keep the rows of earlier runs for other DOIs.

    A row of this run replaces the row of an earlier run for the same DOI. So the log of a folder
    lists every DOI that a run in this folder asked for, with its last status and file.
    harvest() reads this log to know the DOI of each downloaded PDF.
    """
    path = os.path.join(output_dir, REPORT_CSV_NAME)
    by_doi = {}
    if os.path.isfile(path):
        with open(path, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                by_doi[row["doi"]] = row
    for row in rows:
        by_doi[row["doi"]] = row
    _save_csv(list(by_doi.values()), path, REPORT_CSV_NAME, REPORT_COLUMNS)


def _print_summary(output_dir, rows, seconds, saved_to, sources, respect_robots):
    """Print one short summary of a download_papers() run."""
    counts = {}
    by_source = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
        if row["status"] == "downloaded":
            by_source[row["source"]] = by_source.get(row["source"], 0) + 1
    parts = [f"{status}: {counts[status]}" for status in STATUSES if status in counts]
    print(f"download: {len(rows)} DOIs -> {output_dir} in {seconds / 60:.1f} min")
    print(f"  sources: {', '.join(sources)} | respect_robots={respect_robots}")
    print(f"  {' | '.join(parts)}")
    if by_source:
        print(f"  downloaded from: {by_source}")
    if saved_to:
        print(f"  saved: {saved_to}")
