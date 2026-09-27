"""dois — the DOI of each paper, and the DOIs in its references.

    from theoryminer import extract_dois, extract_references
    rows = extract_dois("sample_files")                        # the DOI and title of each paper
    rows = extract_dois("sample_files", save="outputs")        # also writes outputs/dois.csv
    refs = extract_references("sample_files", save="outputs")  # the DOIs that the papers cite
                                                               # -> outputs/references.csv

A paper holds many DOIs, most of them in its reference list. The DOI of the
paper itself is printed at the top of the first page, in the header, the
citation box or the footer. So the rule is: the first DOI on page 1, else the
first DOI on page 2. The rule was checked by hand on the 7 sample papers:
7 of 7 correct.

Each row also gets the title of the paper. The title is the text in the
largest font on page 1 that has at least MIN_TITLE_WORDS words. A shorter
text in a large font is a journal banner ("PLOS ONE"), so the rule skips it.
When no text passes, the title field of the PDF metadata is used, if it looks
like a title. Else the title is "". Test on the 7 sample papers: the font rule
found 7 of 7 titles; the metadata alone had 5 of 7.

A bad file does not stop the run. It gets a row with its status. The page
text comes from the same reader and cache as harvest(), so a later harvest()
of the same files is fast. The only files that the function writes are the
page caches (<pdf>.pages.json) and, with save=, the CSV file.
"""

import collections
import csv
import os
import re
from urllib.parse import unquote

import pdf_inspector

from .harvest import _doc_id, _list_pdfs, _read_pages

# The characters of a DOI, as Crossref recommends: "10.", a registrant code, "/", a suffix.
# An old Wiley DOI (SICI) also holds one "<number::code>" part. Only that form may hold "<" and ">",
# so an HTML tag after a DOI ("<sup>") stays out.
# Matches:  "doi: 10.3389/fpsyg.2021.728657"   -> "10.3389/fpsyg.2021.728657"
#           "10.1002/1098-237X(200011)84:6<740::AID-SCE4>3.0.CO;2-3" (the whole DOI)
# Stops at: "10.3389/fpsyg.2021.728657*"       -> the "*" is not part of the DOI
# No match: "page 10.5 of the report"
DOI_CHAR = r"(?:[-._;()/:a-z0-9]|<\d+::[a-z0-9-]+>)"
RE_DOI = re.compile(r"10\.\d{4,9}/" + DOI_CHAR + "+", re.I)

# The end of a publisher web address after a DOI: "10.1111/j.1745-9125.1991.tb01087.x/full".
# No match: "10.1037//0033-2909.128.1.3" (the "//" belongs to that DOI)
RE_URL_TAIL = re.compile(r"/(?:full|abstract|pdf|epdf|fulltext|html)$", re.I)

# A word broken at the end of a title line: "Autonomy- Supportive" -> "Autonomy-Supportive".
# No match: "health - results" (a space before the hyphen: a dash, not a broken word)
RE_BROKEN_WORD = re.compile(r"(\w)- (\w)")

# A metadata title that is a file name, not a title: "Microsoft Word - final_v3.docx".
# No match: "Who are Your Joneses? Socio-Specific Income Inequality and Trust"
RE_FILE_NAME = re.compile(r"\.(docx?|pdf|tex|indd|rtf)\b|^microsoft word\b", re.I)

# A markdown link: [text](url). The page text writes a DOI link twice, once in each part, so the link
# keeps only its url. Matches: "[https://doi.org/10.1/x](https://doi.org/10.1/x)" -> "https://doi.org/10.1/x"
RE_MD_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]*)\)")

# A DOI that the PDF cut at a line end. The parts: the first part, a dot, one space or line break,
# a dot, and the rest. Each dot is optional. The rest has DOI characters only, so a word does not match.
# Matches:  "10.1007/s1096 4-015-0354-5"   -> "10.1007/s10964-015-0354-5"
#           "10.1097/YCO. 0b013e32816ebc8c" -> "10.1097/YCO.0b013e32816ebc8c"
#           "10.3389/fpubh\n.2024.1392999." -> "10.3389/fpubh.2024.1392999"
#           "10.1093/ applin/amu02"        -> "10.1093/applin/amu02" (the cut is right after the "/")
# No match: "10.1037/abc. Accessed 2021" (the next piece has no digit, or it is a year: see _join_cut_doi)
# The two last groups look ahead: the punctuation and the space after the rest.
RE_CUT_DOI = re.compile(r"(10\.\d{4,9}/(?:" + DOI_CHAR + r"*[-_/a-z0-9])?)(\.?)([ \n])(\.?)"
                        r"([0-9a-z]" + DOI_CHAR + r"*[0-9a-z]|[0-9])(?=([.,;]?)(\s|$))", re.I)

