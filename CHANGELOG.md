# Changelog

Each release of `theoryminer` has one section. The newest release is first.
The version numbers follow semantic versioning: before 1.0.0, a minor release (0.x.0) can change the API.

## 0.3.0

This release rewrites `download_papers()` and restructures the first stages into folders.

### Added

- A documentation website: https://rasoulnorouzi.github.io/theoryminer/. It has a guide for each
  step, a reference page for each public function, and every setting with its default. The book is
  made with mdBook from `docs/`. The reference pages come from the docstrings (`docs/make_api.py`),
  so they always match the code. A push to `main` publishes the book with GitHub Pages.
- `download_papers()` is rewritten. It tries many free sources in turn until one gives a real PDF:
  OpenAlex, per-publisher plugins, PubMed Central, Europe PMC, Unpaywall, Semantic Scholar, Crossref,
  OSF preprints, and the doi.org landing page. On a 100-DOI benchmark it downloads the correct PDF for
  33 papers; the old version (OpenAlex, then `tmsr-doi-downloader`) downloaded 25. It is also faster.
  The new `sources` setting chooses the sources and their order.
- Per-publisher plugins, in the style of Zotero translators (`theoryminer/download/publishers.py`).
  A plugin turns a DOI into the direct PDF link of its publisher (Springer with BMC and Palgrave,
  and Frontiers). To add a journal, add one plugin.
- `download_papers()` gets open-access copies only. It does not log in to a publisher site and it
  does not use a browser. A paper that is only behind a paywall stays `not_found`.
- `respect_robots` (default `True`). Set it `False` only when you have the right to download from the
  sites, for example by an agreement of your institution.
- The DOI and title of each paper travel with the data. `harvest()` puts `doi` and `title` on every
  sentence (new setting `find_dois`, default `True`). `causenet()` copies them to every relation.
  `causal_map()` collects them in `cmap["papers"]`, and `draw_map(cmap)` shows them. The call
  `draw_map(cmap, papers=extract_dois(folder))` is no longer needed; `papers=` still works.
- A better DOI rule, shared by `harvest()` and `extract_dois()`. The DOI comes from the most certain
  source: the download log `downloads.csv` of the folder, a DOI in the text that gives the file name
  of a `download_papers()` PDF, the subject or keywords field of the PDF metadata, then the first DOI
  on pages 1-2. `extract_dois()` rows have a new column `source`. On 21 papers with a known DOI
  (7 sample papers and 14 downloads) the rule finds 20; the old rule found 18.
- `download_papers()` always writes its log `downloads.csv` into the PDF folder. The log keeps
  the rows of earlier runs. `harvest()` reads it, so it knows the DOI of every downloaded PDF.

### Changed

- The modules of the first stages are in two new folders. The public functions do not change:
  `from theoryminer import harvest, extract_dois, extract_references, download_papers` works as before.

  | Before | Since this release |
  |---|---|
  | `theoryminer/harvest.py` | `theoryminer/prepare/harvest.py` |
  | `theoryminer/dois.py` | `theoryminer/prepare/dois.py` |
  | `theoryminer/download.py` | `theoryminer/download/papers.py` |

- `download_papers()` no longer uses `tmsr-doi-downloader` in the default. On the benchmark it added
  one paper per hundred and doubled the run time. `tmsr-doi-downloader` stays a dependency and an
  opt-in source: `sources=[..., "tmsr-doi-downloader"]`.

- The docstrings of the public functions give, for each argument, every permitted value
  and what the default does in words. For example, `harvest(steps=None)` names the 10 steps
  of `DEFAULT_STEPS`. Five functions got an example: `causenet()`, `standardize_constructs()`,
  `standardize_groups()`, `pairwise_grouping()` and `clusterer()`. A new test,
  `tests/test_docstrings.py`, checks every argument and every choice value.
- `causenet()` checks its settings before the model loads. An unknown `mode` or `decision`,
  a `threshold` outside 0 to 1, or a `batch_size` below 1 raises a `ValueError`.
  `mode` accepts `"neural"` and `"auto"`. Before, `mode="heuristic"` (or a typing error)
  ran the neural path without a message, and an unknown `decision` ran `"cls+span"`.
- `harvest()` checks its settings before it reads a PDF. A page selection that is not a page,
  an unknown step name, `min_words` below 1, or `max_words` below `min_words` raises a
  `ValueError` with the permitted values. Before, an unknown step gave a `KeyError`.

### Fixed

- `clusterer()` no longer prints a `FutureWarning` from scikit-learn 1.9 about the `copy` setting of
  HDBSCAN. The clusters do not change.
- `tutorials/PACKAGE_LINE_BY_LINE.ipynb` runs again without an error. Four cells used the APA
  thesaurus (removed) or the defaults before 0.2.0 (`leaves_only=True`, `linkage="single"`).

### Deprecated

- The module paths `theoryminer.harvest` and `theoryminer.dois` still work, as aliases of the new modules.
  They go away in 0.4.0. Use `theoryminer.prepare.harvest` and `theoryminer.prepare.dois`.
- `theoryminer.download` is now a folder. `from theoryminer.download import download_papers` still works.
  Its private helpers (names that start with `_`) are in `theoryminer.download.papers`.

## 0.2.2

### Added

- Editor support. The 13 public functions have type hints: the kind of each setting and of the result.
  The package holds the marker file `py.typed` (PEP 561), so VS Code (Pylance), PyCharm and type checkers
  use these hints: they suggest the settings, and they mark a wrong value, for example `min_words="four"`.
- `__all__` in `theoryminer` and in `theoryminer.harmonizer` lists the public names.

## 0.2.1

