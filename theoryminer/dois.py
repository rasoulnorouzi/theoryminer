"""dois — find the DOI of each paper in a PDF, or in a folder of PDFs.

One call does the full job:

    from theoryminer import extract_dois
    rows = extract_dois("sample_files")                        # a list, one row per file
    rows = extract_dois("sample_files", save="outputs")        # also writes outputs/dois.csv

A paper holds many DOIs, most of them in its reference list. The DOI of the
paper itself is printed at the top of the first page, in the header, the
citation box or the footer. So the rule is: the first DOI on page 1, else the
first DOI on page 2. The rule was checked by hand on the 7 sample papers:
7 of 7 correct.

A bad file does not stop the run. It gets a row with its status. The page
text comes from the same reader and cache as harvest(), so a later harvest()
of the same files is fast. The only files that the function writes are the
page caches (<pdf>.pages.json) and, with save=, the CSV file.
"""

import csv
import os
import re

from .harvest import _doc_id, _list_pdfs, _read_pages

# The characters of a DOI, as Crossref recommends: "10.", a registrant code, "/", a suffix.
# Matches:  "doi: 10.3389/fpsyg.2021.728657"   -> "10.3389/fpsyg.2021.728657"
# Stops at: "10.3389/fpsyg.2021.728657*"       -> the "*" is not part of the DOI
# No match: "page 10.5 of the report"
RE_DOI = re.compile(r"10\.\d{4,9}/[-._;()/:a-z0-9]+", re.I)

FIRST_PAGES = 2       # the DOI of the paper itself is on page 1; page 2 covers a cover page
CSV_NAME = "dois.csv"  # the file name when save= gives a folder
COLUMNS = ["doc_id", "file", "doi", "page", "status", "note"]


def _clean_doi(doi):
    """Remove the punctuation that ends a sentence, and write the DOI in lowercase.

    A DOI does not depend on case, so lowercase makes two DOIs easy to compare.
    A closing bracket stays when the DOI also holds its opening bracket.

    Example:
        >>> _clean_doi("10.3389/FPSYG.2021.728657.")
        '10.3389/fpsyg.2021.728657'
        >>> _clean_doi("10.1016/S0140-6736(20)30183-5")
        '10.1016/s0140-6736(20)30183-5'
        >>> _clean_doi("10.1016/S0140-6736(20)30183-5).")
        '10.1016/s0140-6736(20)30183-5'
    """
    doi = doi.rstrip(".,;:/")
    if doi.count(")") > doi.count("("):
        doi = doi.rstrip(")")
    return doi.lower()


def _first_doi(page_md, first_pages=FIRST_PAGES):
    """Return the first DOI on the first pages, and its page number.

    Args:
        page_md: The dict {page number: markdown} of one PDF, as _read_pages() gives it.
        first_pages: Search pages 1 to this number, in order.

    Returns:
        (doi, page). ("", 0) when no page holds a DOI.

    Example:
        >>> _first_doi({1: "Header only", 2: "doi: 10.1186/s12889-018-5621-4", 9: "10.1016/j.x"})
        ('10.1186/s12889-018-5621-4', 2)
    """
    for page in range(1, first_pages + 1):
        match = RE_DOI.search(page_md.get(page, ""))
        if match:
            return _clean_doi(match.group(0)), page
    return "", 0


def _doi_row(path, doi="", page=0, status="found", note=""):
    """Return one result row for one file.

    Example:
        >>> _doi_row("papers/notes.txt", status="not_pdf", note="the file name does not end with .pdf")
        {'doc_id': 'notes', 'file': 'notes.txt', 'doi': '', 'page': 0, 'status': 'not_pdf', 'note': 'the file name does not end with .pdf'}
    """
    return {"doc_id": _doc_id(path), "file": os.path.basename(path), "doi": doi,
            "page": page, "status": status, "note": note}