# A DOI start ("10." + a registrant code + "/") that the PDF cut with one space or line break.
# Matches:  "10.1 186/s12888", "10.1186 /s13034", "10. 1111/j.1475", "1\n0.1016/j.ridd"
# No match: "10.1186/s13034" is matched too, but it has no space, so _join_cut_prefix keeps it as it is.
RE_CUT_PREFIX = re.compile(r"(?<![\w.])1\s?0\s?\.\s?(\d(?:\s?\d){3,8})\s?/")

# A "/" written as "%2F" in a web address: "10.1177%2F1362168817725759".
RE_ENCODED_SLASH = re.compile(r"%2F", re.I)

# A year, which often follows a DOI in a reference and is never the rest of a DOI.
# Matches: "2021", "2019a"   No match: "17970"
RE_YEAR = re.compile(r"^(?:19|20)\d\d[a-z]?$")

FIRST_PAGES = 2       # the DOI of the paper itself is on page 1; page 2 covers a cover page
MIN_TITLE_WORDS = 4   # a title has at least this many words; a shorter large text is a banner
CSV_NAME = "dois.csv"  # the file name when save= gives a folder
COLUMNS = ["doc_id", "file", "doi", "title", "page", "status", "note"]
REFERENCES_CSV_NAME = "references.csv"      # the file name of extract_references() when save= gives a folder
REFERENCE_COLUMNS = ["doi", "n_seeds", "cited_by"]


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
        >>> _clean_doi("10.1111/j.1745-9125.1991.tb01087.x/full.")
        '10.1111/j.1745-9125.1991.tb01087.x'
    """
    doi = doi.rstrip(".,;:/")
    if doi.count(")") > doi.count("("):
        doi = doi.rstrip(")")
    doi = RE_URL_TAIL.sub("", doi)
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


def _doi_row(path, doi="", page=0, status="found", note="", title=""):
    """Return one result row for one file.

    Example:
        >>> _doi_row("papers/notes.txt", status="not_pdf", note="the file name does not end with .pdf")
        {'doc_id': 'notes', 'file': 'notes.txt', 'doi': '', 'title': '', 'page': 0, 'status': 'not_pdf', 'note': 'the file name does not end with .pdf'}
    """
    return {"doc_id": _doc_id(path), "file": os.path.basename(path), "doi": doi, "title": title,
            "page": page, "status": status, "note": note}


def _clean_title(text):
    """Join the words of a title into one line, and repair a word broken at a line end.

    Example:
        >>> _clean_title("The Influence of Autonomy-   Supportive  Teaching")
        'The Influence of Autonomy-Supportive Teaching'
    """
    text = " ".join(text.split())
    return RE_BROKEN_WORD.sub(r"\1-\2", text)


def _font_size(item):
    """Return the font size of a text item, rounded. Used to group the text by size."""
    return round(item.font_size, 1)


def _font_title(pdf_path):
    """Return the text in the largest font on page 1 that has at least MIN_TITLE_WORDS words, or ""."""
    items = []
    for item in pdf_inspector.extract_text_with_positions(pdf_path):
        if item.page == 1 and item.text.strip():
            items.append(item)
    sizes = sorted({_font_size(item) for item in items}, reverse=True)
    for size in sizes:
        words = [item.text for item in items if _font_size(item) == size]
        text = _clean_title(" ".join(words))
        if len(text.split()) >= MIN_TITLE_WORDS:
            return text
    return ""


def _metadata_title(pdf_path):
    """Return the title field of the PDF metadata when it looks like a title, else ""."""
    title = _clean_title(pdf_inspector.process_pdf(pdf_path).title or "")
    if len(title.split()) < MIN_TITLE_WORDS:
        return ""
    if RE_FILE_NAME.search(title):
        return ""
    return title


def _title_of_pdf(pdf_path):
    """Return the title of the paper: the largest font on page 1, else the PDF metadata, else "".

    A page cache without its PDF gives "": the title needs the font sizes of the PDF itself.
    """
    if not os.path.isfile(pdf_path):
        return ""
    try:
        title = _font_title(pdf_path)
        if not title:
            title = _metadata_title(pdf_path)
    except ValueError:
        return ""
    return title


def _doi_of_pdf(pdf_path, first_pages, cache):
    """Find the DOI of one PDF. Return its row. A PDF that cannot be read gives a row, not an error."""
    try:
        page_md = _read_pages(pdf_path, cache)
    except ValueError as error:
        return _doi_row(pdf_path, status="unreadable_pdf", note=str(error))
    doi, page = _first_doi(page_md, first_pages)
    title = _title_of_pdf(pdf_path)
    if not doi:
        return _doi_row(pdf_path, status="not_found", note=f"no DOI on pages 1-{first_pages}", title=title)
    return _doi_row(pdf_path, doi=doi, page=page, title=title)


def _save_csv(rows, save, name=CSV_NAME, columns=COLUMNS):
    """Write the rows to a CSV file. Return the path of the file.

    Args:
        rows: The result rows.
        save: A path that ends with ".csv", or a folder. For a folder, the file
            is <folder>/<name>. A missing folder is made.
        name: The file name for a folder.
        columns: The columns of the file, in order.
    """
    path = save
    if not save.lower().endswith(".csv"):
        path = os.path.join(save, name)
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    return path


def _source_pdfs(source):
    """Return (pdf_paths, other_paths) for a PDF file or a folder, as harvest() finds them.

    Raises:
        ValueError: The source does not exist, or the folder has no PDF.
    """
    if os.path.isdir(source):
        pdf_paths, other_paths = _list_pdfs(source)
        if not pdf_paths:
            other_names = [os.path.basename(p) for p in other_paths]
            raise ValueError(f"no PDF file in the folder {source!r}; files found: {other_names}")
        return pdf_paths, other_paths
    if os.path.isfile(source) or os.path.isfile(source + ".pages.json"):
        return [source], []
    raise ValueError(f"no file or folder at {source!r}; give a PDF file or a folder of PDF files")


def extract_dois(source, save=None, first_pages=FIRST_PAGES, cache=True):
    """Find the DOI and the title of each paper in one PDF, or in every PDF in a folder.

    The DOI rule: the first DOI on page 1, else the first DOI on page 2. The title
    rule: the largest font on page 1 with at least MIN_TITLE_WORDS words, else the
    title in the PDF metadata. A bad file
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
        doc_id, file, doi, title, page, status, note. doi is lowercase, or "" when
        none was found. title is "" when no title was found.

    Raises:
        ValueError: The source does not exist, or the folder has no PDF.

    Example:
        >>> rows = extract_dois("sample_files/barrech_2018_job_insecurity_health.pdf")   # doctest: +SKIP
        >>> rows[0]["doi"]                                                             # doctest: +SKIP
        '10.1186/s12889-018-5621-4'
    """
    # 1. Find the files. A page cache can stand in for its PDF, as in harvest().
    pdf_paths, other_paths = _source_pdfs(source)

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


# ---------------------------------------------------------------------------
# The DOIs in the references of the seed papers.
# ---------------------------------------------------------------------------

def _join_cut_prefix(match):
    """Return the DOI start without its space, when the match holds at most one space or line break.

    Example:
        >>> _join_cut_prefix(RE_CUT_PREFIX.search("https://doi.org/10.1 186/s12888"))
        '10.1186/'
        >>> _join_cut_prefix(RE_CUT_PREFIX.search("see 1 0. 1 234/5"))
        '1 0. 1 234/'
    """
    text = match.group(0)
    if len(re.findall(r"\s", text)) > 1:
        return text
    return "10." + re.sub(r"\s", "", match.group(1)) + "/"


def _is_list_number(separator, piece, punctuation, space):
    """Return True when the piece is the number of the next reference: a line break, then "36. Smith J".

    A cut DOI that ends in a short number ("...2016.11.00", then "8." alone on the next line) is not a
    list number: its line ends after the dot.
    """
    if separator != "\n" or not piece.isdigit() or len(piece) > 3:
        return False
    return punctuation == "." and space == " "


def _join_cut_doi(match):
    """Return the joined DOI for a RE_CUT_DOI match, or the match unchanged when the piece is not a DOI part.

    Example:
        >>> _join_cut_doi(RE_CUT_DOI.search("10.1007/s1096 4-015-0354-5."))
        '10.1007/s10964-015-0354-5'
        >>> _join_cut_doi(RE_CUT_DOI.search("10.1016/j.psyneuen.2016.11.00\\n8.\\n88. Sahu MK"))
        '10.1016/j.psyneuen.2016.11.008'
        >>> _join_cut_doi(RE_CUT_DOI.search("10.1037/abc 2021."))
        '10.1037/abc 2021'
        >>> _join_cut_doi(RE_CUT_DOI.search("10.1037/abc.\\n36. Smith J"))
        '10.1037/abc.\\n36'
    """
    first, dot, separator, dot_after, piece, punctuation, space = match.groups()
    if not re.search(r"\d", piece) or RE_YEAR.match(piece):
        return match.group(0)
    if _is_list_number(separator, piece, punctuation, space):
        return match.group(0)
    return first + dot + dot_after + piece


def _text_dois(text):
    """Return every DOI in the text, cleaned, in lowercase, in reading order, without duplicates.

    The text is repaired first, in this order: a markdown link keeps only its url, "%2F" becomes "/",
    a cut DOI start ("10.1 186/") is joined, and a DOI cut after its start is joined.

    Example:
        >>> _text_dois("[https://doi.org/10.1177/](https://doi.org/10.1177/) 0149206316632058\\nSee doi:10.1177/0149206316632058.")
        ['10.1177/0149206316632058']
    """
    text = RE_MD_LINK.sub(r"\1", text)
    text = RE_ENCODED_SLASH.sub("/", text)
    text = RE_CUT_PREFIX.sub(_join_cut_prefix, text)
    text = RE_CUT_DOI.sub(_join_cut_doi, text)
    dois = []
    for match in RE_DOI.finditer(text):
        doi = _clean_doi(unquote(match.group(0)))
        if doi not in dois:
            dois.append(doi)
    return dois


def _reference_dois(pdf_path, cache):
    """Return (own_doi, reference_dois) of one PDF. The own DOI and its parts (figures, tables) are left out.

    Raises:
        ValueError: The PDF cannot be read.
    """
    page_md = _read_pages(pdf_path, cache)
    own, _ = _first_doi(page_md)
    text = "\n".join(page_md[page] for page in sorted(page_md))
    references = []
    for doi in _text_dois(text):
        if own and doi.startswith(own):
            continue                                  # the paper itself, or one of its figures or tables
        references.append(doi)
    return own, references


def _cited_by_count(row):
    """Return the sort key of a reference row: the most cited DOI first, then the DOI."""
    return (-row["n_seeds"], row["doi"])


def extract_references(source, save=None, cache=True):
    """Find the DOIs that the seed papers cite, for one PDF or every PDF in a folder.

    The function reads every page of each seed paper and finds each DOI. It repairs a DOI
    that the PDF cut at a line end ("10.1007/s1096 4-015-0354-5"). It leaves out the DOI of
    the seed itself and the DOIs of its parts (figures, tables). A reference that prints no
    DOI cannot be found. A bad file does not stop the run: the summary names it.

    Args:
        source: Path of a PDF file, or of a folder with PDF files (the seed papers).
        save: None writes no file. A path that ends with ".csv" writes that file. A folder
            writes <folder>/references.csv. The CSV has the columns doi, n_seeds, cited_by;
            a download tool can read its "doi" column.
        cache: Read and write the page cache <pdf>.pages.json beside each PDF, as harvest() does.

    Returns:
        A list of dicts, one per unique reference DOI, with the keys
            doi       the DOI, in lowercase
            n_seeds   the number of seed papers that cite it
            cited_by  the doc_ids of those seed papers
        The DOIs that most seeds cite come first.

    Raises:
        ValueError: The source does not exist, or the folder has no PDF.

    Example:
        >>> refs = extract_references("sample_files")                          # doctest: +SKIP
        >>> refs[0]["doi"], refs[0]["n_seeds"]                                  # doctest: +SKIP
        ('10.1037/0003-066x.55.1.68', 2)
    """
    pdf_paths, other_paths = _source_pdfs(source)

    # 1. The reference DOIs of each seed.
    cited_by = collections.OrderedDict()
    per_seed = {}
    unreadable = []
    for i, path in enumerate(pdf_paths):
        print(f"\r  reading .pdf file {i + 1} of {len(pdf_paths)}", end="")
        try:
            own, references = _reference_dois(path, cache)
        except ValueError as error:
            unreadable.append(f"{os.path.basename(path)}: {error}")
            continue
        per_seed[_doc_id(path)] = len(references)
        for doi in references:
            cited_by.setdefault(doi, []).append(_doc_id(path))
    print()

    # 2. One row per DOI, the most cited first.
    rows = []
    for doi, seeds in cited_by.items():
        rows.append({"doi": doi, "n_seeds": len(seeds), "cited_by": seeds})
    rows.sort(key=_cited_by_count)

    saved_to = ""
    if save:
        csv_rows = [{**row, "cited_by": " | ".join(row["cited_by"])} for row in rows]
        saved_to = _save_csv(csv_rows, save, REFERENCES_CSV_NAME, REFERENCE_COLUMNS)
    _print_reference_summary(source, rows, per_seed, other_paths, unreadable, saved_to)
    return rows


def _print_reference_summary(source, rows, per_seed, other_paths, unreadable, saved_to):
    """Print one short summary of an extract_references() run."""
    shared = [row for row in rows if row["n_seeds"] > 1]
    no_dois = [doc_id for doc_id, n in per_seed.items() if n == 0]
    print(f"references: {source}")
    print(f"  seeds read: {len(per_seed)} | unique reference DOIs: {len(rows)} | "
          f"cited by 2 or more seeds: {len(shared)}")
    for doc_id, n in per_seed.items():
        print(f"    {n:>5}  {doc_id}")
    if no_dois:
        print(f"  no DOI in the references of: {', '.join(no_dois)} (the journal printed none)")
    for path in other_paths:
        print(f"  skipped: {os.path.basename(path)} (the file name does not end with .pdf)")
    for note in unreadable:
        print(f"  skipped: {note}")
    if saved_to:
        print(f"  saved: {saved_to}")
