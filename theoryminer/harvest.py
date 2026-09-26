"""harvest — read a PDF, or a folder of PDFs, and return clean sentences.

One call does the full job:

    from theoryminer import harvest
    data = harvest("raw_data/my_book.pdf")     # one PDF
    data = harvest("sample_files")             # every PDF in a folder
    data["sentences"]   # the kept sentences
    data["dropped"]     # the drop log, with a reason per row

The function extracts the pages, cleans the text, and splits it into
sentences. Preprocessing is an ordered list of steps. You can remove a
step, change the order, or insert your own function. Each step receives
a list of row dicts and returns a list of row dicts. A step does not
delete a row. It sets kept=False and a drop_reason. This keeps every
drop visible in the returned drop log.

In a folder, a bad file does not stop the run. The drop log gets one
row for the file, with page 0 and one of these reasons:
    not_pdf         the file name does not end with ".pdf"
    unreadable_pdf  the PDF cannot be read, or it has no text layer
A page with no text gets one row with the reason "empty_page".

The only file that the function writes is the page cache,
<pdf>.pages.json, beside each PDF.
"""

import collections
import json
import os
import re
import unicodedata

from nltk.tokenize.punkt import PunktParameters, PunktSentenceTokenizer

# ---------------------------------------------------------------------------
# Fixed values. These come from the earlier notebook and stay predefined.
# ---------------------------------------------------------------------------

# Unicode replacements: curly quotes, long dashes, odd spaces, invisible marks.
QUOTES = {"‘": "'", "’": "'", "‚": "'", "‛": "'", "′": "'",
          "“": '"', "”": '"', "„": '"', "‟": '"', "″": '"'}
DASHES = {d: "-" for d in "‐‑‒–—―−"}
SPACES = {s: " " for s in "          　"}
KILL = {c: "" for c in "­​‌‍﻿"}
TRANS = str.maketrans({**QUOTES, **DASHES, **SPACES, **KILL})

# Markdown patterns: [text](url) links and *emphasis* markers.
RE_MDLINK = re.compile(r"\[([^\]]*)\]\((?:[^)]*)\)")
RE_EMPH = re.compile(r"(\*{1,3}|_{1,3})(?=\S)(.+?)(?<=\S)\1")

# Line-level junk patterns.
RE_HEADING = re.compile(r"^#{1,6}\s")
RE_TABLE = re.compile(r"^\s*\|")
RE_DOI = re.compile(r"^\s*(\[?https?://|10\.\d{4,}/|doi:)", re.I)
RE_NOSPACE = re.compile(r"^\s*[\w./:%-]+\s*$")
RE_PAGENUM = re.compile(r"^\s*[ivxlcdm\d]{1,6}\s*$", re.I)
RE_SECT_REF = re.compile(r"^#{1,6}\s*(references|bibliography|notes?|acknowledge?ments?)\s*$", re.I)
RE_CHAPTER = re.compile(r"^\s*(CHAPTER|PART)\s*$")
RE_INDEXY = re.compile(r"^\s*(index|contents|appendix)\s*$", re.I)
RE_TERMINAL = re.compile(r"[.!?][\"')\]]?$")

# Sentence-level patterns.
RE_YEAR = re.compile(r"(?:1[89]|20)\d{2}[a-z]?")
RE_PAREN = re.compile(r"\(([^()]{0,300}?)\)")
RE_BRACK = re.compile(r"\[([^\[\]]{0,300}?)\]")
RE_STAT = re.compile(r"[=<>]|\bp\s*[<>=]|\bn\s*=|\bSD\b|\bCI\b|%")
RE_LABEL = re.compile(r"^\s*(?:(?:key\s*words?|keywords?|source|notes?|abstract)\s*[:.]"
                      r"|(?:figure|fig\.|table|tab\.)\s*\d)", re.I)
RE_SEEALSO = re.compile(r"^\s*See also\b", re.I)
RE_PAGERANGE = re.compile(r"\d+[-]\d+")

# Abbreviations for the sentence splitter, so "e.g." does not end a sentence.
ABBREV = """e.g i.e cf al vs viz etc resp approx fig figs tab eq ch chap sec no vol
pp p ed eds trans repr rev suppl dr prof mr mrs ms st jr sr univ dept inc ltd
u.s u.k a.m p.m n.b ibid op.cit et""".split()
_params = PunktParameters()
_params.abbrev_types = set(ABBREV)
SPLITTER = PunktSentenceTokenizer(_params)