### Changed

- `pip install theoryminer` installs `tmsr-doi-downloader` on Python 3.11 or newer, so `download_papers()`
  has all its sources without an extra. On Python 3.10 it is left out, and `download_papers()` uses
  OpenAlex only. The old command `pip install "theoryminer[download]"` still works.
- CI installs and tests the package on Windows and macOS with Python 3.11, 3.12 and 3.13, and on Linux
  with Python 3.10 to 3.13.

### Fixed

- `download_papers()` no longer clears a key that you set as an environment variable (`UNPAYWALL_EMAIL`,
  `CORE_API_KEY`, `SERPAPI_KEY`). A key that you do not pass as an argument keeps its environment value.

## 0.2.0

### Added

- The causal map. `causal_map()` turns the relations and the names of their groups into nodes and edges.
  An edge counts papers, sentences and relations, and keeps its `rel_id`s. Two relations of one sentence
  on one edge count as one sentence. Self-loops and two-way pairs get flags. The filters `min_papers`
  (default 1) and `min_sentences` (default 2) move the weak edges to `hidden`, with a reason; nothing is
  deleted.
- `draw_map()` shows the map as an interactive page: in a notebook cell, or as `causal_map.html` from a
  script. The page works offline. It has hover cards, a panel with every sentence and the DOI or title of
  its paper, a search that filters the map (the matches and their neighbours), filters by paper, role,
  two-way pairs, papers and sentences, and a picture export as PNG, JPG or SVG.
- `save_map()` writes `nodes.csv`, `edges.csv`, `hidden.csv` and `map.graphml`.
- `extract_references()` finds the DOIs in the references of seed papers, one row per DOI, with the number
  of seeds that cite it. It repairs a DOI that the PDF cuts at a line end, and it leaves out the seed's own
  DOI and its figure and table DOIs. It can save a CSV file with a `doi` column. On the sample papers,
  214 of its 215 DOIs exist at doi.org.
- `download_papers()` downloads the open-access PDFs of a list of DOIs. It asks OpenAlex for the licence
  first, so `licences=["cc-by"]` downloads only CC BY papers. Then it tries the OpenAlex links and, when it
  is installed, `tmsr-doi-downloader` (`pip install "theoryminer[download]"`, Python 3.11 or newer).
  One status row per DOI; a failed DOI does not stop the run; a second run skips the files it has.
- `extract_dois()` has a new column, `title`: the largest font on page 1, else the PDF metadata.
- `causenet(avoid_ambiguous=True)` skips a relation whose cause or effect only points to another
  sentence ("this", "it", "such things"). The summary prints the count and examples.
- `pairwise_grouping(linkage=...)`: `"average"`, `"complete"` or `"single"`.
- `standardize_constructs()` and `standardize_groups()` have a `threshold`. It is off by default.
- `harvest()` drops the licence and copyright text of a journal, with the reason `licence_text`.

### Fixed

- `causenet()` no longer returns a relation with an empty cause or effect (the model decoded only special
  tokens). The summary counts them. Before, `causal_map()` stopped on such a relation.

### Changed

These defaults change the results of a run that uses them. Give the old value to get the old results.

- `causenet()`: `decision="span_only"` (was `"cls+span"`) and `avoid_ambiguous=True` (new).
- `pairwise_grouping()`: `linkage="average"` (the old method is `linkage="single"`). Single linkage chains:
  on the sample papers its largest group held 153 spans; average linkage gives 27.
- `standardize_constructs()` and `standardize_groups()`: `leaves_only=False` (was `True`). A span can now
  also match a broad ELSST concept, such as TRUST or MOTIVATION.
- `label_groups()`: `by="keywords"` (was `"both"`). The label is the TF-IDF keywords of the group.
- `networkx` is a declared dependency (`save_map()` writes GraphML with it). PyTorch installed it already.

### Data in the package

- `causal_map.html` (the page template), Cytoscape.js 3.30.2 and the fcose layout (all MIT).

## 0.1.1

### Changed

- `umap-learn` is installed by default. `pip install theoryminer` is enough for `clusterer(..., umap={...})`.
  The old command `pip install "theoryminer[umap]"` still works.
- The thesaurus vectors are saved in `~/.cache/theoryminer/taxonomy`, not inside the installed package.
  The environment variable `THEORYMINER_CACHE_DIR` chooses another folder.

### Fixed

- A read-only install no longer fails on the first `standardize_constructs()` call. When the cache folder
  cannot be written, the function prints one line and goes on without the cache.
- `pip uninstall theoryminer` no longer leaves a cache folder in the package folder.

## 0.1.0 (first release on PyPI)

### Functions

- `harvest()` reads one PDF, or every PDF in a folder, and returns clean sentences and a drop log.
  A bad file in a folder does not stop the run. Each `sent_id` starts with the document number.
- `extract_dois()` finds the DOI of each paper: the first DOI on page 1, else on page 2.
  It returns one row per file and can save a CSV file.
- `causenet()` finds cause-effect pairs with the SocioCausaNet model. `device="auto"` uses an NVIDIA GPU,
  else an Apple GPU, else the CPU.
- `standardize_constructs()` and `standardize_groups()` map spans and groups to ELSST concepts.
- `pairwise_grouping()`, `clusterer()` and `label_groups()` group and name the spans without a thesaurus.

### Data in the package

- ELSST release 5 (CC BY-SA 4.0, © CESSDA) ships in the package. `taxonomy="elsst"` needs no extra file.

### Tests and release

- Fast tests run on each push, on Linux, Windows and macOS. Slow tests load the real models.
- A GitHub Release publishes the package to PyPI through Trusted Publishing.
