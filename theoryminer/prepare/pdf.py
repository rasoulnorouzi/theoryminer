"""pdf — read the files of stage 1: list the PDFs of a folder, and read the text of each page.

harvest() and the DOI functions (dois.py) both use these helpers. So they are in their own
module, and harvest.py and dois.py do not import each other in a circle.
"""

import json
import os
import re

# A character that is not safe in a file name on every system. A DOI can hold "/", ":", "<", ">" and ";".
# download_papers() names each PDF after its DOI with this rule; harvest() uses the same rule to
# recognise the DOI of a downloaded file.
# Matches: "/" in "10.1093/pubmed"   No match: "fdy133"
RE_UNSAFE = re.compile(r"[^a-z0-9_-]", re.I)


def _doc_id(path):
    """Return the file name without its folder and its extension.

    Example:
        >>> _doc_id("sample_files/smith_2021_trust.pdf")
        'smith_2021_trust'
    """
    name = os.path.basename(path)
    return os.path.splitext(name)[0]


def _list_pdfs(folder):
    """Find the PDF files and the other files in a folder.

    The function looks in the folder only, not in its subfolders.
    It ignores hidden files and the page caches (*.pages.json).
    A name that ends with ".pdf" or ".PDF" is a PDF.

    Args:
        folder: Path of the folder.

    Returns:
        Two sorted lists of paths: the PDF files and the other files.

    Example:
        >>> pdfs, others = _list_pdfs("sample_files")
        >>> others
        ['sample_files/SOURCES.md']
    """
    pdf_paths = []
    other_paths = []
    for name in sorted(os.listdir(folder)):
        path = os.path.join(folder, name)
        if name.startswith(".") or name.endswith(".pages.json") or not os.path.isfile(path):
            continue
        if name.lower().endswith(".pdf"):
            pdf_paths.append(path)
        else:
            other_paths.append(path)
    return pdf_paths, other_paths


def _load_cache(cache_path):
    """Read a page cache. Return None when the file is not valid JSON.

    A broken cache can stay behind when a run stops during the write.
    The caller then extracts the pages again.
    """
    try:
        with open(cache_path, encoding="utf-8") as fh:
            page_md = json.load(fh)
    except ValueError:
        return None
    pages = {}
    for page, markdown in page_md.items():
        pages[int(page)] = markdown
    return pages


def _read_pages(pdf_path, cache=True):
    """Return the markdown text of each page of a PDF.

    The first run extracts the pages with pdf_inspector. With cache=True,
    it saves them to <pdf>.pages.json. The next run reads that file.

    Args:
        pdf_path: Path of the PDF file.
        cache: Read and write the page cache beside the PDF.

    Returns:
        A dict {page number: markdown}. Page numbers start at 1, as in a PDF viewer.

    Raises:
        ValueError: The file is not a PDF, the PDF is broken, or no page has text.

    Example:
        >>> pages = _read_pages("README.md")
        Traceback (most recent call last):
        ValueError: Not a PDF: file appears to be plain text
    """
    cache_path = pdf_path + ".pages.json"

    # 1. Use the cache when it exists and is valid.
    page_md = None
    if cache and os.path.exists(cache_path):
        page_md = _load_cache(cache_path)

    # 2. Otherwise extract the pages. pdf_inspector raises ValueError for a bad file.
    if page_md is None:
        import pdf_inspector
        result = pdf_inspector.extract_pages_markdown(pdf_path)
        page_md = {}
        for page in result.pages:
            page_md[page.page + 1] = page.markdown   # the library counts pages from 0
        if cache:
            with open(cache_path, "w", encoding="utf-8") as fh:
                json.dump(page_md, fh)

    # 3. A scanned PDF has pages but no text. OCR is not part of this package.
    all_text = "".join(page_md.values())
    if not all_text.strip():
        raise ValueError("no text layer; the PDF may be a scan, and OCR is not supported")
    return page_md


def _safe_name(doi):
    """Return the DOI as a file name without its extension: every unsafe character becomes "_".

    Example:
        >>> _safe_name("10.1093/pubmed/fdy133")
        '10_1093_pubmed_fdy133'
    """
    return RE_UNSAFE.sub("_", doi)