# Short tokens that are real words, not broken running-head letters.
LEGIT_SHORT = set("a i is it in of to on at as by be or if we he do so no up an my us me ah oh id "
                  "et al eg ie cf vs pp ed op ff".split())

# Thresholds for the junk rules.
MIN_ALPHA = 0.50     # a sentence needs at least this share of letters
MAX_DIGIT = 0.20     # a sentence with more digits than this is junk
MAX_SPACED = 0.25    # share of broken short tokens that marks a mangled line
LONG_FLAG = 80       # a longer sentence gets a flag, not a drop


# ---------------------------------------------------------------------------
# Small helpers.
# ---------------------------------------------------------------------------

def _alpha_ratio(text):
    """Return the share of letters and spaces in the text."""
    if not text:
        return 0.0
    good = sum(1 for ch in text if ch.isalpha() or ch.isspace())
    return good / len(text)


def _spaced_letter_ratio(words):
    """Return the share of broken short tokens, like 'Jacq ues F ores t'."""
    if not words:
        return 0.0
    bad = 0
    for w in words:
        letters = re.sub(r"[^A-Za-z]", "", w)
        if letters and len(letters) <= 2 and letters.lower() not in LEGIT_SHORT:
            bad = bad + 1
    if bad < 3:
        return 0.0
    return bad / len(words)


def _is_citation(inner):
    """Return True when the parenthesis content is a citation."""
    years = RE_YEAR.findall(inner)
    if not years:
        return False
    if len(years) >= 2 and (";" in inner or "et al" in inner):
        return True
    if len(re.findall(r"[A-Za-z]+", inner)) > 12:
        return False
    if re.search(r"[A-Z][a-z]+|et al\.?|&|;", inner):
        return True
    return inner.strip().isdigit()


def _is_stat(inner):
    """Return True when the parenthesis content is a statistic."""
    if not RE_STAT.search(inner):
        return False
    nonalpha = sum(1 for c in inner if not c.isalpha() and not c.isspace())
    if nonalpha / max(len(inner), 1) <= 0.15:
        return False
    return len(re.findall(r"[A-Za-z]{4,}", inner)) <= 4


