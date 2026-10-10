# Install

`theoryminer` needs Python 3.10 or newer.

## From PyPI

```bash
pip install theoryminer
```

The install includes UMAP (for `clusterer(..., umap={...})`) and `tmsr-doi-downloader`, an extra
download source. On Python 3.10, pip leaves out `tmsr-doi-downloader`. The default download
sources work on every version.

## The newest code

To get the code on GitHub before the next release:

```bash
pip install "theoryminer @ git+https://github.com/rasoulnorouzi/theoryminer.git"
```

## In a notebook

In Google Colab or Jupyter, put this line at the start of the first cell:

```python
%pip install theoryminer
```

The [tutorial notebook](tutorials.md) does this for you.

## The models

The package downloads two models on first use. It keeps them in the Hugging Face cache, so later
runs use the local copy.

| Model | First used by | Size |
|---|---|---|
| `rasoultilburg/SocioCausaNet` | `causenet()` | about 430 MB |
| `sentence-transformers/all-mpnet-base-v2` | the grouping and naming functions | about 420 MB |

Without a network, set the environment variable `HF_HUB_OFFLINE=1`. The models must already be in
the cache.

## The GPU

You do not need to set anything. `causenet()` uses `device="auto"`: an NVIDIA GPU when PyTorch sees
one, else the GPU of an Apple Silicon Mac, else the CPU.

| System | What to do |
|---|---|
| Google Colab | Choose a GPU runtime: Runtime → Change runtime type → T4 GPU. |
| Linux with an NVIDIA GPU | Nothing. The PyTorch from pip supports the GPU. |
| Windows with an NVIDIA GPU | Install PyTorch from [pytorch.org](https://pytorch.org) first, then `theoryminer`. The PyTorch from pip uses only the CPU on Windows. |
| Apple Silicon Mac | Nothing. When the model fails on the Apple GPU, the run moves to the CPU. |

## The caches

| What | Where | Change it with |
|---|---|---|
| The text of each PDF page | `<pdf>.pages.json` beside each PDF | `harvest(..., cache=False)` |
| The thesaurus vectors | `~/.cache/theoryminer/taxonomy` | the environment variable `THEORYMINER_CACHE_DIR` |
| The models | the Hugging Face cache | the environment variable `HF_HOME` |

When the package cannot write a cache folder, the functions still work. They compute the vectors
again in the next session.
