"""Measure the success rate of download_papers() on the fixed benchmark set.

Run it from the repository root:

    python benchmarks/downloader/run_benchmark.py --label baseline --email you@lab.org

The script downloads the PDFs of the DOIs in benchmarks/downloader/dois.csv into
outputs/benchmarks/downloader/<label>/ (gitignored: the PDFs have copyright).
It checks that each PDF is the correct paper: the DOI or the title must be on page 1 or 2.
It writes one row per DOI to benchmarks/downloader/results/<label>.csv and prints the rates:
all DOIs, the open-access DOIs, the closed DOIs, per publisher and per source.

A second run with the same label downloads only the DOIs that have no PDF yet.
Use a new label (or delete the folder) for a clean run.
"""

import argparse
import csv
import inspect
import os
import re
import sys
import time
import unicodedata

import pypdf

sys.path.insert(0, os.getcwd())      # the theoryminer of this repository, also without an install
from theoryminer import download_papers  # noqa: E402

DOIS_CSV = "benchmarks/downloader/dois.csv"
RESULTS_DIR = "benchmarks/downloader/results"
PDF_ROOT = "outputs/benchmarks/downloader"
CHECK_PAGES = 2          # the DOI or the title must be on one of the first 2 pages
TITLE_SHARE = 0.80       # a title counts as found when 80 % of its words are on those pages
RESULT_COLUMNS = ["doi", "publisher", "year", "oa_status", "status", "source", "check", "note"]

# A run of letters or digits of any script. It keeps non-Latin words (Japanese, Russian).
WORD = re.compile(r"\w+", re.UNICODE)
# Everything that is not a letter or a digit. Used to compare a DOI against mangled PDF text.
NOT_ALNUM = re.compile(r"[^a-z0-9]", re.IGNORECASE)


def fold(text):
    """Return the text in lowercase, without accents, so "Velázquez" matches "velazquez"."""
    stripped = unicodedata.normalize("NFKD", text)
    stripped = "".join(char for char in stripped if not unicodedata.combining(char))
    return stripped.lower()


def read_set(path):
    """Return the rows of the benchmark set."""
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def words_of(text):
    """Return the folded words of a text (lowercase, no accents)."""
    return WORD.findall(fold(text))


def first_pages_text(pdf_path):
    """Return the text of the first CHECK_PAGES pages, or "" when the PDF cannot be read."""
    try:
        reader = pypdf.PdfReader(pdf_path)
        pages = reader.pages[:CHECK_PAGES]
        return " ".join(page.extract_text() or "" for page in pages)
    except Exception:                      # a broken PDF is a failed check, not a stopped run
        return ""


def check_pdf(pdf_path, doi, title):
    """Return "doi", "title", "no_text" or "wrong_paper": how the PDF matches the paper.

    "doi": the DOI is on page 1 or 2. "title": TITLE_SHARE of the title words are there.
    "no_text": the PDF gives no text (a scan). "wrong_paper": neither the DOI nor the title.
    """
    text = first_pages_text(pdf_path)
    if not text.strip():
        return "no_text"
    # The DOI, ignoring punctuation and spaces: PDF extraction often adds a hyphen or a space.
    flat = NOT_ALNUM.sub("", text)
    if NOT_ALNUM.sub("", doi).lower() in flat.lower():
        return "doi"
    title_words = words_of(title)
    if not title_words:
        return "wrong_paper"
    page_words = set(words_of(text))
    n_found = 0
    for word in title_words:
        if word in page_words:
            n_found += 1
    if n_found / len(title_words) >= TITLE_SHARE:
        return "title"
    return "wrong_paper"


def rate(rows):
    """Return "found/total (percent)" for the rows: a row counts when its PDF passed the check."""
    if not rows:
        return "0/0"
    n_good = 0
    for row in rows:
        if row["check"] in ("doi", "title"):
            n_good += 1
    return f"{n_good}/{len(rows)} ({100 * n_good / len(rows):.0f} %)"


