# Download papers

`download_papers()` takes a list of DOIs. For each DOI, it looks for a free, legal copy of the
paper. When it finds one, it saves the PDF into a folder. It returns one row for each DOI that
tells what happened.

The usual input is the result of `extract_references()`. That function reads your papers and lists
the DOIs in their reference lists. So the two functions together get the papers that your papers
cite. See [DOIs and references](dois.md) and [A snowball round](snowball.md).

## An example

```python
from theoryminer import extract_references, download_papers

# Read the PDFs in the folder "seed_papers". Get the DOIs of the papers that they cite.
refs = extract_references("seed_papers")

# Download those papers into the folder "round_2".
report = download_papers(
    refs,                          # the DOIs to download
    "round_2",                     # the folder for the PDFs; the function makes it
    licences=["cc-by"],            # download only the papers with a CC BY licence
    email="you@your-uni.edu",      # your address; some services answer faster with it
)
```

`"seed_papers"` and `"round_2"` are folder names. Use the names that you want.
`"round_2"` is a name for the second round of a snowball search: the seed papers are round 1.

## The arguments

| Argument | What you give | Default |
|---|---|---|
| `dois` | The DOIs. Give the result of `extract_references()`, a list of DOI strings such as `["10.3389/fpsyg.2021.728657"]`, or the path of a CSV file with a `doi` column. | none; you must give it |
| `output_dir` | The folder for the PDFs. The function makes the folder when it does not exist. | none; you must give it |
| `licences` | A list of licences. The function downloads only the papers with one of these licences. Examples: `["cc-by"]`, `["cc-by", "cc-by-sa"]`. | `None`: every free paper, whatever its licence |
| `email` | Your email address. OpenAlex and Crossref answer faster with it. Unpaywall needs it. Give a real address. | `None`: the function skips Unpaywall |
| `sources` | The services to try, in order. See the table below. | `None`: all 9 services in the table below |
| `respect_robots` | `True` obeys the `robots.txt` file of each website. Set `False` only when you have the right to download from the site. | `True` |
| `save` | A path for a CSV copy of the result, for example `"outputs/report.csv"`. | `None`: no CSV copy |

`core_api_key` and `serpapi_key` are keys for `tmsr-doi-downloader`, an extra source. Most users do
not need them. See the [reference page](../reference/download_papers.md).

A text in `dois` is always the path of a CSV file. To download one DOI, put it in a list:
`download_papers(["10.3389/fpsyg.2021.728657"], "round_2")`.

## The result

The function returns a list with one dict for each DOI:

| Key | Meaning |
|---|---|
| `doi` | the DOI, in lowercase |
| `status` | `"downloaded"`, `"already_there"` (the PDF was in the folder before), `"skipped_licence"` (the licence is not in `licences`), `"not_found"` or `"error"` |
| `source` | the service that gave the PDF |
| `licence` | the licence of the paper, from OpenAlex. `"none"` means no free copy. `"unknown"` means that OpenAlex does not know the DOI. |
| `file` | the file name of the PDF in `output_dir` |
| `note` | for a DOI without a PDF, the reason from each service |

To see the result as a table, use pandas:

```python
import pandas as pd

table = pd.DataFrame(report)
print(table["status"].value_counts())
```

## The files in the folder

After the run, `output_dir` holds:

- one PDF for each downloaded paper. The file name is the DOI, with `_` in place of each `.` and
  `/`. For example, the DOI `10.3389/fpsyg.2021.728657` gives `10_3389_fpsyg_2021_728657.pdf`;
- `downloads.csv`, the log of the downloads. `harvest()` reads this file to find the DOI of each
  PDF.

You can stop the function and start it again. It does not download a PDF again when the PDF is
already in the folder.

## The services

The function asks OpenAlex for the licence of each paper first. Then it tries the services in
this order. It stops at the first service that gives a real PDF.

| Name in `sources` | Service |
|---|---|
| `"openalex"` | the free copies that OpenAlex lists |
| `"publisher"` | the PDF link of the publisher, for Springer, BMC, Palgrave and Frontiers |
| `"pmc"` | PubMed Central |
| `"europe_pmc"` | Europe PMC |
| `"unpaywall"` | Unpaywall. It needs `email`. |
| `"semantic_scholar"` | Semantic Scholar |
| `"crossref"` | the PDF links that the publisher gives to Crossref |
| `"preprint"` | a preprint on OSF |
| `"landing_page"` | the web page of the DOI, and the PDF link on it |
| `"tmsr-doi-downloader"` | an extra source. It is not in the default list. It needs Python 3.11 or newer. |

To try only two services:

```python
report = download_papers(refs, "round_2", sources=["openalex", "pmc"])
```

The function waits 1 second between two requests to the same website.

## Papers that it cannot get

The function gets free, legal copies only. It does not log in to a publisher website. A paper
without a free copy gets the status `"not_found"`. Some publishers also block programs, for
example Wiley, Elsevier, SAGE, Taylor & Francis and MDPI. Then their free papers can also be
`"not_found"`.

To add such a paper, get the PDF through your library. Put it into the folder with the other PDFs.
`harvest()` reads it and finds its DOI in the PDF.

## The licence of a paper

A free copy is not always free to share. The `licence` column gives the licence of each paper.
Check it before you publish the text of a paper, for example in a notebook output. Use
`licences=["cc-by"]` when you want to share the text.
