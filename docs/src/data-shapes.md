# Data shapes

The functions pass plain Python lists and dicts. This page lists the keys of each shape, so that
you can read the results in your own code or in pandas.

## A sentence

One item of `harvest(...)["sentences"]`.

| Key | Meaning |
|---|---|
| `doc_id` | the file name without `.pdf` |
| `page` | the page number |
| `sent_id` | a unique id, for example `d000p0012s003` |
| `section` | the last heading before the sentence |
| `raw` | the sentence as the sentence splitter gave it |
| `clean` | the sentence that `causenet()` reads |
| `flag` | `""`, `"front_matter"`, `"fragment"` or `"long"` |
| `doi`, `title` | the paper, or `""` |

## A dropped row

One item of `harvest(...)["dropped"]`: `doc_id`, `page`, `section`, `drop_reason` and `text`.

## A relation

One item of the list that `causenet()` returns.

| Key | Meaning |
|---|---|
| `rel_id` | a unique id, for example `d000p0012s003r01` |
| `sent_id`, `doc_id`, `page` | from the sentence |
| `cause`, `effect` | the two spans, in lowercase |
| `sentence` | the clean sentence |
| `doi`, `title` | the paper, or `""` |

## Groups

The result of `clusterer()` and `pairwise_grouping()`, keyed by the span:

```python
{"loneliness": {"group": 4, "central": "address loneliness"},
 "levels of loneliness": {"group": 4, "central": "address loneliness"}}
```

A noise span of `clusterer()` has the group `-1`.

## Names

The result of `label_groups()`, keyed by the group id (or by the span, for a noise span):

```python
{4: {"central": "address loneliness", "size": 6,
     "members": ["loneliness", "levels of loneliness", ...],
     "keywords": [("loneliness", 0.91), ...],
     "name": "loneliness levels address"}}
```

`standardize_groups()` and `standardize_constructs()` give each group or span a list of
thesaurus matches, best first. See their reference pages.

## The causal map

`causal_map()` returns a dict with six keys:

| Key | What it holds |
|---|---|
| `nodes` | `{node_id: node}` |
| `edges` | the list of shown edges |
| `hidden` | the list of hidden edges, each with its `drop_reason` |
| `relations` | `{rel_id: relation}`, the relations behind the edges |
| `papers` | one row per paper: `doc_id`, `doi`, `title` |
| `settings` | `min_papers`, `min_sentences`, `min_share` |

A node:

| Key | Meaning |
|---|---|
| `node_id`, `label` | the id and the name of the node |
| `members` | the spans in the node |
| `as_cause`, `as_effect` | the sentences of the shown edges that start at the node, and that end at it |
| `n_sentences` | `as_cause` plus `as_effect` |
| `n_papers` | the papers of the shown edges that touch the node |
| `role` | `cause only`, `effect only` or `cause and effect`; `""` when no shown edge touches the node |
| `shown` | `True` when a shown edge touches the node |

The counts use the shown edges only. A filter that hides an edge also lowers the counts of its
nodes.

An edge: `edge_id`, `source`, `target`, `n_papers`, `n_sentences`, `n_relations`, `rel_ids`,
`doc_ids`, `direction`, `reciprocal`, `self_loop` and `drop_reason`. See
[The causal map](guide/causal-map.md) for their meaning.
