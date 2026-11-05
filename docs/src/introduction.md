# theoryminer

`theoryminer` reads a set of research papers and makes a causal map from them.

A causal map shows the constructs of the papers as nodes, and the causal claims between them as
arrows. An arrow from "social support" to "well-being" means that the papers claim that social
support causes well-being. You can click each arrow and read the sentences that make the claim,
with the page and the DOI of each paper.

## The steps

| Step | Function | Input | Output |
|---|---|---|---|
| 1. Read the PDFs | [`harvest()`](guide/harvest.md) | a folder of PDF files | the sentences |
| 2. Find the causal claims | [`causenet()`](guide/causenet.md) | the sentences | the relations: cause, effect, sentence |
| 3. Group the constructs | [`clusterer()`](guide/harmonizer.md) | the relations | groups of spans with the same meaning |
| 4. Name the groups | [`label_groups()`](guide/harmonizer.md) | the groups | a name for each group |
| 5. Make the map | [`causal_map()`](guide/causal-map.md) | the relations and the names | the nodes and the edges |
| 6. Show and save the map | [`draw_map()`, `save_map()`](guide/causal-map.md) | the map | a web page, CSV files |

Other functions do the same steps in a different way, or add steps:

- `pairwise_grouping()` makes groups in a different way from `clusterer()`.
- `standardize_groups()` names the groups with the terms of a social-science thesaurus (ELSST).
- `extract_references()` and `download_papers()` get the papers that your papers cite.
  See [A snowball round](guide/snowball.md).

## How to start

1. [Install](install.md) the package.
2. Run the [quick start](quickstart.md). It makes a map from 7 sample papers.
3. Read the guide page of each step. Each page shows an example, all the arguments and the
   result.

## What the package does not change

The package removes no data without a record. When a step removes a sentence or hides an edge, it
writes the reason. A cause or an effect is always the words of the author. Each edge of the map
leads back to its sentences, pages and papers.
