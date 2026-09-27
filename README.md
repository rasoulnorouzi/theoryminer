# theoryminer

[![PyPI](https://img.shields.io/pypi/v/theoryminer)](https://pypi.org/project/theoryminer/)
[![CI](https://github.com/rasoulnorouzi/theoryminer/actions/workflows/ci.yml/badge.svg)](https://github.com/rasoulnorouzi/theoryminer/actions/workflows/ci.yml)
[![Open the tutorial in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/rasoulnorouzi/theoryminer/blob/main/tutorials/TUTORIAL.ipynb)

Assemble theories from text. `theoryminer` reads a PDF, finds the sentences that make causal
claims, extracts each cause → effect pair, and brings the many ways authors name the same
construct together, with a thesaurus (ELSST) or without one. Then it draws a causal map: an
interactive page where every arrow leads back to the sentences that claim it.

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
                                  └───────────────┬───────────────┘
                                                  ▼
                        causal_map() ──► draw_map() (interactive page), save_map() (tables, GraphML)
```

Status: extraction, harmonisation and the causal map are written. The evaluation is planned.

## Install

Install from PyPI with pip:

```bash
pip install theoryminer
```

The install includes UMAP for `clusterer(..., umap={...})`.

The newest code on GitHub, before the next release:

```bash
pip install "theoryminer @ git+https://github.com/rasoulnorouzi/theoryminer.git"
```

In a notebook, such as Google Colab, put `%pip install` at the start of the first cell.
The tutorial notebook does this for you: click the Colab badge above.

To change the code, clone the repository and install it in editable mode:

```bash
git clone https://github.com/rasoulnorouzi/theoryminer.git
cd theoryminer
pip install -e ".[notebooks,dev,umap]"
```

### GPU

You do not need to set anything. `causenet(sentences)` uses `device="auto"`: an NVIDIA GPU when
PyTorch can see one, else the GPU of an Apple Silicon Mac, else the CPU. `device="cpu"`,
`"cuda"` or `"mps"` choose one device.

- **Google Colab:** choose a GPU runtime (Runtime → Change runtime type → T4 GPU). Colab already
  has a GPU build of PyTorch, so pip installs nothing extra.
- **Linux with an NVIDIA GPU:** the normal PyTorch from pip includes GPU support.
- **Windows with an NVIDIA GPU:** pip gives a CPU-only PyTorch there. The package then runs on
  the CPU, without errors. For the GPU, install PyTorch from https://pytorch.org first, then
  install `theoryminer`.
- **Apple Silicon Mac:** `"auto"` uses the Apple GPU. If the model fails there, it moves to the
  CPU and the run goes on.

The first call to `causenet()` downloads the SocioCausaNet model
(`rasoultilburg/SocioCausaNet`) from the Hugging Face Hub. The first call to a harmonizer
function downloads the sentence-transformer (`all-mpnet-base-v2` by default).

## Quick start

```python
from theoryminer import (harvest, extract_dois, extract_references, download_papers, causenet, clusterer,
                         label_groups, standardize_constructs, causal_map, draw_map, save_map)

data = harvest("raw_data/my_book.pdf", pages="12-540")   # clean sentences + a drop log
data = harvest("sample_files")                          # or every PDF in a folder
dois = extract_dois("sample_files", save="outputs")     # the DOI and title of each paper -> outputs/dois.csv
refs = extract_references("sample_files", save="outputs")   # the DOIs that the papers cite -> outputs/references.csv
report = download_papers(refs, "round_2", licences=["cc-by"])  # their open-access PDFs: the next snowball round
relations = causenet(data["sentences"])                 # one dict per cause → effect pair

groups = clusterer(relations)                           # group similar spans (HDBSCAN)
names = label_groups(groups)                            # name each group from its own words
matches = standardize_constructs(relations)             # or map each span to ELSST concepts

cmap = causal_map(relations, names)                     # nodes, edges, and the hidden edges
draw_map(cmap, papers=dois)                             # the interactive page (in a notebook, or causal_map.html)
save_map(cmap, "outputs/my_map")                        # nodes.csv, edges.csv, hidden.csv, map.graphml
```

`harvest()` takes one PDF or a folder of PDFs. In a folder, a file that is not a PDF, or a PDF
that cannot be read, does not stop the run. The drop log gets one row for it, with the reason.

`extract_references()` finds the DOIs in the references of seed papers, for a snowball search. It
repairs the DOIs that a PDF cuts at a line end. On the sample papers, 214 of its 215 DOIs exist at
doi.org. `download_papers()` downloads their open-access PDFs. It checks the licence of each paper
with OpenAlex first (free, no key), so `licences=["cc-by"]` downloads only CC BY papers. For more
sources, install the extra: `pip install "theoryminer[download]"` (Python 3.11 or newer). It adds
`tmsr-doi-downloader`, whose Unpaywall, CORE and Google Scholar sources take `email=`, `core_api_key=`
and `serpapi_key=`. The tutorial, section 11, runs one snowball round.

## The causal map

A node is a construct: a group of spans, or a thesaurus concept. An arrow goes from a cause to an
effect. Its width shows the number of papers that make the claim. On the page you can:

- hover over a node or an arrow, and click an arrow to read all its sentences, with the DOI of each
  paper (else its title, else its file name);
- search as a filter: "age" shows only the matching nodes and their neighbours (or 2 steps, or only
  the matches), and hides the rest;
- filter by paper, by role ("cause only", "cause and effect", "effect only"), by two-way pairs, and with
  `min papers`, `min sentences` and the self-loop switch; drag, zoom, and Reset;
- save a picture as PNG, JPG or SVG: the whole map, the current view, or one node with its neighbours.

The page is one HTML file that works offline. Nothing is deleted: a two-way claim keeps both arrows,
and an edge that a filter hides stays in the data with its reason.

## Sample papers

`sample_files/` holds 7 open-access social-science papers with a CC BY licence.
`sample_files/SOURCES.md` gives the title, authors, DOI and licence of each one.
The tutorial and the tests use them.

## Data you supply

Give `harvest()` your own PDFs. In a clone, `raw_data/` is a good place for them: git ignores it.

The ELSST thesaurus (release 5) ships inside the package as `theoryminer/data/ELSST_R5.rdf.gz`.
`taxonomy="elsst"` needs no extra file. A full path to another SKOS `.rdf` or `.rdf.gz` file also
works as `taxonomy=`. The thesaurus vectors are computed once and cached in
`~/.cache/theoryminer/taxonomy`. Set the environment variable `THEORYMINER_CACHE_DIR` to use
another folder. If the folder cannot be written, the functions still work; they only compute the
vectors again in the next session.
`label_groups()` needs no thesaurus at all.

## Documentation

All learning material is in `tutorials/`:

| file | what it is |
|---|---|
| `tutorials/TUTORIAL.ipynb` | every function and every setting, with real output, and a full run on the sample papers, up to the causal map |
| `tutorials/PACKAGE_LINE_BY_LINE.ipynb` | each function taken apart line by line and checked against the real one |
| `tutorials/STRATEGIES.md` | the six ways to turn a thesaurus concept into text, and the test behind the defaults |

The notebooks work from `tutorials/` and from the repository root. The examples use the papers in
`sample_files/`.

## Tests

```bash
pip install -e ".[dev]"
pytest                 # the fast tests: no model download, a few seconds
pytest -m slow         # the tests that load the real models (about 1 GB on the first run)
```

GitHub Actions runs the fast tests on each push, on Linux, Windows and macOS. It also builds the
package and tests the built wheel. The slow tests run on each push to `main` and every Monday.

## Releases

A push to `main` never publishes. A release goes to PyPI in three steps:

1. Set the new version in `pyproject.toml`, add a section to `CHANGELOG.md`, push, and wait for a green CI.
2. On GitHub: **Releases → Draft a new release**, tag `v` plus the version (for example `v0.1.0`),
   **Generate release notes**, **Publish release**.
3. In the Actions tab, open the "Publish to PyPI" run and approve it (**Review deployments**).

The workflow stops when the tag and the version differ. PyPI trusts the workflow through Trusted
Publishing, so no token is stored in the repository.

## Licence

The code has the MIT licence. See `LICENSE`.

These files in this repository keep their own licence:

- `theoryminer/data/ELSST_R5.rdf.gz`: ELSST, © CESSDA, CC BY-SA 4.0. See `theoryminer/data/ELSST_LICENSE.md`.
- `sample_files/*.pdf`: open-access papers, CC BY 4.0. See `sample_files/SOURCES.md`.
- `theoryminer/data/cytoscape.min.js` (Cytoscape.js) and the fcose layout files (`layout-base.js`,
  `cose-base.js`, `cytoscape-fcose.js`): MIT. Each page that `draw_map()` makes holds a copy, with the
  licence text.
