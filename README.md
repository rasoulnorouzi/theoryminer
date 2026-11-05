# theoryminer

[![PyPI](https://img.shields.io/pypi/v/theoryminer)](https://pypi.org/project/theoryminer/)
[![CI](https://github.com/rasoulnorouzi/theoryminer/actions/workflows/ci.yml/badge.svg)](https://github.com/rasoulnorouzi/theoryminer/actions/workflows/ci.yml)
[![Documentation](https://img.shields.io/badge/docs-book-blue)](https://rasoulnorouzi.github.io/theoryminer/)
[![Open the tutorial in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/rasoulnorouzi/theoryminer/blob/main/tutorials/TUTORIAL.ipynb)

`theoryminer` reads a set of research papers and makes a causal map from them.

A causal map shows the constructs of the papers as nodes, and the causal claims between them as
arrows. An arrow from "social support" to "well-being" means that the papers claim that social
support causes well-being. Click an arrow to read the sentences that make the claim, with the
page and the DOI of each paper.

The documentation is at **https://rasoulnorouzi.github.io/theoryminer/**. It has one guide page
for each step, with an example, all the arguments and the result.

## Install

`theoryminer` needs Python 3.10 or newer.

```bash
pip install theoryminer
```

In a notebook, such as Google Colab, put `%pip install theoryminer` in the first cell.

## Quick start

Put your PDF files into one folder. This example uses the folder `sample_files/` of this
repository, with 7 open-access papers.

```python
from theoryminer import (harvest, causenet, clusterer, label_groups,
                         causal_map, draw_map, save_map)

# 1. Read the PDFs in the folder. Split their text into sentences.
data = harvest("sample_files")

# 2. Find the causal claims (cause -> effect) in the sentences.
relations = causenet(data["sentences"])

# 3. Put the causes and effects that mean the same construct into groups.
groups = clusterer(relations)

# 4. Give each group a name.
names = label_groups(groups)

# 5. Make the map, show it, and write it to files in the folder outputs/my_map.
cmap = causal_map(relations, names)
draw_map(cmap)
save_map(cmap, "outputs/my_map")
```

The first run downloads two models (about 850 MB in total). On a laptop CPU, step 2 takes about
2 minutes for the 7 papers. A GPU is much faster: in Colab, select Runtime → Change runtime type →
T4 GPU.

## The functions

| Step | Function | What it does |
|---|---|---|
| Read | `harvest()` | reads PDF files and returns their sentences |
| Read | `extract_dois()` | returns the DOI and the title of each PDF |
| Read | `extract_references()` | returns the DOIs in the reference lists of the PDFs |
| Download | `download_papers()` | downloads the free PDFs of a list of DOIs |
| Find claims | `causenet()` | finds the cause and the effect of each causal claim |
| Group | `clusterer()`, `pairwise_grouping()` | put the spans with the same meaning into groups |
| Name | `label_groups()` | names each group with its own words |
| Name | `standardize_groups()`, `standardize_constructs()` | name the groups or the spans with terms of the ELSST thesaurus |
| Map | `causal_map()` | makes the nodes and the edges |
| Map | `draw_map()` | shows the map as a web page |
| Map | `save_map()` | writes the map to CSV files and a GraphML file |

## Tutorials

| File | What it is |
|---|---|
| `tutorials/TUTORIAL.ipynb` | runs every function and every setting on the sample papers, with the output |
| `tutorials/PACKAGE_LINE_BY_LINE.ipynb` | shows the code of each function, line by line |

## Development

See the [Development page](https://rasoulnorouzi.github.io/theoryminer/development.html) for the
tests, the documentation build and the releases.

## Licence

The code has the MIT licence. See `LICENSE`.

These files keep their own licence:

- `theoryminer/data/ELSST_R5.rdf.gz`: ELSST, © CESSDA, CC BY-SA 4.0. See `theoryminer/data/ELSST_LICENSE.md`.
- `sample_files/*.pdf`: open-access papers, CC BY 4.0. See `sample_files/SOURCES.md`.
- `theoryminer/data/cytoscape.min.js` (Cytoscape.js) and the fcose layout files (`layout-base.js`,
  `cose-base.js`, `cytoscape-fcose.js`): MIT. Each page that `draw_map()` makes holds a copy, with the
  licence text.
