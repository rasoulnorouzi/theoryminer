# Development

## Set up

```bash
git clone https://github.com/rasoulnorouzi/theoryminer.git
cd theoryminer
python -m venv .venv
source .venv/bin/activate
pip install -e ".[notebooks,dev]"
```

The code uses plain functions with full docstrings. A step never deletes a row: it marks the row
and writes the reason. Keep these two rules when you add a step.

## Tests

```bash
pytest                                  # the fast tests: no model download, a few seconds
pytest -m slow                          # the tests that load the real models (about 1 GB on the first run)
pytest tests/test_harvest.py -k folder  # one test by name
```

GitHub Actions runs the fast tests on each push, on Linux, Windows and macOS. It also builds the
package and tests the built wheel.

## Benchmarks

| Benchmark | Command | What it measures |
|---|---|---|
| Downloads | `python benchmarks/downloader/run_benchmark.py --label my_run --email you@your-uni.edu` | the share of correct PDFs on a fixed set of 300 DOIs |
| Map speed | `python benchmarks/map/run_benchmark.py <out_folder>` | the time to build and open maps of 300 to 10,000 nodes |

## This documentation

The book uses [mdBook](https://rust-lang.github.io/mdBook/). The pages are Markdown files in
`docs/src/`. The reference pages come from the docstrings: a script writes them before each build,
so the docstrings stay the only source.

```bash
python docs/make_api.py     # write docs/src/reference/ from the docstrings
mdbook serve docs --open    # build the book and open it; it builds again when a file changes
```

To get `mdbook`, download it from its
[release page](https://github.com/rust-lang/mdBook/releases), or run `cargo install mdbook`.

A push to `main` builds the book and publishes it with GitHub Pages
(`.github/workflows/docs.yml`).

## Releases

A push to `main` never publishes to PyPI. A release has three steps:

1. Set the new version in `pyproject.toml`, and in the first cell of `tutorials/TUTORIAL.ipynb`
   (`%pip install -q "theoryminer==<version>"`). A test checks that the two match. Add a section to
   `CHANGELOG.md`. Push, and wait for a green CI.
2. On GitHub, open **Releases → Draft a new release**. Give the tag `v` plus the version, for
   example `v0.3.0`. Click **Generate release notes**, then **Publish release**.
3. In the Actions tab, open the "Publish to PyPI" run and approve it (**Review deployments**).

The workflow stops when the tag and the version are different. PyPI trusts the workflow through
Trusted Publishing, so the repository stores no token.
