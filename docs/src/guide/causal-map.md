# The causal map

Three functions turn the relations and the names into a map:

| Function | What it does |
|---|---|
| `causal_map()` | builds the nodes and the edges |
| `draw_map()` | shows the map as an interactive page |
| `save_map()` | writes the map as CSV tables and a GraphML file |

```python
from theoryminer import causal_map, draw_map, save_map

cmap = causal_map(relations, names)
draw_map(cmap)
save_map(cmap, "outputs/my_map")
```

`names` is the output of `label_groups()`, `standardize_groups()` or `standardize_constructs()`.
See [Group and name constructs](harmonizer.md).

## Nodes and edges

A node is a construct: a named group, or a thesaurus concept. An edge goes from a cause node to an
effect node. It counts the papers, the sentences and the relations that claim it, and it keeps the
`rel_ids` of those relations. So each edge leads back to its sentences.

| Edge key | Meaning |
|---|---|
| `n_papers`, `n_sentences`, `n_relations` | how many papers, sentences and relations claim the edge |
| `rel_ids`, `doc_ids` | the relations and the papers behind the edge |
| `self_loop` | `True` when the cause and the effect are the same node |
| `reciprocal` | `True` when the opposite edge also exists (a two-way pair) |
| `direction` | `one-way`, or for a two-way pair `dominant`, `minority` or `contested` |
| `drop_reason` | `""` for a shown edge, else why the edge is hidden |

A node has a role, from its shown edges: `cause only`, `effect only` or `cause and effect`.

## Which edges show

`causal_map()` hides a weak edge, but it deletes nothing. A hidden edge goes to `cmap["hidden"]`
with its reason.

| Setting | Default | A shown edge needs |
|---|---|---|
| `min_papers` | `1` | at least this many papers. `1` also suits one long book. |
| `min_sentences` | `2` | at least this many sentences. Use `1` to show every edge. |

A hidden edge has the `drop_reason` `below_min_papers` or `below_min_sentences`.

## Two-way pairs

When papers claim both A → B and B → A, both edges stay. `min_share` (default `0.67`) decides how the
pair is read. When one side has at least 2/3 of the papers, that side is `dominant` and the other
side is `minority`. Otherwise both sides are `contested`. A `minority` edge shows as a dashed line.

## The page

`draw_map()` writes one HTML file that works offline. In a notebook it shows in the cell. In a
script it writes `causal_map.html`, or the file that you give with `save=`.

On the page you can:

- hover over a node or an edge, and click an edge to read all its sentences, with the DOI of each
  paper (else its title, else its file name);
- search for a construct: the page shows only the matches and their neighbours;
- filter by paper, by role, by two-way pairs, with the `min papers` and `min sentences` sliders, and
  with the self-loop switch;
- drag, zoom and reset;
- save a picture as PNG, JPG or SVG: the whole map, the current view, or one node with its
  neighbours.

The page receives every edge, also the hidden ones. Its sliders start at the values of
`causal_map()`, so you can show a hidden edge on the page.

**Warning:** a large map opens slowly. The page computes the layout in the browser. In our test, a
map with 1,000 shown nodes took about 78 seconds to open. A map with 3,000 nodes did not open in
10 minutes. Keep the map small with `min_papers` and `min_sentences`. Most readers cannot read more
than a few hundred nodes anyway.

## The files

`save_map(cmap, folder)` writes:

| File | What it holds |
|---|---|
| `nodes.csv` | one row per node, also the nodes that no shown edge touches |
| `edges.csv` | one row per shown edge |
| `hidden.csv` | one row per hidden edge, with its `drop_reason` |
| `map.graphml` | every node and edge, for Gephi or Cytoscape Desktop |

In the CSV files, a list (members, doc_ids, rel_ids) is one text, joined by ` | `.
