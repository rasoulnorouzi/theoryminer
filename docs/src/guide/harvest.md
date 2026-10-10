# Read PDFs

`harvest()` reads one PDF, or every PDF in a folder, and returns clean sentences and a drop log.

```python
from theoryminer import harvest

data = harvest("sample_files")                       # every PDF in the folder
data = harvest("book.pdf", pages="12-540")           # one PDF, some pages only
```

The result has two lists:

| Key | What it holds |
|---|---|
| `data["sentences"]` | one dict per kept sentence |
| `data["dropped"]` | one dict per dropped row, with its `drop_reason` |

## What a sentence holds

| Key | Meaning |
|---|---|
| `doc_id` | the file name without `.pdf` |
| `page` | the page number, as in a PDF viewer |
| `sent_id` | a unique id, for example `d000p0012s003`: document 0, paragraph 12, sentence 3 |
| `section` | the last heading before the sentence |
| `raw` | the sentence as the sentence splitter gave it |
| `clean` | the sentence after the later steps; `causenet()` reads this text |
| `flag` | `""`, or a flag for a doubtful sentence (see below) |
| `doi`, `title` | the DOI and the title of the paper, or `""` |

## The cleaning steps

The steps run in this order. You can change the list with `steps=`.

| Step | What it does |
|---|---|
| `fix_unicode` | replaces curly quotes, long dashes, odd spaces, and removes invisible marks |
| `strip_markdown` | removes Markdown links and emphasis that the PDF extractor adds |
| `drop_running_heads` | drops short lines that repeat 3 or more times, such as a chapter header |
| `drop_junk_lines` | drops structural lines: headings, table rows, page numbers, the reference section |
| `join_paragraphs` | joins the lines of a paragraph, and a word that a hyphen cut. It joins a paragraph that a page break cut when the first part has no final punctuation and the next part starts in lowercase. |
| `split_sentences` | splits the paragraphs into sentences |
| `strip_citations` | removes citations such as "(Ryan & Deci, 2000)" from `clean` |
| `strip_stats` | removes statistics such as "(p < .05)" from `clean` |
| `drop_junk_sentences` | drops sentences that are not research text |
| `filter_length` | drops sentences that are too short or too long |

To switch off one step, give the list without it:

```python
from theoryminer import DEFAULT_STEPS

steps = [step for step in DEFAULT_STEPS if step != "strip_stats"]
data = harvest("sample_files", steps=steps)
```

You can also add a function of your own. It takes the list of row dicts and returns it. The
tutorial notebook, section 1.3b, shows how.

## Why a row is dropped

`harvest()` never deletes a row. A step marks it as dropped and writes the reason.

| Reason | The row is |
|---|---|
| `running_head` | a line of 90 characters or fewer that repeats 3 or more times |
| `reference_section` | a line inside a references, bibliography, notes or acknowledgements section |
| `heading` | a heading; its text becomes the `section` of the next sentences |
| `table_row` | a row of a table |
| `page_number` | a line that holds only a page number |
| `chapter_marker` | a line that holds only "CHAPTER" or "PART" |
| `front_back_matter` | a line that holds only "Index", "Contents" or "Appendix" |
| `doi_url` | a line that starts with a DOI or a web address |
| `ref_fragment` | one word with a digit and no space, a piece of a reference |
| `low_alpha` | a line or a sentence with too few letters |
| `licence_text` | the licence or copyright text of a journal |
| `caption_or_keywords` | a text that starts with "Keywords:", "Source:", "Note:" or "Abstract:", or a caption such as "Figure 1" or "Table 2" |
| `index_entry` | an entry of a book index |
| `spaced_letters` | text with spaces between its letters, such as "R e s u l t s" |
| `no_lowercase` | a sentence without a lowercase letter |
| `digit_heavy` | a sentence with too many digits |
| `too_short` | a sentence with fewer than `min_words` words (default 4) |
| `too_long` | a sentence with more than `max_words` words (default 80) |
| `empty_page` | a page without text |
| `not_pdf`, `unreadable_pdf` | a file in the folder that is not a PDF, or that cannot be read |

## Flags

A flag marks a doubtful sentence. The sentence stays in `data["sentences"]`.

| Flag | Meaning |
|---|---|
| `front_matter` | the PDF extractor mixed journal sidebar text into the sentence: an editor name, a date, an e-mail address |
| `fragment` | the sentence has no final punctuation |
| `long` | the sentence has more than 80 words. With the default `max_words=80`, these sentences are dropped as `too_long`, so the flag shows only when you raise `max_words`. |

To keep the flagged sentences away from the model:

```python
sentences = [s for s in data["sentences"] if not s["flag"]]
```

## Pages

Page 1 is the first page, as in a PDF viewer.

```python
harvest("book.pdf", pages=12)               # one page
harvest("book.pdf", pages="12-540")         # a range
harvest("book.pdf", pages="3,7,9-12")       # a list of pages and ranges
harvest("book.pdf", skip_pages=[4, 5])      # every page except 4 and 5
```

For a folder, the same pages apply to every PDF.

## The page cache

Text extraction is the slow part. `harvest()` writes the text of each PDF to `<pdf>.pages.json`
beside the PDF. The next run reads that file. Use `cache=False` to read every PDF again and write
no file.

## A bad file

For one PDF, a missing or broken file raises a `ValueError`. For a folder, a bad file does not stop
the run. The drop log gets one row for the file, with page 0 and the reason `not_pdf` or
`unreadable_pdf`. `harvest()` reads the folder only, not its subfolders.

See the full list of settings in the [reference of `harvest()`](../reference/harvest.md).
