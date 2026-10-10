# Tutorials

The repository has two notebooks. Both use the 7 sample papers in `sample_files/`.

| Notebook | What it does | Open it |
|---|---|---|
| `TUTORIAL.ipynb` | runs every function and every setting, with real output. Section 10 is a full run on the sample papers, up to the causal map. Section 11 is one snowball round. | [GitHub](https://github.com/rasoulnorouzi/theoryminer/blob/main/tutorials/TUTORIAL.ipynb) · [Colab](https://colab.research.google.com/github/rasoulnorouzi/theoryminer/blob/main/tutorials/TUTORIAL.ipynb) |
| `PACKAGE_LINE_BY_LINE.ipynb` | takes each function apart: it shows the code, runs its lines by hand, and checks the result against the real function | [GitHub](https://github.com/rasoulnorouzi/theoryminer/blob/main/tutorials/PACKAGE_LINE_BY_LINE.ipynb) · [Colab](https://colab.research.google.com/github/rasoulnorouzi/theoryminer/blob/main/tutorials/PACKAGE_LINE_BY_LINE.ipynb) |

In Colab, the first cell installs the package and downloads the sample papers. Choose a GPU
runtime for `causenet()`: Runtime → Change runtime type → T4 GPU.

On your own computer, run the notebooks from `tutorials/` or from the repository root. The first
cell moves to the repository root.

The page [Thesaurus strategies](strategies.md) explains the six ways to turn a thesaurus concept
into text, and the test behind the defaults.

## The sample papers

`sample_files/` holds 7 open-access social-science papers with a CC BY licence. The file
`sample_files/SOURCES.md` gives the title, the authors, the DOI and the licence of each paper.
