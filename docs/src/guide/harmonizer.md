# Group and name constructs

Authors use many names for one construct: "loneliness", "feelings of loneliness", "perceived
isolation". Before the map, the spans that mean the same thing must become one node. The package
has three routes.

| Route | Functions | Needs a thesaurus | A node is |
|---|---|---|---|
| Group, then name from the group's own words | `clusterer()` or `pairwise_grouping()`, then `label_groups()` | no | a group, named by its keywords |
| Group, then name with a thesaurus | `clusterer()` or `pairwise_grouping()`, then `standardize_groups()` | yes (ELSST is included) | the best thesaurus concept of a group |
| Name each span with a thesaurus | `standardize_constructs()` | yes | the best thesaurus concept of a span |

Each route gives the `names` that `causal_map()` needs.

```python
from theoryminer import clusterer, label_groups, causal_map

groups = clusterer(relations)
names = label_groups(groups)
cmap = causal_map(relations, names)
```

All the functions read the cause and effect spans of the relations. You can also give them a plain
list of span strings. They use the sentence model `all-mpnet-base-v2` by default. Every similarity
is a cosine.

## Make groups

| Function | Method | Default |
|---|---|---|
| `clusterer()` | HDBSCAN on the span vectors. A span that fits no group stays alone (noise). | `min_cluster_size=2`, `min_samples=2`, no UMAP |
| `pairwise_grouping()` | joins the spans whose cosine is at or above a threshold | `threshold=0.69`, `linkage="average"` |

The result of both is a dict: `{span: {"group": id, "central": span}}`. The central span is the
member that is most like the other members.

Use `linkage="average"`, the default since 0.2.0. With `"single"`, one shared neighbour joins two
groups, and long chains form. When A is like B and B is like C, A and C go into one group, also
when they are far apart.

**Warning:** `pairwise_grouping()` computes the distance between every pair of spans. Its memory
grows with the square of the number of spans: about 10 GB for 50,000 spans. For a large corpus,
use `clusterer()`.

## Name the groups without a thesaurus

`label_groups()` names each group with the words that its members repeat and that the other
groups do not use (class-based TF-IDF). It needs no model and no thesaurus.

| `by` | The name is |
|---|---|
| `"keywords"` (default) | the 3 best keywords, joined by a space |
| `"medoid"` | the central span |
| `"both"` | the central span, then ` \| `, then the keywords |

## Name with the ELSST thesaurus

ELSST (the European Language Social Science Thesaurus, release 5) is part of the package. Its
licence is CC BY-SA 4.0.

`standardize_constructs()` gives each span the 5 best concepts. `standardize_groups()` gives each
group the 5 best concepts. A group of spans gets one name from all its members.

| Setting | Default | What it does |
|---|---|---|
| `strategy` | `"enriched"` | the text that stands for a concept: its label, other labels, scope note and path. See [Thesaurus strategies](../strategies.md). |
| `top` | `5` | the number of concepts for each span or group |
| `leaves_only` | `False` | `False` also allows broad concepts, such as TRUST. `True` allows only the most specific concepts. |
| `threshold` | `None` | `None` gives every span its best concept. A number leaves a span without a concept when its best score is lower. |
| `name_by` (groups only) | `"mean_sim"` | how a group is compared with a concept: the mean of its members (`"mean_sim"`), their mean vector (`"centroid"`), or the central span (`"medoid"`) |
| `taxonomy` | `"elsst"` | the thesaurus. A path to another SKOS `.rdf` or `.rdf.gz` file also works. |

The first run computes the vectors of the thesaurus and caches them in
`~/.cache/theoryminer/taxonomy`. Later runs load them.

## Which route to use

- Start with `clusterer()` and `label_groups()`. They need no thesaurus, and the names use the words
  of your papers.
- Use `standardize_groups()` when you want names from a shared vocabulary, so that you can compare
  your map with other work.
- Use `standardize_constructs()` to check how one span maps to the thesaurus.
