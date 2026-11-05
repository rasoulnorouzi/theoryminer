# The causal map

A causal map shows the constructs of your papers as nodes, and the causal claims between them as
arrows (edges). An arrow from "job insecurity" to "stress" means that your papers claim that job
insecurity causes stress.

Three functions make the map:

| Function | What it does |
|---|---|
| `causal_map()` | makes the nodes and the edges from the relations and the names |
| `draw_map()` | shows the map as an interactive web page |
| `save_map()` | writes the map to CSV files and a GraphML file |

## An example

```python
from theoryminer import causal_map, draw_map, save_map

cmap = causal_map(
    relations,               # the relations from causenet()
    names,                   # the names from label_groups() or standardize_groups()
    min_sentences=2,         # show an edge only when 2 or more sentences claim it
)

draw_map(cmap)                     # show the page in the notebook
save_map(cmap, "outputs/my_map")   # write the files into the folder outputs/my_map
```

## `causal_map()`: make the nodes and the edges

Each group of spans becomes one node. Each relation becomes an arrow from the node of its cause to
the node of its effect. When many relations go from the same cause node to the same effect node,
they become one edge. The edge counts its papers and its sentences.

The function hides the weak edges. A hidden edge is not deleted: it goes to `cmap["hidden"]`, and
you can show it on the page.

| Argument | What you give | Default |
|---|---|---|
| `relations` | The relations from `causenet()`. | none; you must give it |
| `names` | The result of `label_groups()`, `standardize_groups()` or `standardize_constructs()`, made from the same relations. | none; you must give it |
| `min_papers` | An edge is shown only when this number of papers or more claim it. Use `1` for one long book. | `1` |
| `min_sentences` | An edge is shown only when this number of sentences or more claim it. Use `1` to show every edge. | `2` |
| `min_share` | A number above 0.5, up to 1. It is for a two-way pair, see below. | `0.67` |

### Two-way pairs

Sometimes papers claim A → B, and other papers claim B → A. The map keeps both edges. `min_share`
tells which side is the main direction. With the default `0.67`, a side with 2/3 of the papers or
more is `"dominant"`, and the other side is `"minority"`. The page shows a minority edge as a
dashed line. When no side has 2/3 of the papers, both sides are `"contested"`.

### The result

A dict with these keys:

| Key | What it holds |
|---|---|
| `cmap["nodes"]` | a dict of the nodes, with the node id as the key |
| `cmap["edges"]` | a list of the shown edges |
| `cmap["hidden"]` | a list of the hidden edges |
| `cmap["relations"]` | the relations behind the edges, with the `rel_id` as the key |
| `cmap["papers"]` | one row for each paper: `doc_id`, `doi`, `title` |
| `cmap["settings"]` | the values of `min_papers`, `min_sentences` and `min_share` |

A node:

| Key | Meaning |
|---|---|
| `node_id` | the id of the node |
| `label` | the name of the node |
| `members` | the spans in the node |
| `as_cause` | the number of sentences in which the node is a cause |
| `as_effect` | the number of sentences in which the node is an effect |
| `n_sentences` | `as_cause` plus `as_effect` |
| `n_papers` | the number of papers with an edge of the node |
| `role` | `"cause only"`, `"effect only"`, `"cause and effect"`, or `""` when the node has no shown edge |
| `shown` | `True` when the node has a shown edge |

The counts of a node use only its shown edges.

An edge:

| Key | Meaning |
|---|---|
| `edge_id` | the id of the edge |
| `source` | the `node_id` of the cause |
| `target` | the `node_id` of the effect |
| `n_papers` | the number of papers that claim the edge |
| `n_sentences` | the number of sentences that claim the edge |
| `n_relations` | the number of relations behind the edge |
| `rel_ids` | the `rel_id` of each relation. Use them to find the sentences in `cmap["relations"]`. |
| `doc_ids` | the `doc_id` of each paper |
| `self_loop` | `True` when the cause and the effect are the same node |
| `reciprocal` | `True` when the edge in the other direction also exists |
| `direction` | `"one-way"`, or for a two-way pair `"dominant"`, `"minority"` or `"contested"` |
| `drop_reason` | `""` for a shown edge. For a hidden edge, `"below_min_papers"` or `"below_min_sentences"`. |

To read the sentences of the first edge:

```python
edge = cmap["edges"][0]
for rel_id in edge["rel_ids"]:
    print(cmap["relations"][rel_id]["sentence"])
```

## `draw_map()`: show the map

```python
from theoryminer import draw_map

draw_map(
    cmap,                            # the result of causal_map()
    save="outputs/map.html",         # also write the page to this file
    title="Causal map",              # the title at the top of the page
)
```

In a notebook, the page shows in the output of the cell. In a Python script, the function writes
the file `causal_map.html`. Open that file in a web browser. The page works without the internet.

| Argument | What you give | Default |
|---|---|---|
| `cmap` | The result of `causal_map()`. | none; you must give it |
| `save` | A path for the HTML file, for example `"outputs/map.html"`. | `None`: no file in a notebook; `causal_map.html` in a script |
| `title` | The title at the top of the page. | `"Causal map"` |
| `height` | The height of the map in a notebook, in pixels. | `720` |
| `papers` | The rows of `extract_dois()`. Use it only when you want other paper names than the ones that `harvest()` found. | `None`: the DOI and title from `harvest()` |

On the page, you can:

- click an edge to read all its sentences, with the DOI of each paper;
- search for a construct;
- filter the edges by paper, by role, and by the number of papers and sentences;
- move the nodes and zoom;
- save a picture of the map as PNG, JPG or SVG.

The page also holds the hidden edges. The filters start at the values of `causal_map()`. Move them
down to show the hidden edges.

A large map opens slowly, because the browser computes the positions of the nodes. A map with
1,000 shown nodes takes about 1 minute to open. Use `min_papers` and `min_sentences` to make the
map smaller.

## `save_map()`: write the files

```python
from theoryminer import save_map

save_map(
    cmap,                    # the result of causal_map()
    "outputs/my_map",        # the folder for the files; the function makes it
)
```

| Argument | What you give | Default |
|---|---|---|
| `cmap` | The result of `causal_map()`. | none; you must give it |
| `folder` | The folder for the files. | none; you must give it |

The function writes 4 files into the folder:

| File | What it holds |
|---|---|
| `nodes.csv` | one row for each node |
| `edges.csv` | one row for each shown edge |
| `hidden.csv` | one row for each hidden edge, with its `drop_reason` |
| `map.graphml` | all the nodes and edges. Open it in Gephi or Cytoscape Desktop. |

In the CSV files, a list, such as `members` or `rel_ids`, is one text, joined by ` | `.
The function returns the paths of the 4 files.