def _tidy(text):
    """Remove the leftovers after a parenthesis removal."""
    text = re.sub(r"\s+([,.;:])", r"\1", text)
    text = re.sub(r"\(\s*\)|\[\s*\]", "", text)
    text = re.sub(r"[,;]\s*([.!?])", r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


def _page_list(spec):
    """Turn a page selection into a set of page numbers.

    Pages are 1-indexed, as printed in a PDF viewer.
    Accepted forms: a list of ints, one int, or a string like "12-540" or "3,7,9-12".
    """
    if isinstance(spec, int):
        return {spec}
    if isinstance(spec, str):
        pages = set()
        for part in spec.split(","):
            part = part.strip()
            if "-" in part:
                lo, hi = part.split("-", 1)
                pages.update(range(int(lo), int(hi) + 1))
            elif part:
                pages.add(int(part))
        return pages
    return set(int(p) for p in spec)


# ---------------------------------------------------------------------------
# The steps. Every step takes a list of row dicts and returns a list of
# row dicts. A step marks a bad row with kept=False and a drop_reason.
# ---------------------------------------------------------------------------

def fix_unicode(rows):
    """Normalize unicode: ligatures, quotes, dashes, spaces, invisible marks."""
    for r in rows:
        text = unicodedata.normalize("NFKC", r["text"])
        r["text"] = text.translate(TRANS)
    return rows


def strip_markdown(rows):
    """Remove link and emphasis markers. Keep the words."""
    for r in rows:
        text = RE_MDLINK.sub(r"\1", r["text"])
        r["text"] = RE_EMPH.sub(r"\2", text)
    return rows


def drop_running_heads(rows):
    """Drop lines that repeat across pages, like a chapter header."""
    counts = collections.Counter()
    for r in rows:
        line = r["text"].strip()
        if 0 < len(line) <= 90:
            counts[line] = counts[line] + 1
    heads = set(line for line, n in counts.items() if n >= 3)
    for r in rows:
        if r["kept"] and r["text"].strip() in heads:
            r["kept"] = False
            r["drop_reason"] = "running_head"
    return rows


def drop_junk_lines(rows):
    """Drop structural junk lines and record the section of each line.

    A heading line sets the section name for the lines after it.
    A reference section is dropped until the next chapter marker.
    """
    section = ""
    in_refs = False
    for r in rows:
        if not r["kept"]:
            continue
        line = r["text"].strip()
        if RE_SECT_REF.match(line):
            in_refs = True
        if RE_CHAPTER.match(line):
            in_refs = False
        if in_refs:
            r["kept"] = False
            r["drop_reason"] = "reference_section"
            continue
        r["section"] = section
        if not line:
            r["kept"] = False
            r["drop_reason"] = "blank"
        elif RE_CHAPTER.match(line):
            r["kept"] = False
            r["drop_reason"] = "chapter_marker"
        elif RE_INDEXY.match(line):
            r["kept"] = False
            r["drop_reason"] = "front_back_matter"
        elif RE_TABLE.match(line):
            r["kept"] = False
            r["drop_reason"] = "table_row"
        elif RE_HEADING.match(line):
            section = re.sub(r"^#+\s*", "", line)
            r["kept"] = False
            r["drop_reason"] = "heading"
        elif RE_PAGENUM.match(line):
            r["kept"] = False
            r["drop_reason"] = "page_number"
        elif RE_DOI.match(line):
            r["kept"] = False
            r["drop_reason"] = "doi_url"
        elif RE_NOSPACE.match(line) and any(ch.isdigit() for ch in line):
            r["kept"] = False
            r["drop_reason"] = "ref_fragment"
        elif _alpha_ratio(line) < 0.55:
            r["kept"] = False
            r["drop_reason"] = "low_alpha"
    return rows


def join_paragraphs(rows):
    """Join the kept lines into paragraphs.

    A dropped line closes the open paragraph. Inside a paragraph, a word
    broken with a hyphen is joined again. A paragraph with no final
    punctuation merges with the next one, because a page break cut it.
    The dropped line rows stay in the output, so the audit log keeps them.
    """
    dropped = []
    paras = []
    block = None
    for r in rows:
        if not r["kept"]:
            dropped.append(r)
            block = None
            continue
        line = r["text"].strip()
        if block is None:
            block = {"doc_id": r["doc_id"], "page": r["page"], "section": r["section"],
                     "text": line, "kept": True, "drop_reason": "", "flag": ""}
            paras.append(block)
        elif block["text"].endswith("-") and line[:1].islower():
            block["text"] = block["text"][:-1] + line
        else:
            block["text"] = block["text"] + " " + line

    # Merge a paragraph that a page break cut in the middle of a sentence.
    merged = []
    for p in paras:
        p["text"] = re.sub(r"\s+", " ", p["text"]).strip()
        # Repair a word that a line break cut, like "inte- grative".
        p["text"] = re.sub(r"(\w)- ([a-z])", r"\1\2", p["text"])
        if merged and not RE_TERMINAL.search(merged[-1]["text"]) and p["text"][:1].islower():
            merged[-1]["text"] = merged[-1]["text"] + " " + p["text"]
        else:
            merged.append(p)
    return merged + dropped


def split_sentences(rows):
    """Split each paragraph into sentences and give each one an id."""
    out = []
    for i, p in enumerate(rows):
        if not p["kept"]:
            out.append(p)
            continue
        for j, sent in enumerate(SPLITTER.tokenize(p["text"])):
            sent = sent.strip()
            out.append({"doc_id": p["doc_id"], "page": p["page"], "section": p["section"],
                        "sent_id": f"p{i:04d}s{j:03d}", "raw": sent, "text": sent,
                        "kept": True, "drop_reason": "", "flag": ""})
    return out


def _strip_noise(text, is_noise):
    """Remove the (...) and [...] groups for which is_noise says True."""
    def keep_or_cut(match):
        if is_noise(match.group(1)):
            return ""
        return match.group(0)
    text = RE_PAREN.sub(keep_or_cut, text)
    text = RE_BRACK.sub(keep_or_cut, text)
    return _tidy(text)


def strip_citations(rows):
    """Remove parenthetical citations, like (Ryan & Deci, 2017)."""
    for r in rows:
        if r["kept"]:
            r["text"] = _strip_noise(r["text"], _is_citation)
    return rows


def strip_stats(rows):
    """Remove parenthetical statistics, like (p < .05, n = 120)."""
    for r in rows:
        if r["kept"]:
            r["text"] = _strip_noise(r["text"], _is_stat)
    return rows


def drop_junk_sentences(rows):
    """Drop structural junk sentences. Flag the ambiguous ones and keep them."""
    for r in rows:
        if not r["kept"]:
            continue
        text = r["text"]
        words = text.split()
        if RE_LABEL.match(text):
            r["kept"] = False
            r["drop_reason"] = "caption_or_keywords"
        elif RE_SEEALSO.match(text) or len(RE_PAGERANGE.findall(text)) >= 3:
            r["kept"] = False
            r["drop_reason"] = "index_entry"
        elif _spaced_letter_ratio(words) > MAX_SPACED:
            r["kept"] = False
            r["drop_reason"] = "spaced_letters"
        elif not any(c.islower() for c in text):
            r["kept"] = False
            r["drop_reason"] = "no_lowercase"
        elif _alpha_ratio(text) < MIN_ALPHA:
            r["kept"] = False
            r["drop_reason"] = "low_alpha"
        elif sum(c.isdigit() for c in text) / max(len(text), 1) > MAX_DIGIT:
            r["kept"] = False
            r["drop_reason"] = "digit_heavy"
        elif not RE_TERMINAL.search(text.strip()):
            r["flag"] = "fragment"
        elif len(words) > LONG_FLAG:
            r["flag"] = "long"
    return rows


def filter_length(rows, min_words=4, max_words=80):
    """Drop sentences that are too short or too long."""
    for r in rows:
        if not r["kept"]:
            continue
        n = len(r["text"].split())
        if n < min_words:
            r["kept"] = False
            r["drop_reason"] = "too_short"
        elif n > max_words:
            r["kept"] = False
            r["drop_reason"] = "too_long"
    return rows


# The registry. The steps run in this order by default.
STEPS = {
    "fix_unicode": fix_unicode,
    "strip_markdown": strip_markdown,
    "drop_running_heads": drop_running_heads,
    "drop_junk_lines": drop_junk_lines,
    "join_paragraphs": join_paragraphs,
    "split_sentences": split_sentences,
    "strip_citations": strip_citations,
    "strip_stats": strip_stats,
    "drop_junk_sentences": drop_junk_sentences,
    "filter_length": filter_length,
}

DEFAULT_STEPS = list(STEPS.keys())


# ---------------------------------------------------------------------------
# The public function.
# ---------------------------------------------------------------------------

def _doc_id(path):
    """Return the file name without its folder and its extension.

    Example:
        >>> _doc_id("sample_files/smith_2021_trust.pdf")
        'smith_2021_trust'
    """
    name = os.path.basename(path)
    return os.path.splitext(name)[0]


def _file_row(path, reason, message):
    """Return one drop-log row for a whole file that the run skipped.

    The row has page 0, because the reason applies to all pages.

    Example:
        >>> _file_row("papers/notes.txt", "not_pdf", "the file name does not end with .pdf")
        {'doc_id': 'notes', 'page': 0, 'section': '', 'text': 'notes.txt: the file name does not end with .pdf', 'kept': False, 'drop_reason': 'not_pdf', 'flag': ''}
    """
    text = os.path.basename(path) + ": " + message
    return {"doc_id": _doc_id(path), "page": 0, "section": "", "text": text,
            "kept": False, "drop_reason": reason, "flag": ""}


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


def _select_pages(page_md, pages=None, skip_pages=None):
    """Return the sorted page numbers to use.

    Args:
        page_md: The dict {page number: markdown} of one PDF.
        pages: Pages to keep, as in harvest(). None keeps all pages.
        skip_pages: Pages to drop, as in harvest(). Applied after `pages`.

    Returns:
        A sorted list of page numbers.

    Example:
        >>> _select_pages({1: "a", 2: "b", 3: "c", 4: "d"}, pages="2-4", skip_pages=3)
        [2, 4]
    """
    if pages is None:
        wanted = set(page_md)
    else:
        wanted = _page_list(pages)
    if skip_pages is None:
        unwanted = set()
    else:
        unwanted = _page_list(skip_pages)
    return [p for p in sorted(page_md) if p in wanted and p not in unwanted]


def _page_rows(doc_id, page_md, selected):
    """Make one row per line of text, with its page number.

    A page with no text gets one dropped row with the reason "empty_page".

    Example:
        >>> rows = _page_rows("demo", {1: "First line\\nSecond line", 2: ""}, [1, 2])
        >>> [(r["page"], r["text"], r["drop_reason"]) for r in rows]
        [(1, 'First line', ''), (1, 'Second line', ''), (2, '', 'empty_page')]
    """
    rows = []
    for page in selected:
        if not page_md[page].strip():
            rows.append({"doc_id": doc_id, "page": page, "section": "", "text": "",
                         "kept": False, "drop_reason": "empty_page", "flag": ""})
            continue
        # Keep split("\n"). A page ends with "\n", so each page ends with one
        # blank row. That blank row closes the paragraph at the page break.
        for line in page_md[page].split("\n"):
            rows.append({"doc_id": doc_id, "page": page, "section": "",
                         "text": line, "kept": True, "drop_reason": "", "flag": ""})
    return rows


def _run_steps(rows, steps, min_words, max_words):
    """Run the preprocessing steps on the rows, first to last.

    A step is a name from STEPS or your own function. The step
    "filter_length" gets min_words and max_words.

    Example:
        >>> rows = [{"text": "Too short.", "kept": True, "drop_reason": ""}]
        >>> _run_steps(rows, ["filter_length"], 4, 80)[0]["drop_reason"]
        'too_short'
    """
    for step in steps:
        if step == "filter_length":
            rows = filter_length(rows, min_words, max_words)
        elif isinstance(step, str):
            rows = STEPS[step](rows)
        else:
            rows = step(rows)
    return rows


def _harvest_one(pdf_path, doc_number, settings):
    """Read and clean one PDF. Return all its rows, kept and dropped.

    The steps run on one document at a time. Two papers never share a
    paragraph, a section name or a running head.
    Each sent_id gets the document number in front: "d000p0012s003" is
    document 0, paragraph 12, sentence 3. So a sent_id is unique in a folder.

    Args:
        pdf_path: Path of the PDF file.
        doc_number: The position of the PDF in the run, from 0.
        settings: A dict with the harvest() arguments pages, skip_pages,
            steps, min_words, max_words and cache.

    Returns:
        A list of row dicts. The rows with a "sent_id" are sentences.

    Raises:
        ValueError: _read_pages() cannot read the PDF.
    """
    doc_id = _doc_id(pdf_path)
    page_md = _read_pages(pdf_path, settings["cache"])
    selected = _select_pages(page_md, settings["pages"], settings["skip_pages"])
    rows = _page_rows(doc_id, page_md, selected)
    rows = _run_steps(rows, settings["steps"], settings["min_words"], settings["max_words"])

    prefix = f"d{doc_number:03d}"
    for row in rows:
        if "sent_id" in row:
            row["sent_id"] = prefix + row["sent_id"]
    return rows


def _harvest_folder(folder, settings):
    """Read and clean every PDF in a folder. Skip a bad file and log it.

    A file that is not a PDF gets a "not_pdf" row. A PDF that cannot be
    read gets an "unreadable_pdf" row with the error message. The run
    then goes on with the next file.

    Args:
        folder: Path of the folder.
        settings: The harvest() settings, as in _harvest_one().

    Returns:
        A list of row dicts from all files. The skipped-file rows come first.

    Raises:
        ValueError: The folder has no PDF file.
    """
    pdf_paths, other_paths = _list_pdfs(folder)
    if not pdf_paths:
        other_names = [os.path.basename(p) for p in other_paths]
        raise ValueError(f"no PDF file in the folder {folder!r}; files found: {other_names}")

    file_rows = []
    for path in other_paths:
        file_rows.append(_file_row(path, "not_pdf", "the file name does not end with .pdf"))

    rows = []
    doc_number = 0
    for i, path in enumerate(pdf_paths):
        print(f"\r  reading PDF {i + 1} of {len(pdf_paths)}", end="")
        try:
            doc_rows = _harvest_one(path, doc_number, settings)
        except ValueError as error:
            file_rows.append(_file_row(path, "unreadable_pdf", str(error)))
            continue
        rows.extend(doc_rows)
        doc_number = doc_number + 1
    print()
    return file_rows + rows


def _print_summary(source, kept, dropped):
    """Print one short summary of a harvest() run."""
    doc_counts = collections.Counter(r["doc_id"] for r in kept)
    skipped = [r for r in dropped if r["page"] == 0]
    reasons = collections.Counter(r["drop_reason"] for r in dropped)

    print(f"harvest: {source}")
    print(f"  documents read: {len(doc_counts)} | files skipped: {len(skipped)}")
    print(f"  sentences kept: {len(kept):,} | dropped rows: {len(dropped):,}")
    for reason, n in reasons.most_common():
        print(f"  {n:>8,}  {reason}")
    if len(doc_counts) > 1:
        print("  sentences per document:")
        for doc_id, n in sorted(doc_counts.items()):
            print(f"  {n:>8,}  {doc_id}")
    for row in skipped:
        print(f"  skipped: {row['text']}")


def harvest(source, pages=None, skip_pages=None, steps=None,
            min_words=4, max_words=80, cache=True):
    """Read one PDF, or every PDF in a folder, and return clean sentences with a drop log.

    For one PDF, a bad file raises a ValueError. For a folder, a bad file
    does not stop the run. The drop log gets one row for the file, with
    page 0 and the reason "not_pdf" or "unreadable_pdf".
    The function looks in the folder only, not in its subfolders.

    Args:
        source: Path of a PDF file, or of a folder with PDF files.
        pages: Pages to keep. Give "12-540", [3, 5, 9], or None for all pages.
            Page numbers are 1-indexed, as in a PDF viewer.
            For a folder, the same pages apply to every PDF.
        skip_pages: Pages to drop, in the same forms. Applied after `pages`.
        steps: The preprocessing steps, in order. None uses DEFAULT_STEPS.
            Give step names from STEPS, or your own function. A custom
            function takes a list of row dicts and returns a list of row dicts.
        min_words: Drop sentences with fewer words.
        max_words: Drop sentences with more words.
        cache: Keep the extracted page markdown on disk, in <pdf>.pages.json
            beside each PDF. The next run then skips the slow extraction.
            This file is the only file that the function writes.

    Returns:
        A dict with two lists:
        - "sentences": kept rows with doc_id, page, sent_id, section,
          raw, clean, flag.
        - "dropped": dropped rows with doc_id, page, section,
          drop_reason, text.

    Raises:
        ValueError: The source does not exist, the folder has no PDF,
            or the one PDF cannot be read.

    Example:
        >>> data = harvest("sample_files")          # doctest: +SKIP
        >>> data["sentences"][0]["sent_id"]          # doctest: +SKIP
        'd000p0000s000'
    """
    if steps is None:
        steps = DEFAULT_STEPS
    settings = {"pages": pages, "skip_pages": skip_pages, "steps": steps,
                "min_words": min_words, "max_words": max_words, "cache": cache}

    # 1. Read the PDF, or each PDF in the folder.
    # A page cache can stand in for its PDF, so a test can use made-up pages.
    if os.path.isdir(source):
        rows = _harvest_folder(source, settings)
    elif os.path.isfile(source) or os.path.isfile(source + ".pages.json"):
        rows = _harvest_one(source, 0, settings)
    else:
        raise ValueError(f"no file or folder at {source!r}; give a PDF file or a folder of PDF files")

    # 2. Split the result into kept sentences and the drop log.
    # A blank line is not content, so it stays out of the log.
    kept = [r for r in rows if r["kept"] and "sent_id" in r]
    dropped = [r for r in rows if not r["kept"] and r["drop_reason"] != "blank"]
    _print_summary(source, kept, dropped)

    # 3. Return the data. The caller writes files when it wants them.
    sentences = [{"doc_id": r["doc_id"], "page": r["page"], "sent_id": r["sent_id"],
                  "section": r["section"], "raw": r["raw"], "clean": r["text"],
                  "flag": r["flag"]} for r in kept]
    drop_log = [{"doc_id": r["doc_id"], "page": r["page"], "section": r["section"],
                 "drop_reason": r["drop_reason"], "text": r["text"]} for r in dropped]
    return {"sentences": sentences, "dropped": drop_log}
