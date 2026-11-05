# DOIs and references

Two functions read DOIs from your PDFs:

| Function | What it finds | Why you use it |
|---|---|---|
| `extract_dois()` | the DOI and the title of each paper | to get a list of your papers |
| `extract_references()` | the DOIs in the reference list of each paper | to find the papers that your papers cite, and download them |

You do not need `extract_dois()` to make a causal map. `harvest()` finds the DOI and the title of
each paper itself, and the map shows them.

## `extract_dois()`: the DOI of each paper

```python
from theoryminer import extract_dois

rows = extract_dois(
    "sample_files",          # a PDF file, or a folder of PDF files
    save="outputs",          # also write the rows to outputs/dois.csv
)
```

### The arguments

| Argument | What you give | Default |
|---|---|---|
| `source` | The path of one PDF file, or of a folder. The function reads the PDFs in the folder, not in its subfolders. | none; you must give it |
| `save` | A folder (the function writes `dois.csv` in it), or a path that ends with `.csv`. | `None`: no file |
| `first_pages` | The function looks for the DOI on pages 1 to `first_pages`. | `2` |
| `cache` | `True` keeps the text of each PDF in a file beside the PDF, so the next run is faster. | `True` |

### The result

A list with one dict for each PDF:

| Key | Meaning |
|---|---|
| `doc_id` | the file name without `.pdf` |
| `file` | the file name |
| `doi` | the DOI in lowercase, or `""` when the function finds none |
| `source` | where the DOI came from (see below) |
| `title` | the title of the paper, or `""` |
| `page` | the page with the DOI, or `0` |
| `status` | `"found"`, `"not_found"`, `"not_pdf"` or `"unreadable_pdf"` |
| `note` | why a file has no DOI |

### Where the DOI comes from

The function uses the first of these sources that gives a DOI:

1. `"download_log"`: the file `downloads.csv` that `download_papers()` writes into the folder.
2. `"file_name"`: the file name, when `download_papers()` saved the file.
3. `"metadata"`: the metadata of the PDF.
4. `"text"`: the first DOI on page 1, then on page 2. Page 1 is sometimes a cover page.

## `extract_references()`: the DOIs that your papers cite

```python
from theoryminer import extract_references

refs = extract_references(
    "sample_files",          # your papers: one PDF file, or a folder of PDF files
    save="outputs",          # also write the rows to outputs/references.csv
)
```

### The arguments

| Argument | What you give | Default |
|---|---|---|
| `source` | The path of one PDF file, or of a folder. The function reads the PDFs in the folder, not in its subfolders. | none; you must give it |
| `save` | A folder (the function writes `references.csv` in it), or a path that ends with `.csv`. | `None`: no file |
| `cache` | `True` keeps the text of each PDF in a file beside the PDF, so the next run is faster. | `True` |

### The result

A list with one dict for each cited DOI. The DOI that most of your papers cite comes first.

| Key | Meaning |
|---|---|
| `doi` | the cited DOI, in lowercase |
| `n_seeds` | how many of your papers cite it |
| `cited_by` | a list with the `doc_id` of each paper that cites it. In the CSV file, the list is one text, joined by ` \| `. |

The function finds only the references that print a DOI. Some journals print no DOIs in their
reference lists. A paper from such a journal gives no DOIs.

Give the result to [`download_papers()`](download.md) to download the cited papers.
