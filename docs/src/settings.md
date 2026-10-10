# Settings and defaults

Each setting of each function, its default, and where the default comes from. The
[reference pages](reference/index.md) give every permitted value.

| function | setting | default | source of the default |
|---|---|---|---|
| `harvest` | `min_words` / `max_words` | 4 / 80 | old cleaning notebook |
| `extract_dois` | `first_pages` / `save` | 2 / `None` | the paper's own DOI is on page 1 (checked by hand: 7 of 7) |
| `extract_references` | `save` / `cache` | `None` / `True` | 214 of 215 DOIs of the sample papers exist at doi.org |
| `download_papers` | `licences` | `None` | `["cc-by"]` keeps only CC BY papers (see [A snowball round](guide/snowball.md)) |
| `download_papers` | `sources` | `None` | `None` = the nine free sources, from `openalex` to `landing_page`; add `tmsr-doi-downloader` |
| `download_papers` | `respect_robots` | `True` | obey `robots.txt`; set `False` only with the right to do so |
| `download_papers` | `email` | `None` | the polite pool of OpenAlex and Crossref, and Unpaywall; `None` keeps `UNPAYWALL_EMAIL` |
| `causenet` | `threshold` | 0.8 | old pipeline sweep 0.5–0.8 |
| `causenet` | `mode` | `neural` | model card default |
| `causenet` | `decision` | `span_only` | since 0.2.0 (`cls+span` before): a cause span and an effect span are enough |
| `causenet` | `avoid_ambiguous` | `True` | since 0.2.0: skip a relation with a pointer span ("this", "it") |
| `causenet` | `batch_size` / `device` | 64 / `auto` | `auto` = an NVIDIA GPU, else an Apple GPU, else the CPU |
| all harmonizer | `embeddings` | `allmpnet` | Paper 3; `bge_base` scores 0.02 F1 higher ([Thesaurus strategies](strategies.md), section 5) |
| `standardize_*` | `taxonomy` | `elsst` | project choice; the only built-in thesaurus |
| `standardize_*` | `strategy` | `enriched` | Paper 3 web tool; confirmed by the held-out test |
| `standardize_*` | `top` | 5 | project choice |
| `standardize_*` | `leaves_only` | `False` | since 0.2.0 (`True` before): broad concepts too, such as TRUST and MOTIVATION |
| `label_groups` | `by` / `top` | `keywords` / 3 | since 0.2.0 (`both` before): the TF-IDF keywords of the group |
| `standardize_*` | `threshold` | `None` | since 0.2.0; `None` gives every span its best concept |
| `standardize_groups` | `name_by` | `mean_sim` | old pipeline's cluster-naming comparison |
| `pairwise_grouping` | `threshold` | 0.69 | Paper 3 `BEST_PAIRWISE_THRESHOLDS` |
| `pairwise_grouping` | `linkage` | `average` | since 0.2.0 (`single` before): single linkage chains (see [Group and name constructs](guide/harmonizer.md)) |
| `clusterer` | `min_cluster_size` / `min_samples` | 2 / 2 | Paper 3 `BEST_CLUSTERING_PARAMS` |
| `clusterer` | `umap` | `None` | Paper 3; the best run had no reduction |
| `causal_map` | `min_papers` / `min_sentences` | 1 / 2 | project choice; 1 paper works for one long book |
| `causal_map` | `min_share` | 0.67 | project choice: a two-way pair needs 2 papers to 1 for one direction |
| `draw_map` | `save` / `height` | `None` / 720 | a notebook shows the page; a script writes `causal_map.html` |

τ, the score that a span needs for a thesaurus concept, is the `threshold` of the `standardize_*`
functions. It is off by default. Choose it per model, per strategy, per thesaurus.
The evidence behind the defaults is in [Thesaurus strategies](strategies.md), section 5.
