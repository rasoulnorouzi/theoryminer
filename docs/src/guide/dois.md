# DOIs and references

Two functions read DOIs from PDFs:

| Function | What it finds | Use it to |
|---|---|---|
| `extract_dois()` | the DOI and the title of each paper itself | label each paper on the map |
| `extract_references()` | the DOIs that each paper cites | find the papers for the next round of a snowball search |

## The DOI of each paper

You do not need `extract_dois()` for the map. `harvest()` already puts the DOI and the title on
each sentence (`find_dois=True`), and `causenet()` copies them to each relation.

Use `extract_dois()` when you want the list on its own:

```python
from theoryminer import extract_dois

rows = extract_dois("sample_files", save="outputs")      # writes outputs/dois.csv
```

Each row has `doc_id`, `file`, `doi`, `source`, `title`, `page`, `status` and `note`.

The DOI comes from the most certain source, in this order:

1. `downloads.csv`, the log that `download_papers()` writes into the folder.
2. The file name of a PDF that `download_papers()` saved, because it is made from the DOI.
3. The subject or keywords field of the PDF metadata.
4. The first DOI on page 1, else on page 2. Page 1 is sometimes a cover page.

The `source` column tells which rule gave the DOI. On 21 papers with a known DOI, this order found 20.

The title is the largest text on page 1 that has at least 4 words. A shorter large text is
usually a journal name, such as "PLOS ONE". When no text passes, the title comes from the PDF
metadata.

## The DOIs in the references

```python
from theoryminer import extract_references

refs = extract_references("sample_files", save="outputs")   # writes outputs/references.csv
```

Each row has `doi`, `n_seeds` (how many of your papers cite it) and `cited_by` (which papers).
The most cited DOIs come first.

The function repairs a DOI that the PDF cut at a line end, for example
`10.1007/s1096 4-015-0354-5`. It leaves out the DOI of the paper itself and the DOIs of its parts
(figures, tables). On the 7 sample papers it found 215 DOIs, and 214 of them exist at doi.org.

A reference that prints no DOI cannot be found. The journal of one sample paper prints no DOIs in
its references, so that paper gives 0 DOIs.

Give the result to [`download_papers()`](download.md) to get the PDFs.
