# Read PDFs

`harvest()` reads your PDF files and splits their text into sentences. It removes the text that is
not research text: headings, table rows, page numbers and the reference lists. The sentences go to
`causenet()`, the next step.

## An example

```python
from theoryminer import harvest

data = harvest(
    "sample_files",          # a PDF file, or a folder of PDF files
)

sentences = data["sentences"]    # the sentences that the function keeps
dropped = data["dropped"]        # the lines that it removes, each with the reason
```

To read only some pages of one long PDF, such as a book:

```python
data = harvest("book.pdf", pages="12-540")
```

## The arguments

| Argument | What you give | Default |
|---|---|---|
| `source` | The path of one PDF file, or of a folder. The function reads the PDFs in the folder, not in its subfolders. | none; you must give it |
| `pages` | The pages to read. Page 1 is the first page, as in a PDF viewer. Examples: `12`, `"12-540"`, `"3,7,9-12"`, `[3, 5, 9]`. For a folder, the same pages apply to each PDF. | `None`: all pages |
| `skip_pages` | The pages to leave out, in the same form as `pages`. | `None`: no page |
| `min_words` | A sentence with fewer words is removed. | `4` |
| `max_words` | A sentence with more words is removed. | `80` |
| `steps` | The list of cleaning steps. See [The cleaning steps](#the-cleaning-steps). | `None`: all 10 steps |
| `cache` | `True` writes the text of each PDF to a file `<name>.pdf.pages.json` beside the PDF. The next run reads this file and is much faster. `False` writes no file. | `True` |
| `find_dois` | `True` finds the DOI and the title of each paper. The causal map shows them. | `True` |

## The result

A dict with two lists.

`data["sentences"]` has one dict for each sentence:

| Key | Meaning |
|---|---|
| `doc_id` | the file name without `.pdf` |
| `page` | the page number |
| `sent_id` | a unique id. `d000p0012s003` means document 0, paragraph 12, sentence 3. |
| `section` | the last heading before the sentence |
| `raw` | the sentence with its citations and statistics |
| `clean` | the sentence without citations such as "(Ryan & Deci, 2000)" and statistics such as "(p < .05)". `causenet()` reads this text. |
| `flag` | `""`, or a word that marks a doubtful sentence. See [Flags](#flags). |
| `doi` | the DOI of the paper, or `""` |
| `title` | the title of the paper, or `""` |

`data["dropped"]` has one dict for each removed line or sentence, with the keys `doc_id`,
`page`, `section`, `text` and `drop_reason`. Use it to check what the function removed.

To see the results as tables, use pandas:

```python
import pandas as pd

sentences = pd.DataFrame(data["sentences"])
dropped = pd.DataFrame(data["dropped"])
print(dropped["drop_reason"].value_counts())
```

## Why a line is removed

The `drop_reason` of a removed line is one of these:

| `drop_reason` | The line is |
|---|---|
| `running_head` | a short line that repeats on 3 or more pages, such as the journal name at the top of each page |
| `reference_section` | in the references, the bibliography, the notes or the acknowledgements |
| `heading` | a heading. Its text becomes the `section` of the sentences after it. |
| `table_row` | a row of a table |
| `page_number` | a page number |
| `chapter_marker` | only the word "CHAPTER" or "PART" |
| `front_back_matter` | only the word "Index", "Contents" or "Appendix" |
| `doi_url` | a line that starts with a DOI or a web address |
| `ref_fragment` | a piece of a reference: one word with a digit |
| `low_alpha` | a text with too few letters |
| `licence_text` | the licence or copyright text of the journal |
| `caption_or_keywords` | a caption such as "Figure 1", or a line that starts with "Keywords:", "Source:", "Note:" or "Abstract:" |
| `index_entry` | an entry of a book index |
| `spaced_letters` | text with spaces between the letters, such as "R e s u l t s" |
| `no_lowercase` | a sentence with no lowercase letter |
| `digit_heavy` | a sentence with too many digits |
| `too_short` | a sentence with fewer than `min_words` words |
| `too_long` | a sentence with more than `max_words` words |
| `empty_page` | a page with no text |
| `not_pdf`, `unreadable_pdf` | a file in the folder that is not a PDF, or that the function cannot read |

A file that the function cannot read does not stop the run. It gets one row in `data["dropped"]`.

## Flags

A flag marks a sentence that can be wrong. The function keeps the sentence.

| `flag` | Meaning |
|---|---|
| `front_matter` | the sentence holds text from the side of the journal page, such as an editor name, a date or an email address |
| `fragment` | the sentence has no full stop at the end |
| `long` | the sentence has more than 80 words. You see this flag only when you set `max_words` above 80. |

To send only the sentences without a flag to `causenet()`:

```python
sentences = [row for row in data["sentences"] if row["flag"] == ""]
```

## The cleaning steps

The function runs these 10 steps in this order:

| Step | What it does |
|---|---|
| `fix_unicode` | replaces curly quotes, long dashes and special spaces, and removes invisible characters |
| `strip_markdown` | removes the link and emphasis marks that the text extraction adds |
| `drop_running_heads` | removes the short lines that repeat on 3 or more pages |
| `drop_junk_lines` | removes headings, table rows, page numbers and the reference list |
| `join_paragraphs` | joins the lines of each paragraph, and joins the words that a hyphen cuts at a line end |
| `split_sentences` | splits each paragraph into sentences |
| `strip_citations` | removes citations from `clean` |
| `strip_stats` | removes statistics from `clean` |
| `drop_junk_sentences` | removes the sentences that are not research text |
| `filter_length` | removes the sentences with fewer than `min_words` or more than `max_words` words |

To switch off one step, give the list without that step:

```python
from theoryminer import DEFAULT_STEPS

steps = [step for step in DEFAULT_STEPS if step != "strip_stats"]
data = harvest("sample_files", steps=steps)
```