def group_by(rows, key):
    """Return {value: rows} for one column."""
    groups = {}
    for row in rows:
        groups.setdefault(row[key] or "(none)", []).append(row)
    return groups


def print_report(label, rows, seconds):
    """Print the success rates of one run."""
    open_rows = [row for row in rows if row["oa_status"] not in ("closed",) and not row["oa_status"].startswith("lookup")]
    closed_rows = [row for row in rows if row["oa_status"] == "closed"]
    wrong = [row for row in rows if row["check"] in ("wrong_paper", "no_text")]
    print(f"\nbenchmark '{label}': {len(rows)} DOIs in {seconds / 60:.1f} min")
    print(f"  correct PDF, all DOIs:      {rate(rows)}")
    print(f"  correct PDF, open access:   {rate(open_rows)}")
    print(f"  correct PDF, closed:        {rate(closed_rows)}")
    print(f"  PDF that failed the check:  {len(wrong)}")
    print("  per open-access status:")
    for status, group in sorted(group_by(rows, "oa_status").items()):
        print(f"    {status:12s} {rate(group)}")
    print("  per publisher (open access only):")
    for publisher, group in sorted(group_by(open_rows, "publisher").items(), key=lambda item: -len(item[1])):
        print(f"    {publisher[:40]:40s} {rate(group)}")
    print("  per source (correct PDFs):")
    for source, group in sorted(group_by(rows, "source").items()):
        n_good = len([row for row in group if row["check"] in ("doi", "title")])
        if n_good:
            print(f"    {source:22s} {n_good}")


def run(label, email, limit, extra):
    """Run download_papers() on the benchmark set. Check every PDF. Return the result rows."""
    benchmark = read_set(DOIS_CSV)[:limit]
    folder = os.path.join(PDF_ROOT, label)
    start = time.time()
    report = download_papers([row["doi"] for row in benchmark], folder, email=email, **extra)
    seconds = time.time() - start
    by_doi = {row["doi"]: row for row in report}
    rows = []
    for item in benchmark:
        result = by_doi.get(item["doi"].lower(), {})
        check = ""
        if result.get("file"):
            check = check_pdf(os.path.join(folder, os.path.basename(result["file"])), item["doi"], item["title"])
        rows.append({"doi": item["doi"], "publisher": item["publisher"], "year": item["year"],
                     "oa_status": item["oa_status"], "status": result.get("status", ""),
                     "source": result.get("source", ""), "check": check, "note": result.get("note", "")})
    return rows, seconds


def save_rows(rows, label):
    """Write the result rows to RESULTS_DIR/<label>.csv. Return the path."""
    os.makedirs(RESULTS_DIR, exist_ok=True)
    path = os.path.join(RESULTS_DIR, label + ".csv")
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=RESULT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def extra_settings(args):
    """Return the settings for download_papers() that this version of the function accepts."""
    accepted = inspect.signature(download_papers).parameters
    extra = {}
    if args.sources and "sources" in accepted:
        extra["sources"] = args.sources.split(",")
    if args.ignore_robots and "respect_robots" in accepted:
        extra["respect_robots"] = False
    return extra


def main():
    """Read the command line, run the benchmark, save and print the results."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--label", required=True, help="the name of the run, for example 'baseline'")
    parser.add_argument("--email", default=os.environ.get("UNPAYWALL_EMAIL"), help="the email for the APIs")
    parser.add_argument("--limit", type=int, default=None, help="use only the first N DOIs")
    parser.add_argument("--sources", default="", help="comma-separated sources, when the function has sources=")
    parser.add_argument("--ignore-robots", action="store_true", help="respect_robots=False, when the function has it")
    args = parser.parse_args()
    rows, seconds = run(args.label, args.email, args.limit, extra_settings(args))
    path = save_rows(rows, args.label)
    print_report(args.label, rows, seconds)
    print(f"  saved: {path}")


if __name__ == "__main__":
    main()
