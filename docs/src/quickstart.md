# Quick start

This page makes a causal map from 7 papers. The papers are in the folder `sample_files/` of the
repository. To get them, clone the repository:

```bash
git clone https://github.com/rasoulnorouzi/theoryminer.git
cd theoryminer
```

To use your own papers, put your PDF files into one folder. Then use the path of that folder in
place of `"sample_files"`.

## The code

```python
from theoryminer import (harvest, causenet, clusterer, label_groups,
                         causal_map, draw_map, save_map)

# 1. Read the PDFs. Split their text into sentences.
data = harvest("sample_files")

# 2. Find the causal claims (cause -> effect) in the sentences.
relations = causenet(data["sentences"])

# 3. Put the spans that mean the same construct into groups.
groups = clusterer(relations)

# 4. Give each group a name.
names = label_groups(groups)

# 5. Make the nodes and the edges of the map.
cmap = causal_map(relations, names)

# 6. Show the map.
draw_map(cmap)

# 7. Write the map to files in the folder outputs/my_map.
save_map(cmap, "outputs/my_map")
```

## What each step does

1. `harvest("sample_files")` reads all the PDF files in the folder `sample_files`. It keeps 2,531
   sentences. It removes the headings, the tables, the page numbers and the reference lists.
   `data["sentences"]` holds the sentences. `data["dropped"]` holds the removed lines, each with
   the reason. [More about `harvest()`](guide/harvest.md).
2. `causenet(data["sentences"])` finds 945 relations. A relation is a cause, an effect, and the
   sentence that claims it. The first call downloads the model (about 430 MB). On a laptop CPU,
   this step takes about 2 minutes. [More about `causenet()`](guide/causenet.md).
3. `clusterer(relations)` reads the causes and the effects. It puts the spans with the same meaning
   into one group, for example "loneliness" and "feelings of loneliness". The first call downloads
   a second model (about 420 MB). [More about groups](guide/harmonizer.md).
4. `label_groups(groups)` gives each group a name from the words that its members use.
5. `causal_map(relations, names)` makes one node for each group, and one edge for each cause and
   effect pair of nodes. It hides the edges that only one sentence claims.
   [More about the map](guide/causal-map.md).
6. `draw_map(cmap)` shows the map in the notebook. In a Python script, it writes the file
   `causal_map.html`. Open that file in a web browser. Click an edge to read its sentences.
7. `save_map(cmap, "outputs/my_map")` writes 4 files into the folder `outputs/my_map`:
   `nodes.csv`, `edges.csv`, `hidden.csv` and `map.graphml`.

## Look at one relation

Each relation tells where it comes from:

```python
relation = relations[0]
print(relation["cause"], "->", relation["effect"])
print(relation["sentence"])
print(relation["doc_id"], "page", relation["page"], relation["doi"])
```

## Next steps

- To name the groups with the terms of a social-science thesaurus, see
  [Group and name constructs](guide/harmonizer.md).
- To find and download the papers that your papers cite, see
  [A snowball round](guide/snowball.md).
- For all the arguments of a function, see its page under [Reference](reference/index.md).
