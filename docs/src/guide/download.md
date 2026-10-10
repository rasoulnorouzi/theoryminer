# Download papers

`download_papers()` downloads the PDFs of a list of DOIs into a folder. It gives one status row
for each DOI.

```python
from theoryminer import extract_references, download_papers

refs = extract_references("seed_papers")
report = download_papers(refs, "round_2", email="you@your-uni.edu")
```

`dois` can be the output of `extract_references()`, a list of DOI strings, or the path of a CSV
file with a `doi` column.

## How it finds a PDF

The function asks OpenAlex for the licence of each paper first. With `licences=["cc-by"]` it
downloads only the CC BY papers, and it never contacts the other papers' sites.

Then it tries the sources in turn and stops at the first real PDF:

| Source | What it does |
|---|---|
| `openalex` | the PDF links and the repository pages of the open-access copies in OpenAlex |
| `publisher` | the direct PDF link of the publisher, from a plugin for that publisher |
| `pmc` | the PDF in the open-access data of PubMed Central |
| `europe_pmc` | the free PDF links that Europe PMC lists |
| `unpaywall` | the PDF links of Unpaywall; it needs `email` |
| `semantic_scholar` | the open-access PDF link of Semantic Scholar |
| `crossref` | the PDF links that the publisher gives to Crossref |
| `preprint` | the open OSF preprint of the paper, when Crossref links one |
| `landing_page` | the page that doi.org opens, and the PDF link on it |

A link can give the PDF or a web page. For a page, the function follows its `citation_pdf_url`
tag, the tag that publishers write for Google Scholar. The function keeps a file only when it
is a real PDF. It waits 1 second between two requests to the same site, and it obeys `robots.txt`.

Give `email` when you can. OpenAlex and Crossref answer faster with it, and Unpaywall needs it.

## The publisher plugins

A plugin knows how one publisher builds its PDF links, in the same way as a Zotero translator.
It turns a DOI into the direct link. The package has plugins for Springer (also BMC and Palgrave)
and Frontiers. Each plugin is a few lines in `theoryminer/download/publishers.py`.

A plugin is useful only when the publisher gives the PDF to a plain request. Wiley, Taylor &
Francis, SAGE, MDPI, Annual Reviews and Emerald give their PDFs only to a browser that passes a
bot check, so they have no plugin. Their open papers often come through the other sources, as a
copy in a repository or in PubMed Central.

## The result

| Key | Meaning |
|---|---|
| `doi` | the DOI, in lowercase |
| `status` | `downloaded`, `already_there`, `skipped_licence`, `not_found` or `error` |
| `source` | the source that gave the PDF |
| `licence` | the OpenAlex licence, `none` or `unknown` |
| `file` | the file name of the PDF, made from the DOI |
| `note` | for a missed DOI, the reason from each source |

The function also writes `downloads.csv` into the folder. `harvest()` reads that file to know the
DOI of each PDF. A PDF that is already in the folder is not downloaded again, so you can run the
function again after a stop.

## What to expect

We tested the sources on 300 DOIs: 100 references of the sample papers and 200 random articles in
psychology and the social sciences.

| | Result |
|---|---|
| Open-access papers downloaded | 101 of 164 (62 %) |
| Closed papers downloaded | 4 of 135 (3 %) |
| On the 100 references, against version 0.2 | 33 correct PDFs, against 25 |

A closed paper has no legal free copy, so no open source can give it. Many publishers (Wiley,
Elsevier, SAGE, Taylor & Francis, MDPI) also block programs, even for their open papers. These
two cases are most of the misses. The `note` column tells you the reason for each DOI.

The benchmark is in `benchmarks/downloader/`. Run it again with
`python benchmarks/downloader/run_benchmark.py --label my_run --email you@your-uni.edu`.

## What the downloader does not do

The downloader gets open-access copies only. It does not log in to a publisher site, and it does
not use a browser. A paper that is only behind a paywall stays `not_found`. Get such a paper
through your library, and put the PDF into the folder with the others. `harvest()` reads it, and
it finds the DOI in the PDF metadata or on the first two pages.

## tmsr-doi-downloader

Versions 0.2.x used the package `tmsr-doi-downloader`. Since 0.3.0 the default sources replace
it: on the 100 references it added one paper and doubled the run time. It is still available as
an extra source: `sources=SOURCES + ["tmsr-doi-downloader"]`.
