# Changelog

Each release of `theoryminer` has one section. The newest release is first.
The version numbers follow semantic versioning: before 1.0.0, a minor release (0.x.0) can change the API.

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
