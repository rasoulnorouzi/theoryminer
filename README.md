# theoryminer

[![Open the tutorial in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/rasoulnorouzi/theoryminer/blob/main/tutorials/TUTORIAL.ipynb)

Assemble theories from text. `theoryminer` reads a PDF, finds the sentences that make causal
claims, extracts each cause → effect pair, and brings the many ways authors name the same
construct together, with a thesaurus (ELSST) or without one.

```
PDF ──harvest()──► sentences ──causenet()──► relations (cause span → effect span)
                                                  │
              ┌───────────────────────────────────┼───────────────────────────┐
              ▼                                   ▼                           ▼
standardize_constructs()            pairwise_grouping() / clusterer()      (spans)
span → top-k thesaurus concepts     spans → groups of similar spans
                                                  │
                                  ┌───────────────┴───────────────┐
                                  ▼                               ▼
                        standardize_groups()               label_groups()
                        group → thesaurus concept          group → label from its own words
```

Status: extraction and harmonisation are written. The graph stage (`theorize()`) and the
evaluation are planned.

## Install

Install from GitHub with pip. You do not need to clone the repository:

```bash
pip install "theoryminer @ git+https://github.com/rasoulnorouzi/theoryminer.git"
pip install "theoryminer[umap] @ git+https://github.com/rasoulnorouzi/theoryminer.git"   # with UMAP
```

In a notebook, such as Google Colab, put `%pip install` at the start of the first cell.
The tutorial notebook does this for you: click the Colab badge above.

To change the code, clone the repository and install it in editable mode:

```bash
git clone https://github.com/rasoulnorouzi/theoryminer.git
cd theoryminer
pip install -e ".[notebooks,dev,umap]"
```

The first call to `causenet()` downloads the SocioCausaNet model
(`rasoultilburg/SocioCausaNet`) from the Hugging Face Hub. The first call to a harmonizer
function downloads the sentence-transformer (`all-mpnet-base-v2` by default).

## Quick start

```python
from theoryminer import harvest, causenet, clusterer, label_groups, standardize_constructs

data = harvest("raw_data/my_book.pdf", pages="12-540")   # clean sentences + a drop log
data = harvest("sample_files")                          # or every PDF in a folder
relations = causenet(data["sentences"])                 # one dict per cause → effect pair

groups = clusterer(relations)                           # group similar spans (HDBSCAN)
names = label_groups(groups)                            # name each group from its own words
matches = standardize_constructs(relations)             # or map each span to ELSST concepts
```

`harvest()` takes one PDF or a folder of PDFs. In a folder, a file that is not a PDF, or a PDF
that cannot be read, does not stop the run. The drop log gets one row for it, with the reason.

## Sample papers

`sample_files/` holds 7 open-access social-science papers with a CC BY licence.
`sample_files/SOURCES.md` gives the title, authors, DOI and licence of each one.
The tutorial and the tests use them.

## Data you supply

Give `harvest()` your own PDFs. In a clone, `raw_data/` is a good place for them: git ignores it.

The ELSST thesaurus (release 5) ships inside the package as `theoryminer/data/ELSST_R5.rdf.gz`.
`taxonomy="elsst"` needs no extra file. A full path to another SKOS `.rdf` or `.rdf.gz` file also
works as `taxonomy=`. The thesaurus vectors are computed once and cached in
`theoryminer/taxonomy_cache/`.
`label_groups()` needs no thesaurus at all.

## Documentation

| file | what it is |
|---|---|
All learning material is in `tutorials/`:

| file | what it is |
|---|---|
| `tutorials/TUTORIAL.ipynb` | every function and every setting, with real output, and a full run on the sample papers |
| `tutorials/PACKAGE_LINE_BY_LINE.ipynb` | each function taken apart line by line and checked against the real one |
| `tutorials/STRATEGIES.md` | the six ways to turn a thesaurus concept into text, and the test behind the defaults |

The notebooks work from `tutorials/` and from the repository root. The examples use the papers in
`sample_files/`.

## Tests

```bash
pip install -e ".[dev]"
pytest tests/
```

The tests check `harvest()` on the sample papers and on broken files. They load no model.

## Licence

The code has the MIT licence. See `LICENSE`.

Two kinds of data in this repository keep their own licence:

- `theoryminer/data/ELSST_R5.rdf.gz`: ELSST, © CESSDA, CC BY-SA 4.0. See `theoryminer/data/ELSST_LICENSE.md`.
- `sample_files/*.pdf`: open-access papers, CC BY 4.0. See `sample_files/SOURCES.md`.