def _doi_of_pdf(pdf_path, first_pages, cache):
    """Find the DOI of one PDF. Return its row. A PDF that cannot be read gives a row, not an error."""
    try:
        page_md = _read_pages(pdf_path, cache)
    except ValueError as error:
        return _doi_row(pdf_path, status="unreadable_pdf", note=str(error))
    doi, page = _first_doi(page_md, first_pages)
    if not doi:
        return _doi_row(pdf_path, status="not_found", note=f"no DOI on pages 1-{first_pages}")
    return _doi_row(pdf_path, doi=doi, page=page)


def _save_csv(rows, save):
    """Write the rows to a CSV file. Return the path of the file.

    Args:
        rows: The result rows.
        save: A path that ends with ".csv", or a folder. For a folder, the file
            is <folder>/dois.csv. A missing folder is made.
    """
    path = save
    if not save.lower().endswith(".csv"):
        path = os.path.join(save, CSV_NAME)
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def extract_dois(source, save=None, first_pages=FIRST_PAGES, cache=True):
    """Find the DOI of each paper in one PDF, or in every PDF in a folder.

    The rule: the first DOI on page 1, else the first DOI on page 2. A bad file
    does not stop the run. It gets a row with the status "not_pdf" or
    "unreadable_pdf". A PDF without a DOI on its first pages gets "not_found".

    Args:
        source: Path of a PDF file, or of a folder with PDF files. The function
            looks in the folder only, not in its subfolders.
        save: None writes no file. A path that ends with ".csv" writes that file.
            A folder writes <folder>/dois.csv. A missing folder is made.
        first_pages: Search pages 1 to this number. A larger value can find a DOI
            that is not on the first page, and also a DOI from the reference list.
        cache: Read and write the page cache <pdf>.pages.json beside each PDF,
            as harvest() does.

    Returns:
        A list of dicts, one per file, in file-name order, with the keys
        doc_id, file, doi, page, status, note. doi is lowercase, or "" when none
        was found.

    Raises:
        ValueError: The source does not exist, or the folder has no PDF.

    Example:
        >>> rows = extract_dois("sample_files/barrech_2018_job_insecurity_health.pdf")   # doctest: +SKIP
        >>> rows[0]["doi"]                                                             # doctest: +SKIP
        '10.1186/s12889-018-5621-4'
    """
    # 1. Find the files. A page cache can stand in for its PDF, as in harvest().
    if os.path.isdir(source):
        pdf_paths, other_paths = _list_pdfs(source)
        if not pdf_paths:
            other_names = [os.path.basename(p) for p in other_paths]
            raise ValueError(f"no PDF file in the folder {source!r}; files found: {other_names}")
    elif os.path.isfile(source) or os.path.isfile(source + ".pages.json"):
        pdf_paths, other_paths = [source], []
    else:
        raise ValueError(f"no file or folder at {source!r}; give a PDF file or a folder of PDF files")

    # 2. One row per file: first the files that are not PDFs, then each PDF.
    rows = []
    for path in other_paths:
        rows.append(_doi_row(path, status="not_pdf", note="the file name does not end with .pdf"))
    for i, path in enumerate(pdf_paths):
        print(f"\r  reading .pdf file {i + 1} of {len(pdf_paths)}", end="")
        rows.append(_doi_of_pdf(path, first_pages, cache))
    print()
    rows.sort(key=_file_name)

    # 3. Save when asked, and print one summary.
    saved_to = ""
    if save:
        saved_to = _save_csv(rows, save)
    _print_summary(source, rows, saved_to)
    return rows


def _file_name(row):
    """Return the file name of a row. Used to sort the rows by file name."""
    return row["file"]


def _print_summary(source, rows, saved_to):
    """Print one short summary of an extract_dois() run."""
    found = [r for r in rows if r["status"] == "found"]
    not_found = [r for r in rows if r["status"] == "not_found"]
    skipped = [r for r in rows if r["status"] in ("not_pdf", "unreadable_pdf")]
    print(f"dois: {source}")
    print(f"  files: {len(rows)} | found: {len(found)} | not found: {len(not_found)} | skipped: {len(skipped)}")
    for row in not_found + skipped:
        print(f"    {row['status']}: {row['file']}: {row['note']}")
    if saved_to:
        print(f"  saved: {saved_to}")
