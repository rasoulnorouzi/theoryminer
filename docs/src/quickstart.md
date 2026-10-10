# Quick start

This page runs the full pipeline on the 7 sample papers in the folder `sample_files/` of the
repository. The numbers below come from that run on a laptop CPU.

To get the sample papers, clone the repository:

```bash
git clone https://github.com/rasoulnorouzi/theoryminer.git
cd theoryminer
```

## The full run

```python
from theoryminer import (harvest, causenet, clusterer, label_groups,
                         causal_map, draw_map, save_map)

data = harvest("sample_files")                  # 1. PDFs -> clean sentences
relations = causenet(data["sentences"])         # 2. sentences -> cause -> effect pairs
groups = clusterer(relations)                   # 3. group the spans that name the same construct
names = label_groups(groups)                    # 4. name each group from its own words
cmap = causal_map(relations, names)             # 5. nodes and edges
draw_map(cmap)                                  # 6. the interactive page
save_map(cmap, "outputs/my_map")                # 7. CSV tables and a GraphML file
```

## What each line gives

1. `harvest()` reads the 7 PDFs. It keeps 2,531 sentences and drops 1,865 rows: table rows, the
   reference sections, headings, page furniture. Each dropped row keeps its reason in
   `data["dropped"]`. Each sentence has the DOI and the title of its paper.
2. `causenet()` finds 490 causal sentences and 945 relations. It takes about 2 minutes on a CPU.
   The first call downloads the model (about 430 MB).
3. `clusterer()` puts the 1,197 different spans into 242 groups. A span that fits no group stays
   alone.
4. `label_groups()` names each group with the words that its members repeat.
5. `causal_map()` makes 50 nodes and 35 shown edges. It hides 849 weak edges and keeps them in
   `cmap["hidden"]`, each with its reason. By default an edge needs 2 sentences to show.
6. `draw_map()` shows the page in a notebook. In a script it writes `causal_map.html`.
7. `save_map()` writes `nodes.csv`, `edges.csv`, `hidden.csv` and `map.graphml`.

## Look at one relation

Each relation leads back to its source:

```python
relation = relations[0]
print(relation["cause"], "->", relation["effect"])
print(relation["sentence"])
print(relation["doc_id"], "page", relation["page"], relation["doi"])
```

## Next steps

- Use your own PDFs: `harvest("path/to/folder")`.
- Use the ELSST thesaurus for the names: see [Group and name constructs](guide/harmonizer.md).
- Find and download the papers that your papers cite: see [A snowball round](guide/snowball.md).
- See every setting with its default: [Settings and defaults](settings.md).
