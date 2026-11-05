# Group and name constructs

Authors use different words for one construct. One paper writes "loneliness", another writes
"feelings of loneliness", a third writes "perceived isolation". On the causal map, these spans
must be one node. Otherwise the map has three nodes for one idea.

This step has two parts:

1. Put the spans that mean the same thing into one group.
2. Give each group a name. The name becomes the label of the node on the map.

## Which functions to use

| You want | Use | Thesaurus |
|---|---|---|
| names from the words of your papers (start here) | `clusterer()`, then `label_groups()` | no |
| names from a fixed list of social-science terms | `clusterer()`, then `standardize_groups()` | ELSST, included |
| for each span, the nearest thesaurus terms | `standardize_constructs()` | ELSST, included |

A thesaurus is a fixed list of terms. The package includes ELSST, the European Language Social
Science Thesaurus, with 3,436 terms.

`pairwise_grouping()` can replace `clusterer()`. The two functions make groups in different ways.
See [`pairwise_grouping()`](#pairwise_grouping-groups-by-a-similarity-limit).

Each route gives the `names` that `causal_map()` needs:

```python
from theoryminer import clusterer, label_groups, causal_map

groups = clusterer(relations)        # 1. put similar spans into groups
names = label_groups(groups)         # 2. name each group
cmap = causal_map(relations, names)  # the map
```

## How the functions compare spans

The functions turn each span into a list of numbers, a vector. A language model makes the vectors.
Two spans with a similar meaning get similar vectors. The similarity of two vectors is a number
from -1 to 1 (the cosine). A higher number means a closer meaning.

The default model is `all-mpnet-base-v2`. The first call downloads it (about 420 MB).
The argument `embeddings` selects another model:

| `embeddings` | Model |
|---|---|
| `"allmpnet"` (default) | `sentence-transformers/all-mpnet-base-v2` |
| `"bge_base"` | `BAAI/bge-base-en-v1.5` |
| `"minilm"` | `sentence-transformers/all-MiniLM-L6-v2`, small and fast |
| any other name | a sentence-transformers model on Hugging Face |

## `clusterer()`: make groups

```python
from theoryminer import clusterer

groups = clusterer(
    relations,               # the relations from causenet(), or a list of spans
    min_cluster_size=2,      # the smallest group has 2 spans
)
```

`clusterer()` finds the areas where many span vectors are close together (the HDBSCAN method).
Each area is one group. A span that is not close to other spans stays alone. Such a span is
"noise" and gets the group number `-1`.

| Argument | What you give | Default |
|---|---|---|
| `items` | The relations from `causenet()`, or a list of span strings. The function uses each different span once. | none; you must give it |
| `min_cluster_size` | The smallest number of spans in a group. A whole number, 2 or more. | `2` |
| `min_samples` | How many close spans a span needs to be in a group. A higher number gives fewer groups and more noise. | `2` |
| `embeddings` | The model. See the table above. | `"allmpnet"` |
| `umap` | `None`, or a dict of UMAP settings, for example `dict(n_components=5)`. UMAP makes the vectors shorter before the grouping. This can help with many spans. | `None`: no UMAP |

## `pairwise_grouping()`: groups by a similarity limit

```python
from theoryminer import pairwise_grouping

groups = pairwise_grouping(
    relations,               # the relations from causenet(), or a list of spans
    threshold=0.69,          # two spans with a cosine of 0.69 or more can be in one group
)
```

`pairwise_grouping()` compares each span with each other span. A span joins a group when its
similarity to the group is `threshold` or more. Every span gets a group, so there is no noise.

| Argument | What you give | Default |
|---|---|---|
| `items` | The relations from `causenet()`, or a list of span strings. | none; you must give it |
| `threshold` | The similarity that a span needs to join a group. In practice, a number from 0.5 to 0.9. A higher number gives smaller groups. | `0.69` |
| `linkage` | How a span is compared with a group. `"average"`: the mean similarity to all members. `"complete"`: the similarity to each member. `"single"`: the similarity to one member. `"single"` can join spans with different meanings into one large group. | `"average"` |
| `embeddings` | The model. See the table above. | `"allmpnet"` |

This function uses much memory with many spans: about 10 GB for 50,000 spans. Use `clusterer()`
for a large set of papers.

### The result of both functions

A dict with one entry for each span:

```python
{"loneliness": {"group": 4, "central": "address loneliness"},
 "levels of loneliness": {"group": 4, "central": "address loneliness"}}
```

`group` is the number of the group. `central` is the member that is the most similar to the other
members of its group.

## `label_groups()`: name the groups with their own words

```python
from theoryminer import label_groups

names = label_groups(
    groups,                  # the result of clusterer() or pairwise_grouping()
    by="keywords",           # the name is the best keywords of the group
    top=3,                   # use 3 keywords
)
```

The function finds the words that the members of a group use often, and that the other groups do
not use (the c-TF-IDF method). It needs no model and no thesaurus.

| Argument | What you give | Default |
|---|---|---|
| `groups` | The result of `clusterer()` or `pairwise_grouping()`. | none; you must give it |
| `by` | `"keywords"`: the name is the `top` keywords, for example "loneliness reducing alleviate". `"medoid"`: the name is the central span, for example "reducing loneliness". `"both"`: the central span, then the keywords. | `"keywords"` |
| `top` | The number of keywords. | `3` |

The result has one entry for each group. The key is the group number. A noise span has its own
entry, with the span as the key.

```python
{4: {"central": "address loneliness",
     "size": 6,
     "members": ["loneliness", "levels of loneliness", ...],
     "keywords": [("loneliness", 0.91), ...],
     "name": "loneliness levels address"}}
```

| Key | Meaning |
|---|---|
| `central` | the central span |
| `size` | the number of spans in the group |
| `members` | the spans in the group |
| `keywords` | the best keywords, each with its score |
| `name` | the name of the group. The map uses it as the node label. |

## `standardize_groups()`: name the groups with thesaurus terms

```python
from theoryminer import standardize_groups

names = standardize_groups(
    groups,                  # the result of clusterer() or pairwise_grouping()
    top=5,                   # keep the 5 best thesaurus terms for each group
)
```

The function compares each group with each term of the thesaurus. The best term becomes the name
of the group. When two groups get the same best term, they become one node on the map.

The first call makes a vector for each thesaurus term. This takes about 3 minutes on a CPU. The
function saves the vectors in `~/.cache/theoryminer/taxonomy`, so later calls are fast.

| Argument | What you give | Default |
|---|---|---|
| `groups` | The result of `clusterer()` or `pairwise_grouping()`. | none; you must give it |
| `top` | The number of terms to keep for each group, best first. | `5` |
| `threshold` | `None`, or the lowest similarity that a term needs, in practice from 0.4 to 0.7. A group without a term keeps its central span as its name. | `None`: always keep the `top` terms |
| `name_by` | How a group is compared with a term. `"mean_sim"`: the mean similarity of the members. `"centroid"`: the similarity of the mean vector of the members. `"medoid"`: the similarity of the central span. | `"mean_sim"` |
| `leaves_only` | `False` allows all terms, also broad terms such as TRUST. `True` allows only the most specific terms. | `False` |
| `taxonomy` | `"elsst"`, or the path of another thesaurus file in the SKOS format (`.rdf` or `.rdf.gz`). | `"elsst"` |
| `strategy` | The text that stands for each term. `"enriched"` uses the term, its other names, its definition and its place in the thesaurus. See [Thesaurus strategies](../strategies.md) for the other 5 values. | `"enriched"` |
| `embeddings` | The model. See the table above. | `"allmpnet"` |
| `cache` | `True` saves the thesaurus vectors on disk. | `True` |

The result has one entry for each group, as in `label_groups()`. In place of `keywords` and `name`,
each group has `matches`: a list of the best terms. Each term is a dict:

| Key | Meaning |
|---|---|
| `leaf` | the term, for example `"LONELINESS"` |
| `path` | the place of the term in the thesaurus, from the broadest term down |
| `score` | the similarity, from -1 to 1 |
| `id` | the web address of the term |

## `standardize_constructs()`: thesaurus terms for each span

```python
from theoryminer import standardize_constructs

matches = standardize_constructs(
    relations,               # the relations from causenet(), or a list of spans
    top=5,                   # keep the 5 best terms for each span
)
```

This function makes no groups. It compares each span with the thesaurus. Use it to see how one
span maps to the thesaurus, or to make a map with one node for each term.

The arguments are the same as for `standardize_groups()`, but there is no `name_by`, and the first
argument is `items`: the relations from `causenet()`, or a list of span strings.

The result has one entry for each span. The value is a list of the best terms, in the form of
`matches` above:

```python
{"social trust": [{"leaf": "TRUST", "score": 0.7604, ...},
                  {"leaf": "INTERPERSONAL TRUST", "score": 0.6876, ...}]}
```
