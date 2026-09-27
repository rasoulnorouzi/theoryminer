# Changelog

Each release of `theoryminer` has one section. The newest release is first.
The version numbers follow semantic versioning: before 1.0.0, a minor release (0.x.0) can change the API.

## 0.2.0

### Added

- The causal map. `causal_map()` turns the relations and the names of their groups into nodes and edges.
  An edge has two weights, papers and relations, and keeps its `rel_id`s. Self-loops and two-way pairs
  get flags. The filters `min_papers` (default 1) and `min_relations` (default 2) move the weak edges to
  `hidden`, with a reason; nothing is deleted.
- `draw_map()` shows the map as an interactive page: in a notebook cell, or as `causal_map.html` from a
  script. The page works offline. It has hover cards, a panel with every sentence and the DOI or title of
  its paper, search, filters, and a picture export as PNG, JPG or SVG.
- `save_map()` writes `nodes.csv`, `edges.csv`, `hidden.csv` and `map.graphml`.
- `extract_dois()` has a new column, `title`: the largest font on page 1, else the PDF metadata.
- `causenet(avoid_ambiguous=True)` skips a relation whose cause or effect only points to another
  sentence ("this", "it", "such things"). The summary prints the count and examples.
- `pairwise_grouping(linkage=...)`: `"average"`, `"complete"` or `"single"`.
- `standardize_constructs()` and `standardize_groups()` have a `threshold`. It is off by default.
- `harvest()` drops the licence and copyright text of a journal, with the reason `licence_text`.

### Changed

These defaults change the results of a run that uses them. Give the old value to get the old results.

- `causenet()`: `decision="span_only"` (was `"cls+span"`) and `avoid_ambiguous=True` (new).
- `pairwise_grouping()`: `linkage="average"` (the old method is `linkage="single"`). Single linkage chains:
  on the sample papers its largest group held 153 spans; average linkage gives 27.
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
